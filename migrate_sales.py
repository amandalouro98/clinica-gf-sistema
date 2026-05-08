"""
Cria as tabelas vendas, venda_itens e sessao_uso no banco existente.
Execute uma vez: python migrate_sales.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

# Importa todos os models para registrar no metadata
from models.base import Base
from models.user import User           # noqa
from models.client import Client       # noqa
from models.appointment import Appointment, AppointmentMaterial  # noqa
from models.biometrics import Biometrics  # noqa
from models.stock import Product, StockLote, StockMovement  # noqa
from models.contract import Contract   # noqa
from models.schedule import ScheduledAppointment  # noqa
from models.professional import Professional  # noqa
from models.assessment import Assessment  # noqa
from models.sale import Sale, SaleItem, SessionUsage  # noqa

from utils.db import engine

Base.metadata.create_all(bind=engine, tables=[
    Sale.__table__,
    SaleItem.__table__,
    SessionUsage.__table__,
])
print("Tabelas vendas / venda_itens / sessao_uso criadas com sucesso.")
