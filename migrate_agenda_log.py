"""Cria tabela agenda_log para auditoria de agendamentos."""
import sqlite3, os

DB_PATH = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "ClinicaGestao", "db", "database.db"
)

def run():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agenda_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agendamento_id INTEGER,
            acao TEXT NOT NULL,
            usuario_id INTEGER,
            usuario_nome TEXT,
            dados_antes TEXT,
            dados_depois TEXT,
            criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    print("Tabela agenda_log pronta.")
    conn.close()

if __name__ == "__main__":
    run()
