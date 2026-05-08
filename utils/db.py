import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

def _default_db_url() -> str:
    """
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

# Fábrica de sessões (abra/feche por request/tela)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
