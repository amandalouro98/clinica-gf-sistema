from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from models.base import Base


class Material(Base):
    __tablename__ = "materiais"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(200), nullable=False)
    tipo = Column(String(50), nullable=False)  # "Injetável" ou "Descartável"
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.now)
