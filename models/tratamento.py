from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from models.base import Base


class Tratamento(Base):
    __tablename__ = "tratamentos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(200), nullable=False)
    descricao = Column(Text, nullable=True)
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.now)
