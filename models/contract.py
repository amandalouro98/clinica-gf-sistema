from sqlalchemy import Column, Integer, ForeignKey, String, Float, DateTime, func, Text
from sqlalchemy.orm import relationship
from models.base import Base

class Contract(Base):
    __tablename__ = "contratos"
    id = Column(Integer, primary_key=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    tipo_tratamento = Column(String, nullable=False)
    valor = Column(Float, nullable=False)
    forma_pagamento = Column(String, nullable=True)
    parcelamento = Column(String, nullable=True)
    assinatura_digital = Column(Text, nullable=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())

    cliente = relationship("Client")
