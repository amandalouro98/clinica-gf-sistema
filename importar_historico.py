"""
Importa o histórico de atendimentos do Excel para o banco de dados.
Uso: python importar_historico.py
Versao: 2.1 - Usa utils.db
"""
import pandas as pd
from datetime import date
from sqlalchemy import text
from utils.db import engine

df = pd.read_excel("histórico de atendimentos.xlsx")
print(f"Total de registros no Excel: {len(df)}")

with engine.connect() as conn:
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
        mes = data_at.strftime("%Y-%m")

        # Buscar cliente pelo nome (ILIKE = case insensitive)
        result = conn.execute(text("SELECT id FROM clientes WHERE nome ILIKE :nome"), {"nome": f"%{nome_cliente}%"})
        cliente_row = result.fetchone()
        
        if cliente_row:
            cliente_id = cliente_row[0]
        else:
            # Criar novo cliente
            result = conn.execute(
                text("INSERT INTO clientes (nome, telefone, email) VALUES (:nome, '', '') RETURNING id"),
                {"nome": nome_cliente}
            )
            cliente_id = result.fetchone()[0]
            clientes_criados.add(nome_cliente)
            print(f"  Cliente criado: {nome_cliente}")
            conn.commit()

        # Inserir atendimento
        conn.execute(
            text("""
                INSERT INTO atendimentos (data, mes, cliente_id, protocolo_atendimento, queixa_consulta, tipo_tratamento, observacoes)
                VALUES (:data, :mes, :cliente_id, :protocolo, :queixa, :tipo_trat, :obs)
            """),
            {
                "data": data_at,
                "mes": mes,
                "cliente_id": cliente_id,
                "protocolo": protocolo,
                "queixa": queixa,
                "tipo_trat": tipo_trat,
                "obs": obs
            }
        )
        inseridos += 1
        
        # Commit a cada 100 registros
        if inseridos % 100 == 0:
            conn.commit()
            print(f"  {inseridos} registros processados...")
    
    conn.commit()
    print(f"\nImportacao concluida! {inseridos} atendimentos inseridos.")
    print(f"Clientes novos criados: {len(clientes_criados)}")
