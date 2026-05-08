import sqlite3, os
db = os.path.join(os.environ.get("LOCALAPPDATA", ""), "ClinicaGestao", "db", "database.db")
con = sqlite3.connect(db)
con.execute("""CREATE TABLE IF NOT EXISTS profissionais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    cor TEXT DEFAULT '#E3A5C7',
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
)""")
con.commit()
con.close()
print("Tabela profissionais criada com sucesso!")
