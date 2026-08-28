import os
import sys
import re
import unicodedata
from datetime import date

import pandas as pd
from sqlalchemy.orm import Session

# Adiciona o diretório do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.db import SessionLocal
from models.client import Client
from models.sale import Sale, SaleItem


def _normalizar(texto: str) -> str:
    texto = (texto or "").strip().lower()
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def _parse_sessao_atual(valor, total):
    """Interpreta 'sessão atual' como fração ou fração textual."""
    if valor is None or pd.isna(valor):
        return 0

    texto = str(valor).strip().replace(",", ".")

    # Formato "4/4." ou "7/10."
    m = re.match(r"^(\d+)\s*/\s*(\d+)\.?\s*$", texto)
    if m:
        return int(m.group(1))

    # Número decimal entre 0 e 1
    try:
        numero = float(texto)
        if 0 <= numero <= 1:
            return round(numero * total)
        return int(numero)
    except ValueError:
        return 0


def importar_pacotes(caminho_xlsx: str, data_compra: date = None, limpar_antigos: bool = True, dry_run: bool = False):
    data_compra = data_compra or date.today()

    df = pd.read_excel(caminho_xlsx)
    df.columns = [c.strip() for c in df.columns]

    db = SessionLocal()
    try:
        if limpar_antigos:
            antigos = db.query(SaleItem).filter(SaleItem.tipo == "pacote").all()
            if dry_run:
                print(f"[DRY-RUN] Limparia {len(antigos)} pacote(s) antigo(s).")
            else:
                for item in antigos:
                    if item.venda:
                        db.delete(item.venda)
                    else:
                        db.delete(item)
                db.commit()
                print(f"[LIMPO] {len(antigos)} pacote(s) antigo(s) removido(s).")

        clientes = db.query(Client).all()
        mapa_clientes = {}
        for c in clientes:
            chave = _normalizar(c.nome)
            mapa_clientes[chave] = c

        importados = 0
        ignorados = 0
        nao_encontrados = []

        for _, row in df.iterrows():
            nome_raw = str(row.get("Paciente", "")).strip()
            procedimento = str(row.get("Procedimento", "")).strip()
            total = int(row.get("Pacote", 0) or 0)
            sessao_atual = row.get("sessão atual", 0)
            usadas = _parse_sessao_atual(sessao_atual, total)

            if not nome_raw or not procedimento or total <= 0:
                ignorados += 1
                continue

            cliente = mapa_clientes.get(_normalizar(nome_raw))
            if not cliente:
                # Tentar busca parcial
                nome_norm = _normalizar(nome_raw)
                for c in clientes:
                    if nome_norm in _normalizar(c.nome) or _normalizar(c.nome) in nome_norm:
                        cliente = c
                        break

            if not cliente:
                nao_encontrados.append(nome_raw)
                continue

            sale = Sale(
                cliente_id=cliente.id,
                data_venda=data_compra,
                forma_pagamento="Não informado",
                valor_total=0.0,
                observacoes="Importado da planilha Pacotes agosto26.xlsx",
            )
            db.add(sale)
            db.flush()

            item = SaleItem(
                sale_id=sale.id,
                procedimento=procedimento,
                tipo="pacote",
                sessoes_total=total,
                sessoes_usadas=usadas,
                valor=0.0,
                data_inicio=data_compra,
            )
            db.add(item)
            if not dry_run:
                db.commit()

            importados += 1
            print(f"[IMPORTADO] {cliente.nome} - {procedimento} | {usadas}/{total}")

        print("\nResumo:")
        print(f"Importados: {importados}")
        print(f"Ignorados: {ignorados}")
        if nao_encontrados:
            print(f"Clientes não encontrados ({len(nao_encontrados)}):")
            for nome in nao_encontrados:
                print(f"  - {nome}")
        print(f"\nTotal no banco após importação: {db.query(SaleItem).filter(SaleItem.tipo == 'pacote').count()} pacotes")
    except Exception as e:
        db.rollback()
        print(f"\n[ERRO] Importação cancelada: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    caminho = sys.argv[1] if len(sys.argv) > 1 else "/opt/Pacotes agosto26.xlsx"
    dry_run = "--dry-run" in sys.argv
    importar_pacotes(caminho, limpar_antigos=True, dry_run=dry_run)
