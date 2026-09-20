import os
import hmac
import hashlib
import secrets
import time
from dotenv import load_dotenv
from utils.db import SessionLocal
from utils.security import hash_password, verify_password
from models.user import User

load_dotenv()

# ── Login persistente (cookie assinado) ────────────────────────────────────
# O Streamlit perde a sessão a cada F5 / nova aba no celular. Um cookie
# assinado com HMAC mantém o login por 30 dias sem expor a senha.
COOKIE_LOGIN = "gf_login"
LOGIN_DIAS = 30


def _chave_secreta():
    """Chave de assinatura dos tokens — criada uma vez e guardada no banco."""
    from models.app_setting import AppSetting
    db = SessionLocal()
    try:
        st_ = db.query(AppSetting).filter_by(chave="login_secret").first()
        if st_ and st_.valor:
            return st_.valor
        novo = secrets.token_hex(32)
        db.add(AppSetting(chave="login_secret", valor=novo))
        db.commit()
        return novo
    finally:
        db.close()


def gerar_token_login(user_id: int) -> str:
    """Token 'user_id.expira_em.assinatura' para manter o login no navegador."""
    secreto = _chave_secreta()
    expira = int(time.time()) + LOGIN_DIAS * 86400
    payload = f"{user_id}.{expira}"
    assinatura = hmac.new(
        secreto.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return f"{payload}.{assinatura}"


def validar_token_login(token: str):
    """Confere assinatura e validade; devolve o User ativo ou None."""
    if not token:
        return None
    try:
        user_id_s, expira_s, assinatura = token.split(".")
        user_id, expira = int(user_id_s), int(expira_s)
    except (ValueError, AttributeError):
        return None
    if expira < time.time():
        return None
    secreto = _chave_secreta()
    esperada = hmac.new(
        secreto.encode(), f"{user_id_s}.{expira_s}".encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(esperada, assinatura):
        return None
    db = SessionLocal()
    try:
        return db.query(User).filter_by(id=user_id, ativo=True).first()
    finally:
        db.close()


def seed_admin():
    db = SessionLocal()
    try:
        email = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@clinica.com")
        senha = os.getenv("DEFAULT_ADMIN_PASSWORD", "Admin@123")
        existe = db.query(User).filter_by(email=email).first()
        if not existe:
            admin = User(
                nome="Administrador",
                email=email,
                senha_hash=hash_password(senha),
                perfil="admin",
                ativo=True
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()

def seed_usuario_venda():
    """Cria o usuário de demonstração (vende o sistema sem expor dados reais).

    Ao logar, esse perfil enxerga o sistema rodando num banco de demonstração
    vazio e separado — ver utils/db.py.
    """
    db = SessionLocal()
    try:
        email = "teste@clinica.com"
        existe = db.query(User).filter_by(email=email).first()
        if not existe:
            venda = User(
                nome="Demonstração",
                email=email,
                senha_hash=hash_password("@Teste123"),
                perfil="venda",
                ativo=True
            )
            db.add(venda)
            db.commit()
    finally:
        db.close()


def authenticate(email: str, senha: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(email=email, ativo=True).first()
        if user and verify_password(senha, user.senha_hash):
            return user
        return None
    finally:
        db.close()
