from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func, UniqueConstraint
from models.base import Base


class GoogleToken(Base):
    """Autorização OAuth da conta Google da clínica (uma única linha)."""
    __tablename__ = "google_tokens"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=True)
    refresh_token = Column(Text, nullable=False)
    access_token = Column(Text, nullable=True)
    expira_em = Column(DateTime(timezone=True), nullable=True)
    atualizado_em = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class GoogleEvento(Base):
    """Vínculo entre um agendamento do sistema e um evento do Google Calendar.

    Um agendamento pode ter dois vínculos (calendário do profissional e da
    sala), espelhando a estrutura de calendários que a clínica já usava.
    """
    __tablename__ = "google_eventos"

    id = Column(Integer, primary_key=True, index=True)
    agendamento_id = Column(Integer, ForeignKey("agenda.id", ondelete="CASCADE"), nullable=False, index=True)
    calendar_id = Column(String, nullable=False, index=True)
    event_id = Column(String, nullable=False, index=True)
    hash_conteudo = Column(String, nullable=True)
    atualizado_em = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("calendar_id", "event_id", name="uq_google_evento"),
    )


class GoogleSyncState(Base):
    """Estado da sincronização incremental de cada calendário."""
    __tablename__ = "google_sync_state"

    id = Column(Integer, primary_key=True, index=True)
    calendar_id = Column(String, nullable=False, unique=True, index=True)
    sync_token = Column(Text, nullable=True)
    ultimo_sync = Column(DateTime(timezone=True), nullable=True)
