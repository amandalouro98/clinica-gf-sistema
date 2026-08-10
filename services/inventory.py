from datetime import date, timedelta
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from utils.db import SessionLocal
from models.stock import StockLote, StockMovement, Product


def movimentar(lote_id: int, tipo: str, quantidade: float, motivo: str = "", db=None):
    """Registra entrada ou saída de estoque pelo ID do lote.

    Pode receber uma sessão aberta via `db` para executar dentro de uma transação
    já existente. Se não receber, cria uma sessão própria e fecha ao final.
    """
    own_session = db is None
    if own_session:
        db = SessionLocal()
    try:
        lote = db.get(StockLote, lote_id)
        if not lote:
            raise ValueError("Lote não encontrado.")
        if tipo == "saida" and (lote.quantidade_atual or 0) < quantidade:
            raise ValueError(f"Estoque insuficiente no lote '{lote.lote}'. Disponível: {lote.quantidade_atual}.")
        if tipo == "entrada":
            lote.quantidade_atual = (lote.quantidade_atual or 0) + quantidade
        else:
            lote.quantidade_atual = (lote.quantidade_atual or 0) - quantidade
        mov = StockMovement(
            lote_id=lote_id,
            produto_id=lote.produto_id,
            tipo=tipo,
            quantidade=quantidade,
            motivo=motivo,
        )
        db.add(mov)
        if own_session:
            db.commit()
    except Exception:
        if own_session:
            db.rollback()
        raise
    finally:
        if own_session:
            db.close()


def alertas():
    """Retorna produtos com saldo total baixo (<=5) e lotes com validade próxima."""
    db = SessionLocal()
    try:
        hoje = date.today()
        limite = hoje + timedelta(days=30)
        
        # Saldo total por produto em uma única query agregada
        saldos = dict(
            db.query(StockLote.produto_id, func.sum(StockLote.quantidade_atual))
            .group_by(StockLote.produto_id)
            .all()
        )
        # Buscar todos os produtos de uma vez
        produtos = {p.id: p for p in db.query(Product).all()}

        produtos_baixo = []
        for prod_id, saldo_total in saldos.items():
            saldo_total = float(saldo_total or 0)
            if 0 < saldo_total <= 5 and prod_id in produtos:
                produtos_baixo.append(produtos[prod_id])
        
        # Lotes com validade próxima (mantém igual)
        validade = (
            db.query(StockLote)
            .options(joinedload(StockLote.produto))
            .filter(StockLote.data_validade != None)
            .filter(StockLote.data_validade <= limite)
            .all()
        )
        
        return produtos_baixo, validade
    finally:
        db.close()
