from pydantic import BaseModel, EmailStr
from enum import Enum
from typing import Optional

class RoleEnum(str, Enum):
    admin = "admin"
    employer = "employer"

class User(BaseModel):
    id: Optional[str]  # MongoDB ObjectId en string
    email: EmailStr
    password: str
    role: RoleEnum = RoleEnum.employer
    is_active: bool = False  # activation par admin