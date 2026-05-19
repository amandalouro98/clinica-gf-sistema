from datetime import date, timedelta
from sqlalchemy import func
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
    """Retorna produtos com saldo total baixo (<=5) e lotes com validade próxima."""
    db = SessionLocal()
    try:
        hoje = date.today()
        limite = hoje + timedelta(days=30)
        
        # Calcular saldo total por produto (soma de todos os lotes)
        produtos_baixo = []
        produtos = db.query(Product).all()
        
        for prod in produtos:
            # Soma quantidade_atual de todos os lotes deste produto
            saldo_total = db.query(func.sum(StockLote.quantidade_atual)).filter(
                StockLote.produto_id == prod.id
            ).scalar() or 0
            
            if 0 < saldo_total <= 5:
                produtos_baixo.append(prod)
        
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
