"""Auditoria SOMENTE LEITURA da sincronização Google Calendar <-> sistema.

Não cria, altera nem apaga nenhum dado da clínica. A única escrita possível
é a renovação automática do token de acesso do Google (necessária para
consultar a API) — nenhum agendamento, evento ou vínculo é tocado.

Uso (no servidor, dentro do container):
    docker exec -it clinica-gf-app python /app/diagnostico_sync.py
    docker exec -it clinica-gf-app python /app/diagnostico_sync.py --rapido
        (--rapido pula as verificações GET evento a evento, mais lento)

O relatório sai em 5 blocos:
  1) Agendamentos duplicados no sistema (mesmo paciente/data/hora)
  2) Vínculos locais quebrados (apontam para agendamento inexistente)
  3) Vínculos cujo evento não existe mais no Google (órfãos no Google)
  4) Eventos no Google sem agendamento correspondente no sistema
  5) Agendamentos do sistema SEM vínculo com o Google (candidatos ao que
     "sumiu do Google" — ex.: Adriana, Layza, Fátima...)
"""
import sys
from collections import defaultdict
from datetime import datetime

# Importa os modelos na mesma ordem do app para o SQLAlchemy resolver
# todos os relacionamentos antes de qualquer consulta.
from models.base import Base  # noqa: F401
from models.user import User  # noqa: F401
from models.client import Client  # noqa: F401
from models.assessment import Assessment  # noqa: F401
from models.stock import Product, StockLote, StockMovement  # noqa: F401
from models.appointment import Appointment, AppointmentMaterial  # noqa: F401
from models.biometrics import Biometrics  # noqa: F401
from models.contract import Contract  # noqa: F401
from models.schedule import ScheduledAppointment
from models.professional import Professional  # noqa: F401
from models.room import Room  # noqa: F401
from models.sale import Sale, SaleItem, SessionUsage  # noqa: F401
from models.schedule_log import AgendaLog  # noqa: F401
from models.dose_table import DoseTable  # noqa: F401
from models.material import Material  # noqa: F401
from models.tratamento import Tratamento  # noqa: F401
from models.deletion_log import RegistroExclusao  # noqa: F401
from models.form_response import FormResposta  # noqa: F401
from models.google_sync import GoogleToken, GoogleEvento, GoogleSyncState  # noqa: F401
from models.app_setting import AppSetting  # noqa: F401
from models.task import Task  # noqa: F401

from utils.db import SessionLocal
import services.google_calendar as g


def _fmt_data(d):
    return d.strftime("%d/%m/%Y (%a)") if d else "?"


def bloco(titulo):
    print()
    print("=" * 72)
    print(titulo)
    print("=" * 72)


def main():
    rapido = "--rapido" in sys.argv
    db = SessionLocal()
    try:
        ini, fim = g._janela()
        print(f"Janela analisada: {_fmt_data(ini)} -> {_fmt_data(fim)}")
        if rapido:
            print("Modo --rapido: verificacoes GET no Google foram puladas.")

        ags = (
            db.query(ScheduledAppointment)
            .filter(ScheduledAppointment.data >= ini,
                    ScheduledAppointment.data <= fim)
            .order_by(ScheduledAppointment.data, ScheduledAppointment.hora_inicio)
            .all()
        )
        links = db.query(GoogleEvento).all()
        por_ag = defaultdict(list)
        par_cal_evento = set()
        for l in links:
            por_ag[l.agendamento_id].append(l)
            par_cal_evento.add((l.calendar_id, l.event_id))

        # ── 1) duplicados no sistema ──────────────────────────────────────
        bloco("1) AGENDAMENTOS DUPLICADOS NO SISTEMA (mesmo paciente/data/hora)")
        grupos = defaultdict(list)
        for ag in ags:
            grupos[(ag.data, ag.hora_inicio, g._norm(ag.cliente_nome))].append(ag)
        dups = {k: v for k, v in grupos.items() if len(v) > 1}
        if not dups:
            print("Nenhum duplicado encontrado.")
        for (data, hora, _nome), lista in sorted(dups.items()):
            print(f"\n{_fmt_data(data)} {hora} — {lista[0].cliente_nome} "
                  f"({len(lista)} agendamentos)")
            for ag in lista:
                vincs = por_ag.get(ag.id, [])
                vinc_txt = (
                    "vinculado: " + ", ".join(
                        f"{l.calendar_id.split('@')[0][:18]}/{l.event_id[:10]}"
                        for l in vincs
                    ) if vincs else "SEM VINCULO com o Google"
                )
                flags = []
                if ag.pre_agendamento:
                    flags.append("pre-agendamento")
                if ag.confirmado:
                    flags.append("confirmado")
                print(f"  id={ag.id} | prof={ag.profissional} | "
                      f"proc={ag.procedimento} | sala={ag.sala} | "
                      f"{'/'.join(flags) or '-'} | {vinc_txt}")

        # ── 2) vínculos locais quebrados ──────────────────────────────────
        bloco("2) VINCULOS LOCAIS QUEBRADOS (apontam p/ agendamento inexistente)")
        ids_vivos = {ag.id for ag in db.query(ScheduledAppointment.id).all()}
        quebrados = [l for l in links if l.agendamento_id not in ids_vivos]
        if not quebrados:
            print("Nenhum.")
        for l in quebrados:
            print(f"  GoogleEvento id={l.id} agendamento_id={l.agendamento_id} "
                  f"cal={l.calendar_id} evento={l.event_id}")

        # ── 3) vínculos cujo evento sumiu do Google ───────────────────────
        bloco("3) VINCULOS CUJO EVENTO NAO EXISTE MAIS NO GOOGLE (orfãos)")
        access = g._access_token(db)
        if not access:
            print("Sem acesso ao Google (token ausente) — bloco pulado.")
            orfaos_google = []
        elif rapido:
            print("Pulado (--rapido).")
            orfaos_google = []
        else:
            orfaos_google = []
            total = len(links)
            for i, l in enumerate(links, 1):
                if i % 100 == 0:
                    print(f"  ... verificando {i}/{total}", flush=True)
                try:
                    g._api_get(
                        access,
                        f"/calendars/{g._cal_path(l.calendar_id)}/events/"
                        f"{g.quote(l.event_id, safe='')}",
                    )
                except g._EventoNaoEncontrado:
                    orfaos_google.append(l)
                except Exception as ex:
                    print(f"  [aviso] falha ao verificar evento "
                          f"{l.event_id[:12]}: {ex}")
            if not orfaos_google:
                print("Nenhum órfão: todos os vínculos existem no Google.")
            for l in orfaos_google:
                ag = db.get(ScheduledAppointment, l.agendamento_id)
                desc = (
                    f"{ag.cliente_nome} em {_fmt_data(ag.data)} {ag.hora_inicio}"
                    if ag else f"agendamento_id={l.agendamento_id} (inexistente)"
                )
                print(f"  {desc} | cal={l.calendar_id.split('@')[0]} | "
                      f"evento={l.event_id[:14]}...")

        # ── 4) eventos no Google sem agendamento no sistema ───────────────
        bloco("4) EVENTOS NO GOOGLE SEM AGENDAMENTO NO SISTEMA")
        if not access:
            print("Sem acesso ao Google — bloco pulado.")
        else:
            mapa = g._mapa_calendarios(db)
            sem_match = []
            for cal_id, (tipo_cal, nome_cal) in mapa.items():
                try:
                    eventos, _ = g._listar_eventos(access, cal_id, None)
                except Exception as ex:
                    print(f"  [aviso] nao consegui listar {nome_cal}: {ex}")
                    continue
                for ev in eventos:
                    if ev.get("status") == "cancelled":
                        continue
                    if (cal_id, ev.get("id")) in par_cal_evento:
                        continue
                    campos = g._parse_evento(ev)
                    if campos is None:
                        continue
                    data, hora_ini, _hf, _dur, nome, proc, _obs, pre, _c = campos
                    if not (ini <= data <= fim):
                        continue
                    priv = (ev.get("extendedProperties") or {}).get("private") or {}
                    gid = priv.get("gf_ag_id")
                    alvo = db.get(ScheduledAppointment, int(gid)) \
                        if gid and str(gid).isdigit() else None
                    sem_match.append(
                        (data, hora_ini, nome_cal, nome, proc, pre, gid, alvo)
                    )
            if not sem_match:
                print("Nenhum: todo evento do Google tem agendamento no sistema.")
            for data, hora, nome_cal, nome, proc, pre, gid, alvo in sorted(sem_match):
                extra = ""
                if alvo is not None:
                    extra = (f"  <-- gf_ag_id={gid} APONTA para agendamento "
                             f"existente id={alvo.id} (vinculo perdido, recasavel)")
                elif gid:
                    extra = f"  <-- gf_ag_id={gid} sem agendamento correspondente"
                print(f"  {_fmt_data(data)} {hora} | {nome_cal} | "
                      f"{'⏳ ' if pre else ''}{nome}"
                      f"{(' — ' + proc) if proc else ''}{extra}")

        # ── 5) agendamentos do sistema SEM vínculo com o Google ───────────
        bloco("5) AGENDAMENTOS DO SISTEMA SEM VINCULO COM O GOOGLE "
              "(candidatos ao que sumiu do Google)")
        sem_vinculo = [ag for ag in ags if not por_ag.get(ag.id)]
        if not sem_vinculo:
            print("Nenhum: todo agendamento da janela está no Google.")
        por_dia = defaultdict(list)
        for ag in sem_vinculo:
            por_dia[ag.data].append(ag)
        for data in sorted(por_dia):
            print(f"\n{_fmt_data(data)}")
            for ag in por_dia[data]:
                flags = []
                if ag.pre_agendamento:
                    flags.append("PRE-AGENDAMENTO")
                if ag.confirmado:
                    flags.append("confirmado")
                print(f"  {ag.hora_inicio}-{ag.hora_fim} | {ag.cliente_nome} | "
                      f"prof={ag.profissional} | proc={ag.procedimento} | "
                      f"sala={ag.sala} | {'/'.join(flags) or '-'} | id={ag.id}")

        bloco("RESUMO")
        print(f"Agendamentos na janela: {len(ags)}")
        print(f"Grupos duplicados no sistema: {len(dups)}")
        print(f"Vinculos locais quebrados: {len(quebrados)}")
        print(f"Vinculos orfaos no Google: "
              f"{len(orfaos_google) if not rapido else '(pulado)'}")
        print(f"Agendamentos sem vinculo com o Google: {len(sem_vinculo)}")
        print()
        print("Relatorio somente leitura — nenhum dado foi alterado.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
