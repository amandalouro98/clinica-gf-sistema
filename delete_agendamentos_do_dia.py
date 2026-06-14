"""
delete_agendamentos_do_dia.py
Apaga todos os agendamentos da data informada em diante.
Uso: docker exec clinica-gf-app python delete_agendamentos_do_dia.py 2026-06-15
"""
import sys
from datetime import date
from utils.db import SessionLocal
from models.schedule import ScheduledAppointment


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
