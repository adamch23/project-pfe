import os
from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import jwt, JWTError
from database import db
from models.user_model import RoleEnum

from services.secret_manager import secret_manager

# ================================================================
# CONFIGURATION SÉCURISÉE RS256 (Asymétrique - Bank Grade)
# ================================================================
ALGORITHM = "RS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Chargement des clés via SecretManager (Vault-Ready)
RSA_PRIVATE_KEY = secret_manager.get_rsa_key("private")
RSA_PUBLIC_KEY = secret_manager.get_rsa_key("public")

if not RSA_PRIVATE_KEY or not RSA_PUBLIC_KEY:
    raise RuntimeError("🚨 CRITICAL: Clés RSA manquantes. Vérifiez le SecretManager.")

# Configuration des Cookies HttpOnly (Ajustée pour le Tunnel Cloudflare)
COOKIE_NAME = "access_token"
# Désactiver Secure en dev pour permettre localhost (Audit Bancaire)
COOKIE_SECURE = os.getenv("ENV", "dev").lower() == "prod"
COOKIE_SAMESITE = "lax"

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_delta)
    to_encode.update({"exp": expire})
    # Utilisation de la clé PRIVÉE pour signer
    token = jwt.encode(to_encode, RSA_PRIVATE_KEY, algorithm=ALGORITHM)
    return token

def decode_access_token(token: str) -> dict:
    try:
        # Utilisation de la clé PUBLIQUE pour vérifier
        payload = jwt.decode(token, RSA_PUBLIC_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

# =========================================
# Création automatique de l'admin par défaut
# =========================================
async def create_default_admin():
    """
    Crée l'admin uniquement si les credentials sont fournis via ENV.
    Évite les comptes 'backdoor' fixés dans le code source.
    """
    admin_email = os.getenv("DEFAULT_ADMIN_EMAIL")
    admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD")

    if not admin_email or not admin_password:
        print("ℹ️ DEFAULT_ADMIN_EMAIL/PASSWORD non définis. Pas de création automatique d'admin.")
        return

    existing = await db["users"].find_one({"email": admin_email})
    if not existing:
        admin = {
            "email": admin_email,
            "password": hash_password(admin_password),
            "role": RoleEnum.admin.value,
            "is_active": True
        }
        await db["users"].insert_one(admin)
        print(f"✅ Admin par défaut créé via variables d'environnement : {admin_email}")
    else:
        print(f"ℹ️ Admin déjà présent : {admin_email}")