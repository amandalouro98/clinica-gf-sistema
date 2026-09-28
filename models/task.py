from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, func

from models.base import Base


class Task(Base):
    __tablename__ = "tarefas"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String(500), nullable=False)
    status = Column(String(30), nullable=False, default="A fazer", server_default="A fazer")
    responsavel_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    atualizado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (Index("ix_tarefas_status_criado", "status", "criado_em"),)
