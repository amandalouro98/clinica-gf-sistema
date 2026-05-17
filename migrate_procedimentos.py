"""Migração: adicionar campos valor_unitario, valor_pacote, sessoes_pacote na tabela tratamentos"""
from utils.db import engine

def migrate():
    with engine.connect() as conn:
        # Adicionar colunas se não existirem
        cols = [
            ("valor_unitario", "FLOAT"),
            ("valor_pacote", "FLOAT"),
            ("sessoes_pacote", "INTEGER"),
        ]
        for col_name, col_type in cols:
            try:
                conn.execute(f"ALTER TABLE tratamentos ADD COLUMN {col_name} {col_type}")
                conn.commit()
                print(f"Coluna '{col_name}' adicionada.")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    print(f"Coluna '{col_name}' já existe.")
                    conn.rollback()
                else:
                    print(f"Erro ao adicionar '{col_name}': {e}")
                    conn.rollback()

if __name__ == "__main__":
    migrate()
    print("Migração concluída!")
