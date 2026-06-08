"""
migrate_biometrics_novos_campos.py
Adiciona colunas: abdomen_superior, abdomen_inferior, braco_e, braco_d, coxa_e, coxa_d
Execute: python migrate_biometrics_novos_campos.py
"""
from sqlalchemy import text
from utils.db import engine

def migrate():
    novas_colunas = [
        "abdomen_superior",
        "abdomen_inferior",
        "braco_e",
        "braco_d",
        "coxa_e",
        "coxa_d",
    ]
    with engine.connect() as conn:
        for col in novas_colunas:
            try:
                conn.execute(text(f"ALTER TABLE medidas_biometricas ADD COLUMN IF NOT EXISTS {col} FLOAT"))
                conn.commit()
                print(f"OK - Coluna {col} adicionada")
            except Exception as e:
                print(f"AVISO - {col}: {e}")
    print("Migracao concluida.")

if __name__ == "__main__":
    migrate()
