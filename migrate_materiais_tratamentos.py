"""
migrate_materiais_tratamentos.py
Cria as tabelas 'materiais' e 'tratamentos' no banco de dados.
Execute: python migrate_materiais_tratamentos.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.db import engine
from models.base import Base
from models.material import Material
from models.tratamento import Tratamento

Base.metadata.create_all(bind=engine, tables=[Material.__table__, Tratamento.__table__])
print("Tabelas 'materiais' e 'tratamentos' criadas com sucesso!")
