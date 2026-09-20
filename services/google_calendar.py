"""Sincronização bidirecional com o Google Calendar.

- Sistema -> Google: mudanças nos agendamentos são enviadas para o calendário
  do profissional e da sala correspondentes.
- Google -> Sistema: mudanças feitas no Google Calendar entram no sistema ao
  abrir a agenda (verificação automática, no mínimo a cada 3 minutos) ou pelo
  botão "Sincronizar agora".

Conflitos: se o mesmo agendamento for alterado nos dois lados antes de uma
sincronização, a versão do Google prevalece.

O evento no Google guarda o mesmo conteúdo do quadradinho da agenda:
  "Nome — Procedimento" (+ "⏳" para pré-agendamento e "✅" para confirmado).
"""
import os
import json
import hashlib
from collections import defaultdict
from datetime import datetime, timedelta, timezone, date, time as dtime
from urllib.parse import urlencode, quote

import requests

BR_TZ = timezone(timedelta(hours=-3))
API = "https://www.googleapis.com/calendar/v3"
OAUTH_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH_TOKEN = "https://oauth2.googleapis.com/token"
SCOPES = "https://www.googleapis.com/auth/calendar"
REDIRECT_URI = "https://sistema.gabifrancosaude.com.br/?gc_auth=callback"

# Janela de sincronização: hoje -> 180 dias à frente (igual à grade da agenda)
JANELA_FUTURO_DIAS = 180
# Intervalo mínimo entre sincronizações automáticas
MIN_ENTRE_SYNCS_SEG = 180


class _SyncExpirado(Exception):
    """syncToken do Google expirou — precisa sincronização completa."""
    def __init__(self, msg="sincronização incremental expirada (410)"):
        super().__init__(msg)


class _EventoNaoEncontrado(Exception):
    """Evento/calendário não encontrado no Google (404)."""
    def __init__(self, msg="não encontrado no Google (404)"):
        super().__init__(msg)


# ────────────────────────── credenciais do app ──────────────────────────

def _credenciais_app():
    """client_id/secret: variáveis de ambiente ou arquivo JSON de segredos."""
    cid = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
    sec = (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip()
    if cid and sec:
        return cid, sec
    caminhos = [
        os.getenv("GOOGLE_OAUTH_CLIENT_PATH") or "",
        "/app/secrets/google_oauth_client.json",
        "secrets/google_oauth_client.json",
    ]
    for cam in caminhos:
        if not cam or not os.path.exists(cam):
            continue
        try:
            with open(cam, encoding="utf-8") as f:
                dados = json.load(f)
            conf = dados.get("web") or dados.get("installed") or {}
            if conf.get("client_id") and conf.get("client_secret"):
                return conf["client_id"], conf["client_secret"]
        except Exception:
            pass
    return None, None


def configurado():
    cid, sec = _credenciais_app()
    return bool(cid and sec)


def conectado(db):
    from models.google_sync import GoogleToken
    return db.query(GoogleToken).first() is not None


def url_autorizacao():
    cid, _ = _credenciais_app()
    params = dict(
        client_id=cid,
        redirect_uri=REDIRECT_URI,
        response_type="code",
        scope=SCOPES,
        access_type="offline",
        prompt="consent",
    )
    return f"{OAUTH_AUTH}?{urlencode(params)}"


def desconectar(db):
    from models.google_sync import GoogleToken, GoogleSyncState
    db.query(GoogleToken).delete()
    db.query(GoogleSyncState).delete()
    db.commit()


def status_conexao(db):
    from models.google_sync import GoogleToken, GoogleSyncState
    tok = db.query(GoogleToken).first()
    ultimo = (
        db.query(GoogleSyncState)
        .filter(GoogleSyncState.ultimo_sync.isnot(None))
        .order_by(GoogleSyncState.ultimo_sync.desc())
        .first()
    )
    return {
        "configurado": configurado(),
        "conectado": tok is not None,
        "email": (tok.email if tok else None) or None,
        "ultimo_sync": (ultimo.ultimo_sync if ultimo else None),
    }


# ───────────────────────────── tokens OAuth ─────────────────────────────

def _salvar_token(db, payload):
    from models.google_sync import GoogleToken
    tok = db.query(GoogleToken).first() or GoogleToken(refresh_token="")
    if payload.get("refresh_token"):
        tok.refresh_token = payload["refresh_token"]
    tok.access_token = payload.get("access_token")
    tok.expira_em = datetime.now(BR_TZ) + timedelta(
        seconds=int(payload.get("expires_in", 3600)) - 60
    )
    db.add(tok)
    db.commit()
    return tok


def processar_callback(db, code):
    """Troca o código de autorização pelos tokens e guarda a conexão."""
    cid, sec = _credenciais_app()
    if not cid:
        raise RuntimeError("Integração com o Google não configurada no servidor.")
    resp = requests.post(
        OAUTH_TOKEN,
        data=dict(
            code=code,
            client_id=cid,
            client_secret=sec,
            redirect_uri=REDIRECT_URI,
            grant_type="authorization_code",
        ),
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"O Google recusou a autorização ({resp.status_code}).")
    dados = resp.json()
    if not dados.get("refresh_token"):
        raise RuntimeError("O Google não devolveu a autorização permanente. Tente conectar novamente.")
    tok = _salvar_token(db, dados)
    # Guarda o e-mail da conta (id do calendário principal)
    try:
        lista = requests.get(
            f"{API}/users/me/calendarList",
            headers=_hdr(dados["access_token"]),
            timeout=30,
        ).json()
        for item in lista.get("items", []):
            if item.get("primary"):
                tok.email = item.get("id")
                db.commit()
                break
    except Exception:
        pass
    return tok


def _access_token(db):
    from models.google_sync import GoogleToken
    tok = db.query(GoogleToken).first()
    if not tok or not tok.refresh_token:
        return None
    agora = datetime.now(BR_TZ)
    if tok.access_token and tok.expira_em:
        exp = tok.expira_em
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=BR_TZ)
        if agora < exp:
            return tok.access_token
    cid, sec = _credenciais_app()
    resp = requests.post(
        OAUTH_TOKEN,
        data=dict(
            client_id=cid,
            client_secret=sec,
            refresh_token=tok.refresh_token,
            grant_type="refresh_token",
        ),
        timeout=30,
    )
    if resp.status_code != 200:
        # Autorização revogada — desconecta para a equipe reconectar
        db.delete(tok)
        db.commit()
        return None
    dados = resp.json()
    _salvar_token(db, dados)
    return dados["access_token"]


# ───────────────────────── chamadas da API REST ─────────────────────────

def _hdr(access):
    return {"Authorization": f"Bearer {access}"}


def _cal_path(cal_id):
    return quote(cal_id, safe="")


def _api_get(access, caminho, params=None):
    r = requests.get(f"{API}{caminho}", headers=_hdr(access), params=params, timeout=40)
    if r.status_code == 410:
        raise _SyncExpirado()
    if r.status_code == 404:
        raise _EventoNaoEncontrado()
    if r.status_code != 200:
        raise RuntimeError(f"Google API GET {caminho}: {r.status_code} {r.text[:200]}")
    return r.json()


def _api_post(access, cal_id, corpo):
    r = requests.post(
        f"{API}/calendars/{_cal_path(cal_id)}/events",
        headers=_hdr(access), json=corpo, timeout=40,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Google API criar evento: {r.status_code} {r.text[:200]}")
    return r.json()


def _api_put(access, cal_id, event_id, corpo):
    r = requests.put(
        f"{API}/calendars/{_cal_path(cal_id)}/events/{quote(event_id, safe='')}",
        headers=_hdr(access), json=corpo, timeout=40,
    )
    if r.status_code == 404:
        raise _EventoNaoEncontrado()
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Google API atualizar evento: {r.status_code} {r.text[:200]}")
    return r.json()


def _api_delete(access, cal_id, event_id):
    r = requests.delete(
        f"{API}/calendars/{_cal_path(cal_id)}/events/{quote(event_id, safe='')}",
        headers=_hdr(access), timeout=40,
    )
    if r.status_code == 404 or r.status_code == 410:
        raise _EventoNaoEncontrado()
    if r.status_code not in (200, 204):
        raise RuntimeError(f"Google API apagar evento: {r.status_code} {r.text[:200]}")


# ─────────────────────── mapeamento calendários ─────────────────────────

def _mapas(db):
    from models.professional import Professional
    from models.room import Room
    prof_para_cal, sala_para_cal = {}, {}
    for p in db.query(Professional).all():
        if p.google_calendar_id:
            prof_para_cal[p.nome] = p.google_calendar_id
    for r in db.query(Room).all():
        if r.google_calendar_id:
            sala_para_cal[r.nome] = r.google_calendar_id
    return prof_para_cal, sala_para_cal


def _mapa_calendarios(db):
    """{calendar_id: (tipo, nome)} dos calendários mapeados."""
    prof_para_cal, sala_para_cal = _mapas(db)
    mapa = {}
    for nome, cal in prof_para_cal.items():
        mapa[cal] = ("profissional", nome)
    for nome, cal in sala_para_cal.items():
        mapa.setdefault(cal, ("sala", nome))
    return mapa


def _descobrir_calendarios(db, access):
    """Preenche e repara os IDs dos calendários usando a lista real do Google.

    Os arquivos exportados pelo Google têm nome "NomeDoCalendario_<id>@...",
    então IDs cadastrados a partir do nome do arquivo ficam inválidos —
    aqui eles são corrigidos removendo o prefixo e validando contra a lista
    real de calendários da conta.
    """
    from models.professional import Professional
    from models.room import Room

    try:
        itens = _api_get(access, "/users/me/calendarList", {"maxResults": 250}).get("items", [])
    except Exception:
        return

    ids_reais = {item.get("id") for item in itens if item.get("id")}
    primario = None
    por_nome = {}
    for item in itens:
        cal_id = item.get("id")
        if not cal_id:
            continue
        if item.get("primary"):
            primario = cal_id
        for valor in (item.get("summary"), item.get("summaryOverride"), cal_id):
            chave = _norm(valor)
            if chave:
                por_nome.setdefault(chave, cal_id)

    def procurar(nome):
        alvo = _norm(nome)
        if not alvo:
            return None
        if alvo in por_nome:
            return por_nome[alvo]
        for chave, cal_id in por_nome.items():
            if alvo in chave or chave in alvo:
                return cal_id
        return None

    def reparar(cal_id):
        """Remove o prefixo 'Nome_' de IDs vindos do nome do arquivo exportado."""
        if not cal_id or cal_id in ids_reais:
            return cal_id
        if "@" in cal_id:
            local, dominio = cal_id.split("@", 1)
            if "_" in local:
                suspeito = f"{local.rsplit('_', 1)[1]}@{dominio}"
                if suspeito in ids_reais:
                    return suspeito
        return None

    alterou = False
    objetos = db.query(Professional).all() + db.query(Room).all()
    for objeto in objetos:
        atual = objeto.google_calendar_id
        consertado = reparar(atual)
        if consertado and consertado != atual:
            objeto.google_calendar_id = consertado
            alterou = True
        elif not consertado and atual:
            # ID inválido e irreparável: tenta achar pelo nome
            novo = procurar(objeto.nome)
            if novo:
                objeto.google_calendar_id = novo
                alterou = True
        if not objeto.google_calendar_id:
            novo = procurar(objeto.nome)
            if novo:
                objeto.google_calendar_id = novo
                alterou = True

    # Calendário principal da conta (o da Gabi) sem dono -> se sobrar
    # exatamente uma profissional sem calendário, é dela.
    if primario and primario not in {o.google_calendar_id for o in objetos}:
        sem_cal = [
            o for o in objetos
            if not o.google_calendar_id and isinstance(o, Professional)
        ]
        if len(sem_cal) == 1:
            sem_cal[0].google_calendar_id = primario
            alterou = True

    if alterou:
        db.commit()


# ───────────────────────────── conteúdo ────────────────────────────────

def _parse_hora(texto):
    try:
        hh, mm = str(texto or "00:00").split(":")[:2]
        return dtime(int(hh), int(mm))
    except Exception:
        return dtime(0, 0)


def _norm(txt):
    import unicodedata
    txt = unicodedata.normalize("NFKD", str(txt or "")).encode("ascii", "ignore").decode()
    return txt.strip().lower()


def _hash_ag(ag):
    base = "|".join([
        ag.cliente_nome or "", ag.procedimento or "", str(ag.data),
        ag.hora_inicio or "", str(ag.duracao_min or ""), ag.sala or "",
        ag.profissional or "", ag.observacoes or "",
        "1" if getattr(ag, "pre_agendamento", False) else "0",
        "1" if ag.confirmado else "0",
    ])
    return hashlib.md5(base.encode("utf-8")).hexdigest()


def _corpo_evento(ag):
    titulo = (ag.cliente_nome or "").strip() or "Agendamento"
    if ag.procedimento:
        titulo = f"{titulo} — {ag.procedimento}"
    if getattr(ag, "pre_agendamento", False):
        titulo = f"⏳ {titulo}"
    if ag.confirmado:
        titulo = f"{titulo} ✅"
    ini = datetime.combine(ag.data, _parse_hora(ag.hora_inicio), tzinfo=BR_TZ)
    fim = datetime.combine(ag.data, _parse_hora(ag.hora_fim), tzinfo=BR_TZ)
    if fim <= ini:
        fim = fim + timedelta(days=1)
    return {
        "summary": titulo,
        "description": ag.observacoes or "",
        "start": {"dateTime": ini.isoformat(), "timeZone": "America/Sao_Paulo"},
        "end": {"dateTime": fim.isoformat(), "timeZone": "America/Sao_Paulo"},
    }


def _parse_evento(ev):
    """Extrai (data, hora_ini, hora_fim, duracao, nome, proc, obs, pre, conf) ou None."""
    inicio = ev.get("start") or {}
    if not inicio.get("dateTime"):
        return None  # evento de dia inteiro: ignora
    try:
        dt = datetime.fromisoformat(inicio["dateTime"])
        dtf = datetime.fromisoformat((ev.get("end") or {}).get("dateTime") or inicio["dateTime"])
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=BR_TZ)
    if dtf.tzinfo is None:
        dtf = dtf.replace(tzinfo=BR_TZ)
    dt = dt.astimezone(BR_TZ)
    dtf = dtf.astimezone(BR_TZ)
    dur = max(15, int((dtf - dt).total_seconds() // 60) or 60)

    titulo = (ev.get("summary") or "").strip() or "(sem título)"
    pre = False
    if titulo.startswith("⏳"):
        pre = True
        titulo = titulo[1:].strip()
    conf = False
    if titulo.endswith("✅"):
        conf = True
        titulo = titulo[:-1].strip()
    nome, proc = titulo, None
    if " — " in nome:
        nome, proc = [p.strip() for p in nome.split(" — ", 1)]
    return (
        dt.date(), dt.strftime("%H:%M"), dtf.strftime("%H:%M"), dur,
        nome, proc, (ev.get("description") or "").strip(), pre, conf,
    )


# ────────────────────── GOOGLE -> SISTEMA (pull) ────────────────────────

def _janela():
    hoje = datetime.now(BR_TZ).date()
    return hoje, hoje + timedelta(days=JANELA_FUTURO_DIAS)


def _listar_eventos(access, cal_id, sync_token):
    base = {"singleEvents": "true", "maxResults": 250}
    if sync_token:
        base["syncToken"] = sync_token
    else:
        ini, fim = _janela()
        base["timeMin"] = datetime.combine(ini, dtime.min, tzinfo=BR_TZ).isoformat()
        base["timeMax"] = datetime.combine(fim, dtime.max, tzinfo=BR_TZ).isoformat()
        base["orderBy"] = "startTime"
    eventos, page_token = [], None
    while True:
        params = dict(base)
        if page_token:
            params["pageToken"] = page_token
        page = _api_get(access, f"/calendars/{_cal_path(cal_id)}/events", params)
        eventos.extend(page.get("items", []))
        page_token = page.get("nextPageToken")
        if not page_token:
            return eventos, page.get("nextSyncToken")


def _aplicar_evento(db, cal_id, tipo_cal, nome_cal, ev, stats):
    from models.schedule import ScheduledAppointment
    from models.google_sync import GoogleEvento

    campos = _parse_evento(ev)
    if campos is None:
        return
    data, hora_ini, hora_fim, dur, nome, proc, obs, pre, conf = campos
    ini, fim = _janela()
    if not (ini <= data <= fim):
        return
    reserva = nome.startswith("[Sala]")

    link = (
        db.query(GoogleEvento)
        .filter_by(calendar_id=cal_id, event_id=ev["id"])
        .first()
    )
    ag = db.get(ScheduledAppointment, link.agendamento_id) if link else None

    # Evento que já existia no Google: casa com agendamento equivalente
    # (mesma data/hora e mesmo nome) para não duplicar.
    if not ag:
        cands = (
            db.query(ScheduledAppointment)
            .filter(
                ScheduledAppointment.data == data,
                ScheduledAppointment.hora_inicio == hora_ini,
            )
            .all()
        )
        for c in cands:
            if _norm(c.cliente_nome) == _norm(nome):
                ag = c
                break

    if ag is not None:
        ag.data = data
        ag.hora_inicio = hora_ini
        ag.hora_fim = hora_fim
        ag.duracao_min = dur
        if not reserva:
            ag.cliente_nome = nome
            ag.procedimento = proc
        if obs:
            ag.observacoes = obs
        if tipo_cal == "profissional":
            ag.profissional = nome_cal
        else:
            ag.sala = nome_cal
            if not ag.profissional:
                ag.profissional = nome_cal
        if link:
            # evento criado pelo sistema: campos de controle voltam confiáveis
            ag.pre_agendamento = pre
            ag.confirmado = conf
        stats["atualizados"] += 1
    else:
        ag = ScheduledAppointment(
            data=data,
            hora_inicio=hora_ini,
            hora_fim=hora_fim,
            duracao_min=dur,
            cliente_id=None,
            cliente_nome=nome,
            profissional=nome_cal,
            procedimento=("Reserva" if reserva else proc),
            observacoes=obs or None,
            confirmado=conf,
            sala=(nome_cal if tipo_cal == "sala" else None),
            pre_agendamento=pre,
        )
        db.add(ag)
        db.flush()
        stats["criados"] += 1

    db.flush()
    if link:
        link.hash_conteudo = _hash_ag(ag)
    else:
        db.add(GoogleEvento(
            agendamento_id=ag.id,
            calendar_id=cal_id,
            event_id=ev["id"],
            hash_conteudo=_hash_ag(ag),
        ))


def _aplicar_cancelamento(db, access, cal_id, ev, stats):
    from models.schedule import ScheduledAppointment
    from models.google_sync import GoogleEvento

    link = (
        db.query(GoogleEvento)
        .filter_by(calendar_id=cal_id, event_id=ev["id"])
        .first()
    )
    if not link:
        return  # já foi reciclado (ex.: recorrência editada no Google)
    ag = db.get(ScheduledAppointment, link.agendamento_id)
    db.delete(link)
    if ag is None:
        db.commit()
        return
    # Apaga também o espelho no outro calendário (profissional <-> sala)
    for outro in (
        db.query(GoogleEvento)
        .filter(
            GoogleEvento.agendamento_id == ag.id,
            GoogleEvento.id != link.id,
        )
        .all()
    ):
        try:
            _api_delete(access, outro.calendar_id, outro.event_id)
        except (_EventoNaoEncontrado, RuntimeError):
            pass
        db.delete(outro)
    db.delete(ag)
    stats["excluidos"] += 1
    db.commit()


def _pull_calendario(db, access, cal_id, tipo_cal, nome_cal, stats):
    from models.google_sync import GoogleSyncState

    state = db.query(GoogleSyncState).filter_by(calendar_id=cal_id).first()
    token = state.sync_token if state else None
    eventos, novo_token = _listar_eventos(access, cal_id, token)
    _aplicar_eventos_calendario(
        db, access, cal_id, tipo_cal, nome_cal, eventos, novo_token, stats
    )


def _aplicar_eventos_calendario(db, access, cal_id, tipo_cal, nome_cal, eventos, novo_token, stats):
    """Grava no banco os eventos baixados de UM calendário (fase sequencial)."""
    from models.google_sync import GoogleSyncState

    # 1) cria/atualiza; 2) cancelamentos por último (a recorrência editada no
    #    Google chega como "apague o evento antigo + crie o novo" — nessa ordem
    #    o novo recasa com o agendamento existente e nada é perdido)
    cancelados = [e for e in eventos if e.get("status") == "cancelled"]
    for ev in eventos:
        if ev.get("status") != "cancelled":
            try:
                _aplicar_evento(db, cal_id, tipo_cal, nome_cal, ev, stats)
            except Exception as ex:
                stats["erros"].append(f"{nome_cal}: {ex}")
    db.commit()
    for ev in cancelados:
        try:
            _aplicar_cancelamento(db, access, cal_id, ev, stats)
        except Exception as ex:
            stats["erros"].append(f"{nome_cal}: {ex}")

    state = db.query(GoogleSyncState).filter_by(calendar_id=cal_id).first()
    if state is None:
        state = GoogleSyncState(calendar_id=cal_id)
        db.add(state)
    state.sync_token = novo_token
    state.ultimo_sync = datetime.now(BR_TZ)
    db.commit()


# ────────────────────── SISTEMA -> GOOGLE (push) ────────────────────────

def _push(db, access, stats):
    from models.schedule import ScheduledAppointment
    from models.google_sync import GoogleEvento

    prof_para_cal, sala_para_cal = _mapas(db)
    ini, fim = _janela()
    ags = (
        db.query(ScheduledAppointment)
        .filter(ScheduledAppointment.data >= ini, ScheduledAppointment.data <= fim)
        .all()
    )
    todos_ids = {i for (i,) in db.query(ScheduledAppointment.id).all()}
    links = db.query(GoogleEvento).all()
    por_ag = defaultdict(list)
    for l in links:
        por_ag[l.agendamento_id].append(l)

    # 1) agendamento apagado no sistema -> apaga o evento no Google
    for l in links:
        if l.agendamento_id not in todos_ids:
            try:
                _api_delete(access, l.calendar_id, l.event_id)
            except _EventoNaoEncontrado:
                pass
            except Exception as ex:
                stats["erros"].append(f"apagar espelho: {ex}")
                continue
            db.delete(l)
    db.commit()

    # 2) cada agendamento da janela.
    # O Google Calendar é a fonte da verdade: agendamentos antigos do sistema
    # (sem vínculo com um evento do Google) NÃO são enviados, para não lotar
    # os calendários da clínica com eventos duplicados.
    for ag in ags:
        if not por_ag.get(ag.id):
            continue  # agendamento que não veio do Google: não envia
        hash_atual = _hash_ag(ag)
        desejados = set()
        if prof_para_cal.get(ag.profissional):
            desejados.add(prof_para_cal[ag.profissional])
        if ag.sala and sala_para_cal.get(ag.sala):
            desejados.add(sala_para_cal[ag.sala])
        atuais = {l.calendar_id: l for l in por_ag.get(ag.id, [])}

        # mudou de profissional/sala: remove do calendário antigo
        for cal_id, l in list(atuais.items()):
            if cal_id not in desejados:
                try:
                    _api_delete(access, cal_id, l.event_id)
                except _EventoNaoEncontrado:
                    pass
                except Exception as ex:
                    stats["erros"].append(f"remover de calendário antigo: {ex}")
                    continue
                db.delete(l)

        for cal_id in desejados:
            l = atuais.get(cal_id)
            if l is None:
                try:
                    ev = _api_post(access, cal_id, _corpo_evento(ag))
                    db.add(GoogleEvento(
                        agendamento_id=ag.id,
                        calendar_id=cal_id,
                        event_id=ev.get("id"),
                        hash_conteudo=hash_atual,
                    ))
                    stats["enviados"] += 1
                except Exception as ex:
                    stats["erros"].append(f"enviar para o Google: {ex}")
            elif l.hash_conteudo != hash_atual:
                try:
                    try:
                        _api_put(access, cal_id, l.event_id, _corpo_evento(ag))
                    except _EventoNaoEncontrado:
                        ev = _api_post(access, cal_id, _corpo_evento(ag))
                        l.event_id = ev.get("id")
                    l.hash_conteudo = hash_atual
                    stats["enviados"] += 1
                except Exception as ex:
                    stats["erros"].append(f"atualizar no Google: {ex}")
        db.commit()


# ─────────────────────────── ciclo completo ─────────────────────────────

def _sync_recente(db):
    from models.google_sync import GoogleSyncState
    ultimo = (
        db.query(GoogleSyncState.ultimo_sync)
        .filter(GoogleSyncState.ultimo_sync.isnot(None))
        .order_by(GoogleSyncState.ultimo_sync.desc())
        .first()
    )
    if not ultimo or not ultimo[0]:
        return False
    t = ultimo[0]
    if t.tzinfo is None:
        t = t.replace(tzinfo=BR_TZ)
    return (datetime.now(BR_TZ) - t).total_seconds() < MIN_ENTRE_SYNCS_SEG


def sincronizar(db, forcar=False):
    """Executa um ciclo: envia as mudanças locais e puxa as do Google.

    A ordem importa: o envio (sistema -> Google) roda ANTES do pull, para
    que uma edição feita no sistema não seja revertida pela versão antiga
    que ainda está no Google.

    Retorna um dicionário de estatísticas ou None quando não há o que fazer.
    """
    if not configurado():
        return None
    if not conectado(db):
        return None
    if not forcar and _sync_recente(db):
        return None
    access = _access_token(db)
    if not access:
        return {"erros": ["Não foi possível renovar o acesso ao Google — conecte novamente."]}

    stats = {"criados": 0, "atualizados": 0, "excluidos": 0, "enviados": 0, "erros": []}
    # Os IDs podem não ter sido cadastrados manualmente. O Google fornece
    # summary/summaryOverride, então conseguimos localizar pelo nome.
    _descobrir_calendarios(db, access)
    try:
        _push(db, access, stats)
    except Exception as ex:
        db.rollback()
        stats["erros"].append(f"envio: {ex}")

    # ── PULL em duas fases ──
    # Fase 1 (paralela): baixa os eventos de TODOS os calendários ao mesmo
    # tempo — eram ~7 chamadas em sequência (2-5 s) e agora levam o tempo de
    # uma só (~0,5 s). Só HTTP, sem tocar no banco (sessão não é thread-safe).
    from concurrent.futures import ThreadPoolExecutor
    from models.google_sync import GoogleSyncState

    mapa = _mapa_calendarios(db)
    tokens_atuais = {}
    for _cal_id in mapa:
        _st = db.query(GoogleSyncState).filter_by(calendar_id=_cal_id).first()
        tokens_atuais[_cal_id] = _st.sync_token if _st else None

    baixados = {}
    expirados = []
    if mapa:
        with ThreadPoolExecutor(max_workers=min(10, len(mapa))) as ex:
            futuros = {
                ex.submit(_listar_eventos, access, _cal_id, tokens_atuais[_cal_id]): _cal_id
                for _cal_id in mapa
            }
            for fut, _cal_id in futuros.items():
                try:
                    baixados[_cal_id] = fut.result()
                except _SyncExpirado:
                    expirados.append(_cal_id)
                except Exception as ex_erro:
                    stats["erros"].append(f"{mapa[_cal_id][1]}: {ex_erro}")

    # token incremental expirou: baixa aquele calendário inteiro
    for _cal_id in expirados:
        try:
            db.query(GoogleSyncState).filter_by(calendar_id=_cal_id).delete()
            db.commit()
            baixados[_cal_id] = _listar_eventos(access, _cal_id, None)
        except Exception as ex_erro:
            stats["erros"].append(f"{mapa[_cal_id][1]}: {ex_erro}")

    # Fase 2 (sequencial): aplica no banco, um calendário por vez
    for _cal_id, (_tipo_cal, _nome_cal) in mapa.items():
        if _cal_id not in baixados:
            continue
        _evs, _ntok = baixados[_cal_id]
        try:
            _aplicar_eventos_calendario(
                db, access, _cal_id, _tipo_cal, _nome_cal, _evs, _ntok, stats
            )
        except Exception as ex:
            stats["erros"].append(f"{_nome_cal}: {ex}")
    return stats


def enviar_agendamentos(db, ag_ids):
    """Cria os eventos no Google para agendamentos criados no sistema.

    Chamado na criação de novos agendamentos: o evento entra nos calendários
    do profissional e da sala e fica vinculado (GoogleEvento).
    """
    if not ag_ids:
        return None
    if not configurado() or not conectado(db):
        return None
    access = _access_token(db)
    if not access:
        return {"erros": ["Sem acesso ao Google — reconecte."]}
    from models.schedule import ScheduledAppointment
    from models.google_sync import GoogleEvento

    prof_para_cal, sala_para_cal = _mapas(db)
    erros = []
    for ag_id in ag_ids:
        ag = db.get(ScheduledAppointment, ag_id)
        if ag is None:
            continue
        desejados = set()
        if prof_para_cal.get(ag.profissional):
            desejados.add(prof_para_cal[ag.profissional])
        if ag.sala and sala_para_cal.get(ag.sala):
            desejados.add(sala_para_cal[ag.sala])
        for cal_id in desejados:
            ja_tem = (
                db.query(GoogleEvento)
                .filter_by(agendamento_id=ag_id, calendar_id=cal_id)
                .first()
            )
            if ja_tem:
                continue
            try:
                ev = _api_post(access, cal_id, _corpo_evento(ag))
                db.add(GoogleEvento(
                    agendamento_id=ag_id,
                    calendar_id=cal_id,
                    event_id=ev.get("id"),
                    hash_conteudo=_hash_ag(ag),
                ))
                db.commit()
            except Exception as ex:
                db.rollback()
                erros.append(str(ex))
    return {"erros": erros} if erros else None


def sincronizar_agendamento(db, ag):
    """Envia ao Google, na hora, as mudanças de UM agendamento.

    Usado ao salvar a edição no espelho: atualiza o evento do profissional
    e da sala (1-2 chamadas, instantâneo), em vez de rodar a sincronização
    completa de todos os calendários.
    """
    if ag is None or not configurado() or not conectado(db):
        return
    access = _access_token(db)
    if not access:
        return
    from models.google_sync import GoogleEvento

    prof_para_cal, sala_para_cal = _mapas(db)
    desejados = set()
    if prof_para_cal.get(ag.profissional):
        desejados.add(prof_para_cal[ag.profissional])
    if ag.sala and sala_para_cal.get(ag.sala):
        desejados.add(sala_para_cal[ag.sala])

    links = db.query(GoogleEvento).filter_by(agendamento_id=ag.id).all()
    hash_atual = _hash_ag(ag)
    atuais = set()
    for l in links:
        if l.calendar_id in desejados:
            atuais.add(l.calendar_id)
            try:
                try:
                    _api_put(access, l.calendar_id, l.event_id, _corpo_evento(ag))
                except _EventoNaoEncontrado:
                    ev = _api_post(access, l.calendar_id, _corpo_evento(ag))
                    l.event_id = ev.get("id")
            except Exception:
                pass  # não bloqueia o fechamento do popup
            l.hash_conteudo = hash_atual
        else:
            # mudou de profissional/sala: apaga do calendário antigo
            try:
                _api_delete(access, l.calendar_id, l.event_id)
            except Exception:
                pass
            db.delete(l)
    # calendário que ainda não tinha evento (ex.: ganhou sala agora)
    for cal_id in desejados - atuais:
        try:
            ev = _api_post(access, cal_id, _corpo_evento(ag))
            db.add(GoogleEvento(
                agendamento_id=ag.id,
                calendar_id=cal_id,
                event_id=ev.get("id"),
                hash_conteudo=hash_atual,
            ))
        except Exception:
            pass
    db.commit()


def excluir_agendamento(db, ag):
    """Apaga do Google os eventos vinculados a um agendamento.

    Deve ser chamado ANTES de db.delete(ag). Os vínculos locais são
    sempre removidos aqui — o ON DELETE CASCADE do banco não é aplicado
    pelo SQLite e o evento ficaria órfão no Google.
    """
    if ag is None:
        return
    from models.google_sync import GoogleEvento
    links = db.query(GoogleEvento).filter_by(agendamento_id=ag.id).all()
    if not links:
        return
    if configurado() and conectado(db):
        access = _access_token(db)
        if access:
            for l in links:
                try:
                    _api_delete(access, l.calendar_id, l.event_id)
                except Exception:
                    pass  # não bloqueia a exclusão local
    for l in links:
        db.delete(l)
    db.commit()
