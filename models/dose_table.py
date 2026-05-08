from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from models.base import Base


class DoseTable(Base):
    __tablename__ = "tabela_doses"

    id = Column(Integer, primary_key=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False, index=True)
    medicacao = Column(String, nullable=False)
    semana = Column(String, nullable=True)
    dose = Column(String, nullable=True)
    via = Column(String, nullable=True)
    peso = Column(Float, nullable=True)
    data_registro = Column(Date, nullable=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())

    cliente = relationship("Client", backref="doses")
