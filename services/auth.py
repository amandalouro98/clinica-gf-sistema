import os
from dotenv import load_dotenv
from utils.db import SessionLocal
from utils.security import hash_password, verify_password
from models.user import User

load_dotenv()

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

def authenticate(email: str, senha: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(email=email, ativo=True).first()
        if user and verify_password(senha, user.senha_hash):
            return user
        return None
    finally:
        db.close()
