"""
Importa o histórico de atendimentos do Excel para o banco de dados.
Uso: python importar_historico.py
"""
import pandas as pd
from datetime import date
from utils.db import SessionLocal, engine
from models.base import Base
from models.client import Client
from models.appointment import Appointment

Base.metadata.create_all(bind=engine)

df = pd.read_excel("histórico de atendimentos.xlsx")
print(f"Total de registros no Excel: {len(df)}")

db = SessionLocal()
try:
    inseridos = 0
    clientes_criados = set()

    for _, row in df.iterrows():
        data_at = row.get("DATA")
        nome_cliente = str(row.get("CLIENTE", "")).strip()
        protocolo = str(row.get("PROTOCOLO", "")) if pd.notna(row.get("PROTOCOLO")) else None
        queixa = str(row.get("QUEIXA", "")) if pd.notna(row.get("QUEIXA")) else None
        tipo_trat = str(row.get("TIPO DE TRATAMENTO", "")) if pd.notna(row.get("TIPO DE TRATAMENTO")) else None
        obs = str(row.get("OBSERVAÇÕES", "")) if pd.notna(row.get("OBSERVAÇÕES")) else None

        if not nome_cliente:
            continue

        # Converter data
        if pd.isna(data_at):
            data_at = date.today()
        else:
            data_at = pd.to_datetime(data_at).date()

        # Buscar cliente pelo nome
        cliente = db.query(Client).filter(Client.nome.ilike(f"%{nome_cliente}%")).first()
        if not cliente:
            cliente = Client(nome=nome_cliente, telefone="", email="")
            db.add(cliente)
            db.flush()
            clientes_criados.add(nome_cliente)
            print(f"  Cliente criado: {nome_cliente}")

        mes = data_at.strftime("%Y-%m")
        at = Appointment(
            data=data_at,
            mes=mes,
            cliente_id=cliente.id,
            protocolo_atendimento=protocolo,
            queixa_consulta=queixa,
            tipo_tratamento=tipo_trat,
            observacoes=obs,
        )
        db.add(at)
        inseridos += 1

    db.commit()
    print(f"\nImportacao concluida! {inseridos} atendimentos inseridos.")
    print(f"Clientes novos criados: {len(clientes_criados)}")
finally:
    db.close()
