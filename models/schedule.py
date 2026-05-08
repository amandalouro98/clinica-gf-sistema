from sqlalchemy import Column, Integer, String, Date, Text, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from models.base import Base


class ScheduledAppointment(Base):
    __tablename__ = "agenda"

    id = Column(Integer, primary_key=True, index=True)
    data = Column(Date, nullable=False, index=True)
    hora_inicio = Column(String, nullable=False)   # "HH:MM"
    hora_fim = Column(String, nullable=False)       # calculado
    duracao_min = Column(Integer, nullable=False, default=60)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    cliente_nome = Column(String, nullable=True)
    profissional = Column(String, nullable=False)
    procedimento = Column(String, nullable=True)
    observacoes = Column(Text, nullable=True)
    confirmado = Column(Boolean, default=False)
    cor_profissional = Column(String, nullable=True, default="#E3A5C7")
    sala = Column(String, nullable=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())

    cliente = relationship("Client", foreign_keys=[cliente_id])
