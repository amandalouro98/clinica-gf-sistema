"""
Script de importação de estoque a partir da planilha estoque_produtos.xlsx.

Uso no servidor:
  docker cp importar_estoque.py clinica-gf-app:/app/
  docker cp estoque_produtos.xlsx clinica-gf-app:/app/
  docker exec clinica-gf-app python importar_estoque.py

O script:
  1. Faz upsert dos produtos (cria só se não existir pelo nome exato)
  2. Para cada lote da planilha, cria StockLote + StockMovement de entrada
  3. Lotes com quantidade 0 são criados mas sem movimento (saldo zero mesmo)
"""

import re
import os
import sys

# ── garante que os models são importados na ordem certa ──────────────────────
import models.base  # noqa: F401
import models.client  # noqa: F401
import models.tratamento  # noqa: F401
import models.schedule  # noqa: F401
import models.sale  # noqa: F401
import models.stock  # noqa: F401

from models.stock import Product, StockLote, StockMovement
from models.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://clinica:clinica123@db:5432/clinicadb"
)

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
db = Session()

# ── dados da planilha ────────────────────────────────────────────────────────
PRODUTOS = [
    {"nome": "5 HTP 10mg",                      "categoria": "injetavel",   "lotes": "Lote 18084: 24.0"},
    {"nome": "ADEK 300 000UI",                   "categoria": "injetavel",   "lotes": "Lote 18560: 10.0, Lote 18028: 5.0"},
    {"nome": "ADEK 600 000UI",                   "categoria": "injetavel",   "lotes": "Lote 18560: 10.0, Lote 18028: 5.0"},
    {"nome": "Agulha 18G",                        "categoria": "descartavel", "lotes": "Lote AGL005V: 0.0, Lote 240810: 0.0, Lote 241110: 184.0"},
    {"nome": "Agulha 22G",                        "categoria": "descartavel", "lotes": "Lote 20240603: 10.0, Lote 241111: 100.0"},
    {"nome": "Agulha 26G",                        "categoria": "descartavel", "lotes": ""},
    {"nome": "Agulha 30G",                        "categoria": "descartavel", "lotes": "Lote 5072899: 6.0"},
    {"nome": "Algodão",                           "categoria": "descartavel", "lotes": ""},
    {"nome": "Citrus booster 3ml",                "categoria": "injetavel",   "lotes": "Lote 17657: 2.0"},
    {"nome": "Creme de massagem REDUXCELL",       "categoria": "outro",       "lotes": "Lote 061556: 0.0, Lote 063382: 7.0"},
    {"nome": "Cânula 20G",                        "categoria": "descartavel", "lotes": ""},
    {"nome": "Cânula 22G",                        "categoria": "descartavel", "lotes": ""},
    {"nome": "Descarpak 7l",                      "categoria": "descartavel", "lotes": ""},
    {"nome": "Emoliente",                         "categoria": "outro",       "lotes": ""},
    {"nome": "Equipo",                            "categoria": "descartavel", "lotes": "Lote 250805: 14.0, Lote 250701A: 0.0"},
    {"nome": "Esfoliação",                        "categoria": "outro",       "lotes": ""},
    {"nome": "Filtro solar",                      "categoria": "outro",       "lotes": ""},
    {"nome": "Filtro solar antioleosidade",       "categoria": "outro",       "lotes": ""},
    {"nome": "Gaze",                              "categoria": "descartavel", "lotes": ""},
    {"nome": "Gel condutor 1kg",                  "categoria": "descartavel", "lotes": ""},
    {"nome": "Gel de limpeza",                    "categoria": "outro",       "lotes": ""},
    {"nome": "Hipertonic redux",                  "categoria": "descartavel", "lotes": ""},
    {"nome": "Metilcobalamina 2500 mcg",          "categoria": "injetavel",   "lotes": "Lote 18168: 9.0"},
    {"nome": "Máscara Beta Calm",                 "categoria": "outro",       "lotes": ""},
    {"nome": "Máscara de Argila",                 "categoria": "outro",       "lotes": ""},
    {"nome": "Máscara de Ouro",                   "categoria": "outro",       "lotes": ""},
    {"nome": "Máscara de Vit.C",                  "categoria": "outro",       "lotes": ""},
    {"nome": "Máscara facial compressiva",        "categoria": "descartavel", "lotes": ""},
    {"nome": "Nano XR",                           "categoria": "outro",       "lotes": ""},
    {"nome": "PDRN",                              "categoria": "outro",       "lotes": ""},
    {"nome": "Reduxcel",                          "categoria": "descartavel", "lotes": ""},
    {"nome": "Reduxcel Thermo",                   "categoria": "outro",       "lotes": ""},
    {"nome": "Scalp 21G",                         "categoria": "descartavel", "lotes": "Lote 20240105: 67.0, Lote 241117: 0.0"},
    {"nome": "Scalp 23G",                         "categoria": "descartavel", "lotes": ""},
    {"nome": "Scalp 25G",                         "categoria": "descartavel", "lotes": ""},
    {"nome": "Seringa 10ml",                      "categoria": "descartavel", "lotes": "Lote SSLAB 0165: 61.0"},
    {"nome": "Seringa 3ml",                       "categoria": "descartavel", "lotes": "Lote 25/33: 70.0"},
    {"nome": "Seringa 5ml",                       "categoria": "descartavel", "lotes": "Lote SSLLAB0063: 25.0"},
    {"nome": "Seringa insulina",                  "categoria": "descartavel", "lotes": "Lote C24460: 124.0, Lote C26402: 98.0"},
    {"nome": "Soro de 100ml",                     "categoria": "injetavel",   "lotes": "Lote m008526A: 4.0"},
    {"nome": "Soro de 250ml",                     "categoria": "injetavel",   "lotes": "Lote M057726: 12.0, Lote M149326: 28.0"},
    {"nome": "Soro de 500ml",                     "categoria": "injetavel",   "lotes": "Lote 197062: 1.0"},
    {"nome": "Tirzepatida 2,5mg",                 "categoria": "injetavel",   "lotes": ""},
    {"nome": "Tirzepatida 5mg",                   "categoria": "injetavel",   "lotes": ""},
    {"nome": "Tirzepatida 60mg",                  "categoria": "injetavel",   "lotes": "Lote 1048: 24.0"},
    {"nome": "atp 20mg",                          "categoria": "injetavel",   "lotes": "Lote 17256: 9.0"},
    {"nome": "azul de metileno 2ml",              "categoria": "injetavel",   "lotes": "Lote 17488: 5.0"},
    {"nome": "bcaa 30mg",                         "categoria": "injetavel",   "lotes": "Lote 001-16525: 5.0"},
    {"nome": "bioestimulador de colageno holtec", "categoria": "injetavel",   "lotes": "Lote 0697: 4.0"},
    {"nome": "cafeina 100mg",                     "categoria": "injetavel",   "lotes": "Lote 17765: 17.0"},
    {"nome": "coezima q10 100mg",                 "categoria": "injetavel",   "lotes": "Lote 17538: 4.0, Lote 18337: 13.0"},
    {"nome": "complexo B",                        "categoria": "injetavel",   "lotes": "Lote 18022: 17.0"},
    {"nome": "complexo B sem b1 85mg",            "categoria": "injetavel",   "lotes": "Lote 18022: 17.0"},
    {"nome": "d-ribose 750mg",                    "categoria": "injetavel",   "lotes": "Lote 17415: 15.0"},
    {"nome": "flacidez",                          "categoria": "injetavel",   "lotes": "Lote 0726: 6.0"},
    {"nome": "flacidez corporal",                 "categoria": "injetavel",   "lotes": "Lote 001-16154: 9.0"},
    {"nome": "glicose + lidocaina",               "categoria": "injetavel",   "lotes": ""},
    {"nome": "glicose",                           "categoria": "injetavel",   "lotes": "Lote 0759: 20.0"},
    {"nome": "l glutamina 120mg",                 "categoria": "injetavel",   "lotes": "Lote 18856: 0.0"},
    {"nome": "l glutamina 150mg",                 "categoria": "injetavel",   "lotes": "Lote 001-16488: 11.0, Lote 17994: 10.0"},
    {"nome": "hmb 50mg",                          "categoria": "injetavel",   "lotes": ""},
    {"nome": "htp 10mg",                          "categoria": "injetavel",   "lotes": ""},
    {"nome": "inositol+taurina 2ml",              "categoria": "injetavel",   "lotes": "Lote 17692: 12.0"},
    {"nome": "l fenilalanina 50mg",               "categoria": "injetavel",   "lotes": "Lote 001-16420: 9.0, Lote 18487: 10.0"},
    {"nome": "l gluthation 1g",                   "categoria": "injetavel",   "lotes": "Lote 17761: 32.0"},
    {"nome": "l theanina 50mg",                   "categoria": "injetavel",   "lotes": "Lote 18104: 10.0, Lote 001-16361: 10.0"},
    {"nome": "l carnitina 600mg",                 "categoria": "injetavel",   "lotes": "Lote 17585: 35.0"},
    {"nome": "lidocaina 10ml",                    "categoria": "injetavel",   "lotes": "Lote 001-16504: 7.0"},
    {"nome": "light 1",                           "categoria": "injetavel",   "lotes": "Lote 001-16681: 6.0"},
    {"nome": "light 2",                           "categoria": "injetavel",   "lotes": "Lote 001-16652: 10.0"},
    {"nome": "metilcobalamina 25mg",              "categoria": "injetavel",   "lotes": "Lote 17559: 3.0, Lote 18047: 5.0, Lote 18052: 10.0"},
    {"nome": "metilfolato 3,5mg",                 "categoria": "injetavel",   "lotes": ""},
    {"nome": "n - acetilcisteina 300mg",          "categoria": "injetavel",   "lotes": "Lote 18467: 9.0, Lote 18188: 15.0"},
    {"nome": "noripurum 5ml",                     "categoria": "injetavel",   "lotes": "Lote 5172126BA: 9.0, Lote 5210126AA: 6.0"},
    {"nome": "picolinato de cromo 100mcg",        "categoria": "injetavel",   "lotes": "Lote 18093: 20.0"},
    {"nome": "picolinato de cromo 200mcg",        "categoria": "injetavel",   "lotes": ""},
    {"nome": "pool capilar 130mg",                "categoria": "injetavel",   "lotes": "Lote 18147: 7.0, Lote 18283: 9.0"},
    {"nome": "pool de aminoacidos farmatec",      "categoria": "injetavel",   "lotes": "Lote 17734: 13.0"},
    {"nome": "power 1",                           "categoria": "injetavel",   "lotes": "Lote 001-16305: 6.0"},
    {"nome": "pqq 5mg",                           "categoria": "injetavel",   "lotes": "Lote 17086: 11.0"},
    {"nome": "pump gluteo",                       "categoria": "injetavel",   "lotes": "Lote 001-16310: 4.0"},
    {"nome": "redutor de culote",                 "categoria": "injetavel",   "lotes": "Lote 001-16719: 10.0"},
    {"nome": "redux holtec",                      "categoria": "injetavel",   "lotes": "Lote 0795: 5.0"},
    {"nome": "selenio 80mcg",                     "categoria": "injetavel",   "lotes": "Lote 17881: 16.0"},
    {"nome": "silicio 20mg",                      "categoria": "injetavel",   "lotes": "Lote 17824: 20.0"},
    {"nome": "sulfato de magnesio 1G",            "categoria": "injetavel",   "lotes": "Lote 17955: 6.0"},
    {"nome": "sulfato de magnesio 500mg",         "categoria": "injetavel",   "lotes": "Lote 18204: 1.0"},
    {"nome": "sulfato de zinco 20mg",             "categoria": "injetavel",   "lotes": "Lote 18321: 11.0"},
    {"nome": "vit c (ac ascorbico) 1G",           "categoria": "injetavel",   "lotes": "Lote 17961: 16.0"},
    {"nome": "vitamina c",                        "categoria": "injetavel",   "lotes": "Lote 17978: 7.0"},
    {"nome": "acido alfa lipoico 300mg",          "categoria": "injetavel",   "lotes": "Lote 17829: 17.0"},
]


def parse_lotes(lotes_str: str):
    """Retorna lista de (codigo_lote, quantidade)."""
    if not lotes_str or not lotes_str.strip():
        return []
    partes = lotes_str.split(",")
    resultado = []
    for p in partes:
        p = p.strip()
        m = re.match(r"Lote\s+(.+?):\s*([\d.]+)", p)
        if m:
            codigo = m.group(1).strip()
            qtd = float(m.group(2))
            resultado.append((codigo, qtd))
    return resultado


def main():
    criados = 0
    ignorados = 0
    lotes_criados = 0

    for item in PRODUTOS:
        nome = item["nome"].strip()
        categoria = item["categoria"]
        lotes_str = item.get("lotes", "")

        # upsert produto
        produto = db.query(Product).filter(Product.nome == nome).first()
        if not produto:
            produto = Product(nome=nome, categoria=categoria)
            db.add(produto)
            db.flush()
            criados += 1
            print(f"  [+] Produto criado: {nome}")
        else:
            ignorados += 1
            print(f"  [=] Produto já existe: {nome}")

        # lotes
        lotes_parsed = parse_lotes(lotes_str)
        if not lotes_parsed:
            # cria um lote vazio para o produto aparecer no estoque
            lote_existente = db.query(StockLote).filter(
                StockLote.produto_id == produto.id
            ).first()
            if not lote_existente:
                lote = StockLote(
                    produto_id=produto.id,
                    lote=None,
                    quantidade_atual=0.0,
                    quantidade_minima=5.0,
                )
                db.add(lote)
                db.flush()
                lotes_criados += 1
        else:
            for codigo, qtd in lotes_parsed:
                # evita duplicar lote pelo código
                lote_existente = db.query(StockLote).filter(
                    StockLote.produto_id == produto.id,
                    StockLote.lote == codigo,
                ).first()
                if lote_existente:
                    continue
                lote = StockLote(
                    produto_id=produto.id,
                    lote=codigo,
                    quantidade_atual=qtd,
                    quantidade_minima=5.0,
                )
                db.add(lote)
                db.flush()
                lotes_criados += 1

                if qtd > 0:
                    mov = StockMovement(
                        lote_id=lote.id,
                        produto_id=produto.id,
                        tipo="entrada",
                        quantidade=qtd,
                        motivo="importacao inicial planilha",
                    )
                    db.add(mov)

    db.commit()
    print(f"\nProntos! Produtos criados: {criados} | Já existiam: {ignorados} | Lotes criados: {lotes_criados}")


if __name__ == "__main__":
    main()
