from sqlalchemy import Column, Integer, ForeignKey, Text, DateTime, func
from sqlalchemy.orm import relationship
from models.base import Base

class Assessment(Base):
    __tablename__ = "avaliacoes"
    id = Column(Integer, primary_key=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False, index=True)
    queixa_detalhada = Column(Text, nullable=True)
    objetivo_tratamento = Column(Text, nullable=True)
    avaliacao_inicial = Column(Text, nullable=True)
    indicacao_protocolo = Column(Text, nullable=True)
    receituario = Column(Text, nullable=True)
    observacoes_profissionais = Column(Text, nullable=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())

    cliente = relationship("Client")
