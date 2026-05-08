"""
Migração do banco: adapta as tabelas antigas para a nova estrutura.
Execute uma vez: python migrate.py
"""
import os, sqlite3

db_path = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "ClinicaGestao", "db", "database.db")
print(f"Banco: {db_path}")

con = sqlite3.connect(db_path)
cur = con.cursor()

# ── 1. Cria tabela produtos (se não existir) ──────────────────────────────────
cur.execute("""
CREATE TABLE IF NOT EXISTS produtos (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nome       TEXT NOT NULL,
    categoria  TEXT NOT NULL DEFAULT 'outro',
    criado_em  DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

# ── 2. Verifica estrutura atual da tabela estoque ─────────────────────────────
cur.execute("PRAGMA table_info(estoque)")
colunas = {row[1] for row in cur.fetchall()}
print(f"Colunas atuais de 'estoque': {colunas}")

tem_estrutura_nova = "produto_id" in colunas

if not tem_estrutura_nova:
    print("Migrando tabela 'estoque'...")

    # 2a. Migra produtos únicos para a tabela 'produtos'
    cur.execute("SELECT DISTINCT nome_produto, categoria FROM estoque WHERE nome_produto IS NOT NULL")
    produtos_existentes = cur.fetchall()
    for nome, cat in produtos_existentes:
        cur.execute("SELECT id FROM produtos WHERE nome = ?", (nome,))
        if not cur.fetchone():
            cur.execute("INSERT INTO produtos (nome, categoria) VALUES (?, ?)", (nome, cat or "outro"))

    # 2b. Renomeia a tabela antiga
    cur.execute("ALTER TABLE estoque RENAME TO estoque_old")

    # 2c. Cria nova tabela estoque
    cur.execute("""
    CREATE TABLE estoque (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        produto_id        INTEGER NOT NULL REFERENCES produtos(id),
        lote              TEXT,
        quantidade_atual  REAL DEFAULT 0.0,
        quantidade_minima REAL DEFAULT 0.0,
        data_validade     DATE,
        fornecedor        TEXT,
        data_entrada      DATE
    )
    """)

    # 2d. Migra linhas antigas para nova estrutura
    cur.execute("SELECT id, nome_produto, categoria, quantidade_atual, quantidade_minima, data_validade, fornecedor, data_entrada, lote FROM estoque_old")
    for row in cur.fetchall():
        old_id, nome, cat, qtd, qtd_min, validade, forn, data_ent, lote = row
        cur.execute("SELECT id FROM produtos WHERE nome = ?", (nome,))
        prod = cur.fetchone()
        if prod:
            cur.execute("""
                INSERT INTO estoque (produto_id, lote, quantidade_atual, quantidade_minima, data_validade, fornecedor, data_entrada)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (prod[0], lote, qtd or 0.0, qtd_min or 0.0, validade, forn, data_ent))

    print(f"  {len(produtos_existentes)} produto(s) migrado(s).")
else:
    print("Tabela 'estoque' já está na estrutura nova. Nada a fazer.")

# ── 3. Migra movimentacoes_estoque ────────────────────────────────────────────
cur.execute("PRAGMA table_info(movimentacoes_estoque)")
cols_mov = {row[1] for row in cur.fetchall()}

if "lote_id" not in cols_mov:
    print("Atualizando 'movimentacoes_estoque'...")
    cur.execute("ALTER TABLE movimentacoes_estoque RENAME TO movimentacoes_estoque_old")
    cur.execute("""
    CREATE TABLE movimentacoes_estoque (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        lote_id    INTEGER NOT NULL REFERENCES estoque(id),
        produto_id INTEGER REFERENCES produtos(id),
        tipo       TEXT NOT NULL,
        quantidade REAL NOT NULL,
        motivo     TEXT,
        criado_em  DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    # Migra movimentações antigas: produto_id antigo vira lote_id
    cur.execute("SELECT id, produto_id, tipo, quantidade, motivo, criado_em FROM movimentacoes_estoque_old")
    for row in cur.fetchall():
        old_id, old_prod_id, tipo, qtd, motivo, criado = row
        # Tenta achar o lote correspondente ao produto_id antigo
        cur.execute("SELECT id, produto_id FROM estoque WHERE id = ?", (old_prod_id,))
        lote = cur.fetchone()
        if lote:
            cur.execute("""
                INSERT INTO movimentacoes_estoque (lote_id, produto_id, tipo, quantidade, motivo, criado_em)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (lote[0], lote[1], tipo, qtd, motivo, criado))
    print("  movimentacoes_estoque migrado.")
else:
    print("movimentacoes_estoque já está atualizado.")

# ── 4. Cria tabela agenda (se não existir) ────────────────────────────────────
cur.execute("""
CREATE TABLE IF NOT EXISTS agenda (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    data             DATE NOT NULL,
    hora_inicio      TEXT NOT NULL,
    hora_fim         TEXT NOT NULL,
    duracao_min      INTEGER NOT NULL DEFAULT 60,
    cliente_id       INTEGER REFERENCES clientes(id),
    cliente_nome     TEXT,
    profissional     TEXT NOT NULL,
    procedimento     TEXT,
    observacoes      TEXT,
    confirmado       INTEGER DEFAULT 0,
    cor_profissional TEXT DEFAULT '#E3A5C7',
    criado_em        DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

# ── 5. Migra atendimento_materiais ────────────────────────────────────────────
cur.execute("PRAGMA table_info(atendimento_materiais)")
cols_mat = {row[1] for row in cur.fetchall()}

if "lote_id" not in cols_mat:
    print("Atualizando 'atendimento_materiais'...")
    cur.execute("ALTER TABLE atendimento_materiais RENAME TO atendimento_materiais_old")
    cur.execute("""
    CREATE TABLE atendimento_materiais (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        atendimento_id INTEGER NOT NULL REFERENCES atendimentos(id),
        lote_id        INTEGER NOT NULL REFERENCES estoque(id),
        produto_id     INTEGER REFERENCES produtos(id),
        categoria      TEXT,
        quantidade     REAL NOT NULL
    )
    """)
    # Migra registros antigos
    cur.execute("SELECT id, atendimento_id, produto_id, categoria, quantidade FROM atendimento_materiais_old")
    for row in cur.fetchall():
        old_id, at_id, old_prod_id, cat, qtd = row
        cur.execute("SELECT id, produto_id FROM estoque WHERE id = ?", (old_prod_id,))
        lote = cur.fetchone()
        if lote:
            cur.execute("""
                INSERT INTO atendimento_materiais (atendimento_id, lote_id, produto_id, categoria, quantidade)
                VALUES (?, ?, ?, ?, ?)
            """, (at_id, lote[0], lote[1], cat, qtd))
    print("  atendimento_materiais migrado.")

con.commit()
con.close()
print("\nMigracao concluida com sucesso!")
