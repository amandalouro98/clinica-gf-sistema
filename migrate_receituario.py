"""Adiciona coluna receituario na tabela avaliacoes."""
import sqlite3, os

DB_PATH = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "ClinicaGestao", "db", "database.db"
)

def run():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Verifica se coluna já existe
    cur.execute("PRAGMA table_info(avaliacoes)")
    cols = [row[1] for row in cur.fetchall()]
    if "receituario" not in cols:
        cur.execute("ALTER TABLE avaliacoes ADD COLUMN receituario TEXT")
        conn.commit()
        print("Coluna 'receituario' adicionada à tabela avaliacoes.")
    else:
        print("Coluna 'receituario' já existe.")
    conn.close()

if __name__ == "__main__":
    run()
