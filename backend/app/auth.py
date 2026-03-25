from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import jwt, JWTError
from database import db
from models.user_model import RoleEnum

SECRET_KEY = "secret123"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_delta)
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token

def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

# =========================================
# Création automatique de l'admin par défaut
# =========================================
async def create_default_admin():
    admin_email = "admin@example.com"
    existing = await db["users"].find_one({"email": admin_email})
    if not existing:
        admin = {
            "email": admin_email,
            "password": hash_password("Admin1234@"),  # mot de passe par défaut
            "role": RoleEnum.admin.value,
            "is_active": True
        }
        await db["users"].insert_one(admin)
        print(f"✅ Admin créé : {admin_email} / Admin1234@")
    else:
        print(f"ℹ️ Admin déjà présent : {admin_email}")