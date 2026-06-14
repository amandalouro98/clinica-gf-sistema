"""
delete_agendamentos_do_dia.py
Apaga todos os agendamentos da data informada em diante.
Uso: docker exec clinica-gf-app python delete_agendamentos_do_dia.py 2026-06-15
"""
import sys
from datetime import date

# Importa todos os modelos para que o SQLAlchemy resolva os relacionamentos
from utils.db import SessionLocal
from models.base import Base
from models.client import Client
from models.user import User
from models.appointment import Appointment, AppointmentMaterial
from models.schedule import ScheduledAppointment
from models.schedule_log import AgendaLog
from models.assessment import Assessment
from models.biometrics import Biometrics
from models.contract import Contract
from models.dose_table import DoseTable
from models.material import Material
from models.professional import Professional
from models.sale import Sale, SaleItem, SessionUsage
from models.stock import Product, StockLote, StockMovement
from models.tratamento import Tratamento


def main(data_corte_str: str):
    ano, mes, dia = map(int, data_corte_str.split("-"))
    data_corte = date(ano, mes, dia)

    db = SessionLocal()
    try:
        ags = db.query(ScheduledAppointment).filter(
            ScheduledAppointment.data >= data_corte
        ).all()

        print(f"Encontrados {len(ags)} agendamentos a partir de {data_corte.strftime('%d/%m/%Y')}")
        if not ags:
            return

        for ag in ags:
            db.delete(ag)
        db.commit()
        print(f"Excluidos {len(ags)} agendamentos com sucesso.")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python delete_agendamentos_do_dia.py YYYY-MM-DD")
        sys.exit(1)
    main(sys.argv[1])
