from sqlalchemy import Column, Integer, String, Date, Float, Boolean, Text, DateTime
from models.base import Base


class FormResposta(Base):
    """Resposta do formulário público de pré-avaliação (link ?form=pre_avaliacao)."""
    __tablename__ = "form_respostas"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False, index=True)
    cpf = Column(String, nullable=True)
    data_nascimento = Column(Date, nullable=True)
    telefone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    profissao = Column(String, nullable=True)
    endereco = Column(String, nullable=True)
    bairro = Column(String, nullable=True)
    cidade = Column(String, nullable=True)

    peso = Column(Float, nullable=True)
    altura = Column(Float, nullable=True)
    queixa_principal = Column(Text, nullable=True)
    exames_recentes = Column(Text, nullable=True)
    funcionamento_intestinal = Column(String, nullable=True)
    uso_vitaminas = Column(String, nullable=True)
    marcacao_corporal = Column(Text, nullable=True)

    neoplasia = Column(Boolean, default=False)
    epilepsia = Column(Boolean, default=False)
    outras_condicoes = Column(Text, nullable=True)

    termo_aceite = Column(Boolean, default=False)
    status = Column(String, default="novo", index=True)  # novo | importado
    criado_em = Column(DateTime, nullable=True)
