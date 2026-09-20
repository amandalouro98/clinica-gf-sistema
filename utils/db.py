import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

def _default_db_url() -> str:
    r"""
    Retorna a URL padrão do SQLite em uma pasta gravável do usuário:
    %LOCALAPPDATA%\ClinicaGestao\db\database.db (Windows)
    Isso evita problemas de permissão quando o app estiver instalado em Program Files.
    """
    base_dir = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    data_dir = os.path.join(base_dir, "ClinicaGestao", "db")
    os.makedirs(data_dir, exist_ok=True)
    db_file = os.path.join(data_dir, "database.db")
    return f"sqlite:///{db_file}"

# 1) Tenta pegar do .env; 2) se não existir, usa o caminho seguro do usuário
DB_URL = os.getenv("DB_URL") or _default_db_url()

# Determina o tipo de banco pelo prefixo da URL
_is_sqlite = DB_URL.startswith("sqlite")

if _is_sqlite:
    # SQLite precisa de check_same_thread=False em apps de UI
    engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
else:
    # PostgreSQL não precisa de check_same_thread; pool_pre_ping verifica conexões ativas
    engine = create_engine(DB_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)

# Fábrica de sessões do banco REAL (abra/feche por request/tela)
_real_sessionmaker = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# ─────────────────────────────────────────────────────────────────────────────
# BANCO DE DEMONSTRAÇÃO (usuário de venda / teste@clinica.com)
#
# Banco separado (SQLite) usado APENAS quando o perfil "venda" está logado.
# Nenhum dado real é acessível nem alterado nesse modo. Scripts fora do
# Streamlit (importadores, sync) continuam sempre no banco real.
# ─────────────────────────────────────────────────────────────────────────────
_DEMO_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "demo_db.sqlite")
_demo_engine = create_engine(
    f"sqlite:///{os.path.abspath(_DEMO_DB_FILE)}",
    connect_args={"check_same_thread": False},
)
_demo_sessionmaker = sessionmaker(bind=_demo_engine, autoflush=False, autocommit=False)

_demo_preparado = False


def _importar_modelos():
    """Importa todos os módulos de models/ para registrar as tabelas no Base."""
    import importlib
    import pkgutil
    import models
    for _m in pkgutil.iter_modules(models.__path__):
        importlib.import_module(f"models.{_m.name}")


def _demo_ativo() -> bool:
    """True somente na sessão Streamlit do usuário de demonstração."""
    try:
        import streamlit as st
        return bool(st.session_state.get("db_demo"))
    except Exception:
        return False


def _garantir_demo_db():
    """Cria as tabelas do banco demo na primeira utilização (vazio)."""
    global _demo_preparado
    if _demo_preparado:
        return
    from models.base import Base
    _importar_modelos()
    Base.metadata.create_all(_demo_engine)
    _demo_preparado = True


def SessionLocal():
    """
    Fábrica de sessões: banco demo quando o usuário de venda está logado,
    banco real em todos os outros casos (inclusive scripts standalone).
    """
    if _demo_ativo():
        _garantir_demo_db()
        return _demo_sessionmaker()
    return _real_sessionmaker()


def resetar_demo_db():
    """Apaga e recria as tabelas do banco de demonstração (volta ao vazio)."""
    global _demo_preparado
    from models.base import Base
    _importar_modelos()
    Base.metadata.drop_all(_demo_engine)
    Base.metadata.create_all(_demo_engine)
    _demo_preparado = True
