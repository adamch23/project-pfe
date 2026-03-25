from pydantic import BaseModel, EmailStr
from enum import Enum
from typing import Optional

# -------------------------
# Rôles utilisateur
# -------------------------
class RoleEnum(str, Enum):
    admin = "admin"
    employer = "employer"

# -------------------------
# Création d'utilisateur
# -------------------------
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: RoleEnum = RoleEnum.employer

# -------------------------
# Utilisateur retourné
# -------------------------
class UserOut(BaseModel):
    id: Optional[str]
    email: EmailStr
    role: RoleEnum
    is_active: bool

    class Config:
        from_attributes = True

# -------------------------
# Login
# -------------------------
class LoginSchema(BaseModel):
    email: EmailStr
    password: str

# -------------------------
# Token JWT
# -------------------------
class Token(BaseModel):
    access_token: str
    token_type: str

# -------------------------
# Forgot Password
# -------------------------
class ForgotPasswordSchema(BaseModel):
    email: EmailStr

# -------------------------
# Reset Password
# -------------------------
class ResetPasswordSchema(BaseModel):
    email: EmailStr
    code: str
    new_password: str