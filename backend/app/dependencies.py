from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from bson import ObjectId
from database import db
from models.user_model import User, RoleEnum
from auth import SECRET_KEY, ALGORITHM

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Token invalide")
        user_doc = await db["users"].find_one({"_id": ObjectId(user_id)})
        if user_doc is None:
            raise HTTPException(status_code=401, detail="Utilisateur non trouvé")
        user_doc["id"] = str(user_doc["_id"])
        return User(**user_doc)
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Token invalide")

async def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Accès refusé: admin requis")
    return current_user

async def require_employer(current_user: User = Depends(get_current_user)):
    if current_user.role != RoleEnum.employer or not current_user.is_active:
        raise HTTPException(status_code=403, detail="Accès refusé: compte non activé ou rôle incorrect")
    return current_user