from sqlalchemy import Column, Integer, String, DateTime, func
from models.base import Base


class Room(Base):
    __tablename__ = "salas"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False, unique=True)
    cor = Column(String, nullable=True, default="#E3A5C7")
    # Calendário do Google Calendar que representa esta sala
    google_calendar_id = Column(String, nullable=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())
