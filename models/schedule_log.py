from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from models.base import Base


class AgendaLog(Base):
    __tablename__ = "agenda_log"

    id = Column(Integer, primary_key=True)
    agendamento_id = Column(Integer, ForeignKey("agenda.id", ondelete="SET NULL"), nullable=True)
    acao = Column(String, nullable=False)          # criado / editado / confirmado / excluido
    usuario_id = Column(Integer, nullable=True)
    usuario_nome = Column(String, nullable=True)
    dados_antes = Column(Text, nullable=True)      # JSON string
    dados_depois = Column(Text, nullable=True)     # JSON string
    criado_em = Column(DateTime(timezone=True), server_default=func.now())
