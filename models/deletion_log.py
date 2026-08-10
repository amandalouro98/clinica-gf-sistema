from sqlalchemy import Column, Integer, String, Text, DateTime, func
from models.base import Base


class RegistroExclusao(Base):
    """Registro (lixeira) de tudo que foi excluído no sistema.

    Guarda um snapshot em JSON do que foi apagado para consulta/auditoria interna.
    """
    __tablename__ = "registros_exclusao"

    id = Column(Integer, primary_key=True)
    tipo = Column(String, nullable=False)          # ex: "atendimento", "produto", "lote"
    referencia_id = Column(Integer, nullable=True) # id original do registro apagado
    descricao = Column(String, nullable=True)      # resumo legível (nome cliente, data, etc)
    dados_json = Column(Text, nullable=True)       # snapshot completo em JSON
    excluido_por = Column(String, nullable=True)   # nome do usuário que excluiu
    excluido_em = Column(DateTime(timezone=True), server_default=func.now())
