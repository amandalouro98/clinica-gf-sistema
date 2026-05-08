import sqlite3, os

db_path = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'ClinicaGestao', 'db', 'database.db')
print("Banco:", db_path)

con = sqlite3.connect(db_path)
cur = con.cursor()

try:
    cur.executescript("""
        PRAGMA foreign_keys=OFF;

        CREATE TABLE clientes_new (
            id INTEGER NOT NULL PRIMARY KEY,
            nome VARCHAR NOT NULL,
            cpf VARCHAR,
            data_nascimento DATE,
            telefone VARCHAR,
            email VARCHAR,
            profissao VARCHAR,
            endereco VARCHAR,
            bairro VARCHAR,
            cidade VARCHAR,
            peso FLOAT,
            altura FLOAT,
            imc FLOAT,
            exames_recentes TEXT,
            funcionamento_intestinal VARCHAR,
            uso_vitaminas VARCHAR,
            marcacao_corporal TEXT,
            neoplasia BOOLEAN DEFAULT 0,
            epilepsia BOOLEAN DEFAULT 0,
            outras_condicoes TEXT,
            queixa_principal TEXT,
            termo_aceite BOOLEAN DEFAULT 0
        );

        INSERT INTO clientes_new
        SELECT id, nome, cpf, data_nascimento, telefone, email, profissao,
               endereco, bairro, cidade, peso, altura, imc, exames_recentes,
               funcionamento_intestinal, uso_vitaminas, marcacao_corporal,
               neoplasia, epilepsia, outras_condicoes, queixa_principal,
               termo_aceite
        FROM clientes;

        DROP TABLE clientes;

        ALTER TABLE clientes_new RENAME TO clientes;

        PRAGMA foreign_keys=ON;
    """)
    con.commit()
    cur.execute("SELECT count(*) FROM clientes")
    print(f"CPF agora permite NULL. Clientes no banco: {cur.fetchone()[0]}")
except Exception as e:
    con.rollback()
    print("Erro:", e)
finally:
    con.close()
