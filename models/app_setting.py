from sqlalchemy import Column, String, Text

from models.base import Base


class AppSetting(Base):
    """Configurações internas do app (chave/valor).

    Hoje guarda a chave secreta que assina o cookie de login persistente —
    fica no banco, então sobrevive a rebuilds do container.
    """
    __tablename__ = "app_settings"

    chave = Column(String, primary_key=True, index=True)
    valor = Column(Text, nullable=True)
