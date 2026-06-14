from pydantic import BaseModel, EmailStr
from enum import Enum
from datetime import datetime
from typing import Optional

class RoleEnum(str, Enum):
    admin = "admin"
    analyste = "analyste"

class User(BaseModel):
    id: Optional[str]  # MongoDB ObjectId en string
    email: EmailStr
    password: str
    role: RoleEnum = RoleEnum.analyste
    is_active: bool = False  # activation par admin
    # --- MFA / Security ---
    otp_code: Optional[str] = None
    otp_expires_at: Optional[datetime] = None