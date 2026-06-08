from sqlalchemy import Column, Integer, ForeignKey, Float, Date, DateTime, func
from sqlalchemy.orm import relationship
from models.base import Base

class Biometrics(Base):
    __tablename__ = "medidas_biometricas"
    id = Column(Integer, primary_key=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    data_medicao = Column(Date, nullable=False)
    peso = Column(Float, nullable=True)
    cintura = Column(Float, nullable=True)
    abdomen = Column(Float, nullable=True)
    abdomen_superior = Column(Float, nullable=True)
    abdomen_inferior = Column(Float, nullable=True)
    quadril = Column(Float, nullable=True)
    braco = Column(Float, nullable=True)
    braco_e = Column(Float, nullable=True)
    braco_d = Column(Float, nullable=True)
    coxa = Column(Float, nullable=True)
    coxa_e = Column(Float, nullable=True)
    coxa_d = Column(Float, nullable=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())

    cliente = relationship("Client")
