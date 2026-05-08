from sqlalchemy import Column, Integer, String, Float, Date, DateTime, func, ForeignKey
from sqlalchemy.orm import relationship
from models.base import Base


class Product(Base):
    """Catálogo de produtos (sem lote/quantidade)."""
    __tablename__ = "produtos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False, index=True)
    categoria = Column(String, nullable=False, default="outro")  # descartavel, injetavel, outro
    criado_em = Column(DateTime(timezone=True), server_default=func.now())

    lotes = relationship("StockLote", back_populates="produto")


class StockLote(Base):
    """Cada entrada de compra = 1 lote de um produto."""
    __tablename__ = "estoque"

    id = Column(Integer, primary_key=True, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False, index=True)
    lote = Column(String, nullable=True)
    quantidade_atual = Column(Float, default=0.0)
    quantidade_minima = Column(Float, default=0.0)
    data_validade = Column(Date, nullable=True)
    fornecedor = Column(String, nullable=True)
    data_entrada = Column(Date, nullable=True)

    produto = relationship("Product", back_populates="lotes")
    movimentos = relationship("StockMovement", back_populates="lote")


class StockMovement(Base):
    __tablename__ = "movimentacoes_estoque"

    id = Column(Integer, primary_key=True, index=True)
    lote_id = Column(Integer, ForeignKey("estoque.id"), nullable=False, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=True)
    tipo = Column(String, nullable=False)       # entrada / saida
    quantidade = Column(Float, nullable=False)
    motivo = Column(String, nullable=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())

    lote = relationship("StockLote", back_populates="movimentos")
    produto = relationship("Product")
