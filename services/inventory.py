from datetime import date, timedelta
from sqlalchemy.orm import joinedload
from utils.db import SessionLocal
from models.stock import StockLote, StockMovement, Product


def movimentar(lote_id: int, tipo: str, quantidade: float, motivo: str = ""):
    """Registra entrada ou saída de estoque pelo ID do lote."""
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
        db.commit()
    finally:
        db.close()


def alertas():
    """Retorna lotes com estoque baixo (<=5) e lotes com validade nos próximos 30 dias."""
    db = SessionLocal()
    try:
        hoje = date.today()
        limite = hoje + timedelta(days=30)
        baixo = (
            db.query(StockLote)
            .options(joinedload(StockLote.produto))
            .filter(StockLote.quantidade_atual <= 5)
            .filter(StockLote.quantidade_atual > 0)
            .all()
        )
        validade = (
            db.query(StockLote)
            .options(joinedload(StockLote.produto))
            .filter(StockLote.data_validade != None)
            .filter(StockLote.data_validade <= limite)
            .all()
        )
        # Force load produto.nome while session is open
        for lt in baixo:
            _ = lt.produto.nome if lt.produto else None
        for lt in validade:
            _ = lt.produto.nome if lt.produto else None
        return baixo, validade
    finally:
        db.close()
