from sqlalchemy import Column, Integer, String, Date, Float, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from models.base import Base


class Sale(Base):
    __tablename__ = "vendas"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False, index=True)
    data_venda = Column(Date, nullable=False)
    forma_pagamento = Column(String, nullable=False)
    valor_total = Column(Float, nullable=False, default=0.0)
    observacoes = Column(Text, nullable=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())

    cliente = relationship("Client", foreign_keys=[cliente_id])
    itens = relationship("SaleItem", back_populates="venda", cascade="all, delete-orphan")


class SaleItem(Base):
    __tablename__ = "venda_itens"

    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey("vendas.id"), nullable=False, index=True)
    procedimento = Column(String, nullable=False)
    tipo = Column(String, nullable=False, default="unitario")  # "unitario" | "pacote"
    sessoes_total = Column(Integer, nullable=False, default=1)
    sessoes_usadas = Column(Integer, nullable=False, default=0)
    valor = Column(Float, nullable=False, default=0.0)

    venda = relationship("Sale", back_populates="itens")
    usos = relationship("SessionUsage", back_populates="item", cascade="all, delete-orphan")

    @property
    def sessoes_restantes(self):
        return self.sessoes_total - self.sessoes_usadas


class SessionUsage(Base):
    __tablename__ = "sessao_uso"

    id = Column(Integer, primary_key=True, index=True)
    sale_item_id = Column(Integer, ForeignKey("venda_itens.id"), nullable=False, index=True)
    agendamento_id = Column(Integer, ForeignKey("agenda.id"), nullable=True)
    data_uso = Column(Date, nullable=False)

    item = relationship("SaleItem", back_populates="usos")
