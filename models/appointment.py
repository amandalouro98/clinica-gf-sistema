from sqlalchemy import Column, Integer, ForeignKey, String, Text, Date, DateTime, func, Float
from sqlalchemy.orm import relationship
from models.base import Base


class Appointment(Base):
    __tablename__ = "atendimentos"

    id = Column(Integer, primary_key=True)
    data = Column(Date, nullable=False)
    mes = Column(String, nullable=False)  # yyyy-mm
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    queixa_consulta = Column(Text, nullable=True)
    protocolo_atendimento = Column(Text, nullable=True)
    tipo_tratamento = Column(String, nullable=True)
    retorno_indicado = Column(String, nullable=True)
    receituario = Column(Text, nullable=True)
    observacoes = Column(Text, nullable=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())

    cliente = relationship("Client")


class AppointmentMaterial(Base):
    __tablename__ = "atendimento_materiais"

    id = Column(Integer, primary_key=True)
    atendimento_id = Column(Integer, ForeignKey("atendimentos.id"), nullable=False)
    lote_id = Column(Integer, ForeignKey("estoque.id"), nullable=False)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=True)
    categoria = Column(String, nullable=True)
    quantidade = Column(Float, nullable=False)

    atendimento = relationship("Appointment")
    lote = relationship("StockLote")
    produto = relationship("Product")
