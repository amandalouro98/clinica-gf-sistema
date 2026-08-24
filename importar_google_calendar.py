"""
Importa agendamentos futuros de arquivos Excel exportados do Google Calendar.

Uso no servidor:
    1) Copie os arquivos .xlsx para /opt/clinica-gf/temp/google_calendar/
    2) docker exec -it clinica-gf-app python importar_google_calendar.py

O script:
    - Lê todos os .xlsx da pasta temp/google_calendar/
    - Mapeia o nome do arquivo para profissional/sala
    - Cria profissionais/salas ausentes com cores padrao
    - Importa apenas eventos a partir de HOJE
    - Evita duplicatas pelo UID do Google Calendar
"""
import os
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.base import Base
from models.client import Client
from models.professional import Professional
from models.room import Room
from models.schedule import ScheduledAppointment
from models.schedule_log import AgendaLog


def _normalizar(texto: str) -> str:
    texto = (texto or "").strip().lower()
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def _hora_str(value) -> str:
    """Converte valor de hora para HH:MM."""
    if pd.isna(value):
        return ""
    if isinstance(value, str):
        value = value.strip()
        # pode vir como "2026-05-12 08:15:00"
        if " " in value:
            value = value.split()[1]
        if len(value) >= 5:
            return value[:5]
        return value
    if isinstance(value, datetime):
        return value.strftime("%H:%M")
    return str(value)[:5]


def _data(value) -> date:
    """Converte valor de data para date."""
    if pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        value = value.strip()
        if " " in value:
            value = value.split()[0]
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
    return None


def _calcular_hora_fim(hora_inicio: str, duracao_min: int) -> str:
    h, m = map(int, hora_inicio.split(":"))
    fim = datetime(2000, 1, 1, h, m) + timedelta(minutes=duracao_min)
    return fim.strftime("%H:%M")


def _extrair_cliente_procedimento(summary: str):
    """Tenta separar 'Cliente - Procedimento' do Summary."""
    if not summary:
        return "N/A", ""
    s = re.sub(r"\s*\(\d+/\d+\)", "", summary)
    s = re.sub(r"\s*[✅✓✔]", "", s)
    s = s.strip()
    if " - " in s:
        cliente, proc = s.split(" - ", 1)
        return cliente.strip(), proc.strip()
    return s.strip(), ""


# Mapeamento do nome do arquivo para (tipo, nome)
# tipo: "profissional" ou "sala"
MAPEAMENTO = {
    "gabi.saudeintegrativa@gmail.com": ("profissional", "Gabi"),
    "gabiofranco87@gmail.com": ("profissional", "Gabi"),
    "juliana": ("profissional", "Juliana"),
    "kawani": ("profissional", "Kauane"),
    "sala 2": ("sala", "Sala 2"),
    "sala 3": ("sala", "Sala 3"),
    "sala 4": ("sala", "Sala 4"),
}

CORES_PADRAO = {
    "Gabi": "#002E7A",
    "Juliana": "#9F6AAF",
    "Kauane": "#A79C8F",
    "Sala 2": "#CC628A",
    "Sala 3": "#F7BF27",
    "Sala 4": "#41CC52",
}


def identificar_fonte(filename: str):
    nome_base = Path(filename).stem.lower()
    for chave, (tipo, nome) in MAPEAMENTO.items():
        if chave in nome_base:
            return tipo, nome
    return None, None


def get_engine():
    db_url = os.getenv("DB_URL")
    if not db_url:
        raise EnvironmentError("DB_URL nao configurada")
    if db_url.startswith("sqlite"):
        return create_engine(db_url, connect_args={"check_same_thread": False})
    return create_engine(db_url, pool_pre_ping=True)


def main():
    pasta = Path(__file__).parent / "temp" / "google_calendar"
    if not pasta.exists():
        print(f"Pasta nao encontrada: {pasta}")
        print("Crie a pasta e copie os arquivos .xlsx do Google Calendar para la.")
        return

    arquivos = sorted(pasta.glob("*.xlsx"))
    if not arquivos:
        print(f"Nenhum arquivo .xlsx encontrado em {pasta}")
        return

    hoje = datetime.now(timezone(timedelta(hours=-3))).date()
    print(f"Importando eventos a partir de {hoje}\n")

    engine = get_engine()
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        total_importados = 0
        total_pulados = 0

        for arquivo in arquivos:
            tipo, nome_fonte = identificar_fonte(arquivo.name)
            if not tipo:
                print(f"[IGNORADO] {arquivo.name}: nao identificado como profissional/sala")
                continue

            print(f"[PROCESSANDO] {arquivo.name} -> {tipo} {nome_fonte}")

            df = pd.read_excel(arquivo)
            if df.empty:
                print("  -> vazio")
                continue

            # Garante/cria profissional/sala no banco
            cor_padrao = CORES_PADRAO.get(nome_fonte, "#E3A5C7")
            if tipo == "profissional":
                prof = db.query(Professional).filter(
                    Professional.nome.ilike(nome_fonte)
                ).first()
                if not prof:
                    prof = Professional(nome=nome_fonte, cor=cor_padrao)
                    db.add(prof)
                    db.commit()
                    print(f"  -> profissional '{nome_fonte}' criado")
                nome_profissional = prof.nome
                cor_profissional = prof.cor or cor_padrao
                sala = None
            else:
                room = db.query(Room).filter(
                    Room.nome.ilike(nome_fonte)
                ).first()
                if not room:
                    room = Room(nome=nome_fonte, cor=cor_padrao)
                    db.add(room)
                    db.commit()
                    print(f"  -> sala '{nome_fonte}' criada")
                nome_profissional = nome_fonte  # salas tambem ficam como "profissional" no agendamento
                cor_profissional = room.cor or cor_padrao
                sala = room.nome

            for _, row in df.iterrows():
                if str(row.get("Type", "")).upper() != "EVENT":
                    continue

                data_evento = _data(row.get("Start Date"))
                if not data_evento or data_evento < hoje:
                    continue

                hora_inicio = _hora_str(row.get("Start Time"))
                hora_fim = _hora_str(row.get("End Time"))
                if not hora_inicio:
                    continue

                duracao = row.get("Duration (Hours)")
                if pd.notna(duracao) and duracao:
                    duracao_min = int(round(float(duracao) * 60))
                else:
                    duracao_min = 60
                if not hora_fim:
                    hora_fim = _calcular_hora_fim(hora_inicio, duracao_min)

                uid = str(row.get("UID", "")).strip()
                if uid and db.query(ScheduledAppointment).filter(
                    ScheduledAppointment.observacoes.ilike(f"%UID: {uid}%")
                ).first():
                    total_pulados += 1
                    continue

                summary = str(row.get("Summary", "")).strip()
                cliente, procedimento = _extrair_cliente_procedimento(summary)

                # Busca cliente cadastrado pelo nome
                cliente_db = db.query(Client).filter(
                    Client.nome.ilike(cliente)
                ).first()
                cliente_id = cliente_db.id if cliente_db else None

                observacoes = f"Importado do Google Calendar. UID: {uid}"
                if row.get("Description") and str(row.get("Description")).strip():
                    observacoes += f"\nDescricao: {str(row.get('Description')).strip()}"

                ag = ScheduledAppointment(
                    data=data_evento,
                    hora_inicio=hora_inicio,
                    hora_fim=hora_fim,
                    duracao_min=duracao_min,
                    cliente_id=cliente_id,
                    cliente_nome=cliente,
                    profissional=nome_profissional,
                    procedimento=procedimento,
                    observacoes=observacoes,
                    confirmado=str(row.get("Status", "")).upper() == "CONFIRMED",
                    cor_profissional=cor_profissional,
                    sala=sala,
                )
                db.add(ag)
                total_importados += 1

            db.commit()

        print(f"\nResumo:")
        print(f"  Importados: {total_importados}")
        print(f"  Pulados (duplicados): {total_pulados}")
        print(f"  Total de arquivos: {len(arquivos)}")

    except Exception as e:
        db.rollback()
        print(f"ERRO: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
