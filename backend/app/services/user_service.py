from fastapi import HTTPException
from bson import ObjectId
from datetime import datetime, timedelta
import re
import base64

from models.user_model import RoleEnum
from auth import hash_password, verify_password, create_access_token
from database import db
from email_utils import generate_code, send_verification_code


# ================================================================
# HELPERS DE VALIDATION
# ================================================================

def validate_email_format(email: str):
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w{2,}$"
    if not re.match(pattern, email):
        raise HTTPException(status_code=422, detail="Format d'email invalide")


def validate_password_strength(password: str):
    errors = []
    if len(password) < 8:
        errors.append("au moins 8 caractères")
    if not re.search(r"[A-Z]", password):
        errors.append("au moins une lettre majuscule")
    if not re.search(r"[a-z]", password):
        errors.append("au moins une lettre minuscule")
    if not re.search(r"\d", password):
        errors.append("au moins un chiffre")
    if not re.search(r"[@$!%*?&._\-#]", password):
        errors.append("au moins un caractère spécial (@$!%*?&._-#)")
    if errors:
        raise HTTPException(
            status_code=422,
            detail=f"Mot de passe invalide — requis : {', '.join(errors)}"
        )


def validate_code_format(code: str):
    if not re.fullmatch(r"\d{6}", code.strip()):
        raise HTTPException(status_code=422, detail="Le code doit contenir exactement 6 chiffres")


def validate_name(value: str, field: str):
    if len(value.strip()) < 2:
        raise HTTPException(status_code=422, detail=f"{field} doit contenir au moins 2 caractères")
    if not re.match(r"^[a-zA-ZÀ-ÿ\s'\-]+$", value.strip()):
        raise HTTPException(status_code=422, detail=f"{field} ne doit contenir que des lettres")


# ================================================================
# SERVICE
# ================================================================

class UserService:
    def __init__(self):
        self.collection = db["users"]

    # ── Projection publique ──────────────────────────────────────
    def _format_user(self, user: dict, include_photo: bool = False) -> dict:
        result = {
            "id":         str(user["_id"]),
            "email":      user.get("email", ""),
            "role":       user.get("role", ""),
            "is_active":  user.get("is_active", False),
            "first_name": user.get("first_name", ""),
            "last_name":  user.get("last_name", ""),
            "has_face_photo": bool(user.get("face_photo")),
        }
        if include_photo:
            result["face_photo"] = user.get("face_photo", None)
        return result

    # -------------------------
    # SIGNUP
    # -------------------------
    async def signup(self, user_data):
        validate_email_format(user_data.email)
        validate_password_strength(user_data.password)

        existing = await self.collection.find_one({"email": user_data.email})
        if existing:
            raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")

        user_dict = user_data.dict()
        user_dict["password"]   = hash_password(user_dict["password"])
        user_dict["role"]       = RoleEnum.employer.value
        user_dict["is_active"]  = False
        user_dict.setdefault("first_name", "")
        user_dict.setdefault("last_name", "")
        user_dict["face_photo"] = None   # pas de photo au départ

        result = await self.collection.insert_one(user_dict)
        return self._format_user({**user_dict, "_id": result.inserted_id})

    # -------------------------
    # LOGIN
    # -------------------------
    async def login(self, email: str, password: str):
        if not email or not email.strip():
            raise HTTPException(status_code=422, detail="L'email est requis")
        if not password or not password.strip():
            raise HTTPException(status_code=422, detail="Le mot de passe est requis")

        validate_email_format(email)
        user = await self.collection.find_one({"email": email})

        if not user or not verify_password(password, user["password"]):
            raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

        if user["role"] == RoleEnum.employer.value and not user["is_active"]:
            raise HTTPException(
                status_code=403,
                detail="Votre compte est en attente d'activation par l'administrateur"
            )

        token = create_access_token({
            "sub":  str(user["_id"]),
            "role": user["role"]
        })

        return {
            "access_token":   token,
            "token_type":     "bearer",
            "has_face_photo": bool(user.get("face_photo")),
        }

    # -------------------------
    # GET USER BY ID
    # -------------------------
    async def get_user_by_id(self, user_id: str, include_photo: bool = False):
        if not ObjectId.is_valid(user_id):
            raise HTTPException(status_code=400, detail="ID invalide")
        user = await self.collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        return self._format_user(user, include_photo=include_photo)

    # -------------------------
    # GET MY PROFILE (with photo)
    # -------------------------
    async def get_my_profile(self, user_id: str):
        return await self.get_user_by_id(user_id, include_photo=True)

    # -------------------------
    # UPDATE MY PROFILE
    # -------------------------
    async def update_my_profile(self, user_id: str, data: dict):
        if not ObjectId.is_valid(user_id):
            raise HTTPException(status_code=400, detail="ID invalide")

        update_data = {}

        if "email" in data and data["email"]:
            validate_email_format(data["email"])
            existing = await self.collection.find_one({
                "email": data["email"],
                "_id": {"$ne": ObjectId(user_id)}
            })
            if existing:
                raise HTTPException(status_code=400, detail="Cet email est déjà utilisé par un autre compte")
            update_data["email"] = data["email"]

        if "first_name" in data and data["first_name"]:
            validate_name(data["first_name"], "Le prénom")
            update_data["first_name"] = data["first_name"].strip()

        if "last_name" in data and data["last_name"]:
            validate_name(data["last_name"], "Le nom")
            update_data["last_name"] = data["last_name"].strip()

        if not update_data:
            raise HTTPException(status_code=400, detail="Aucune donnée valide à mettre à jour")

        await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )
        return await self.get_user_by_id(user_id)

    # -------------------------
    # UPLOAD FACE PHOTO
    # -------------------------
    async def upload_face_photo(self, user_id: str, image_base64: str):
        """
        Stocke une photo de référence (base64) pour la reconnaissance faciale.
        Le frontend envoie directement du base64 (data:image/jpeg;base64,...)
        """
        if not ObjectId.is_valid(user_id):
            raise HTTPException(status_code=400, detail="ID invalide")

        # Vérification basique du format base64 image
        if not image_base64.startswith("data:image/"):
            raise HTTPException(
                status_code=422,
                detail="Format invalide — attendu : data:image/jpeg;base64,..."
            )

        # Limite de taille : ~5 Mo en base64
        if len(image_base64) > 7_000_000:
            raise HTTPException(status_code=413, detail="Image trop volumineuse (max ~5 Mo)")

        result = await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"face_photo": image_base64}}
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

        return {"message": "Photo de reconnaissance faciale enregistrée avec succès"}

    # -------------------------
    # DELETE FACE PHOTO
    # -------------------------
    async def delete_face_photo(self, user_id: str):
        if not ObjectId.is_valid(user_id):
            raise HTTPException(status_code=400, detail="ID invalide")

        await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$unset": {"face_photo": ""}}
        )
        return {"message": "Photo de reconnaissance faciale supprimée"}

    # -------------------------
    # CHANGE MY PASSWORD
    # -------------------------
    async def change_my_password(self, user_id: str, old_password: str, new_password: str):
        if not ObjectId.is_valid(user_id):
            raise HTTPException(status_code=400, detail="ID invalide")

        user = await self.collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

        if not verify_password(old_password, user["password"]):
            raise HTTPException(status_code=401, detail="Mot de passe actuel incorrect")

        if old_password == new_password:
            raise HTTPException(
                status_code=400,
                detail="Le nouveau mot de passe doit être différent de l'ancien"
            )

        validate_password_strength(new_password)
        await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"password": hash_password(new_password)}}
        )
        return {"message": "Mot de passe modifié avec succès"}

    # -------------------------
    # LIST USERS (ADMIN)
    # -------------------------
    async def list_users(self):
        users_cursor = self.collection.find()
        users = []
        async for user in users_cursor:
            users.append(self._format_user(user))
        return users

    # -------------------------
    # ACTIVATE / DEACTIVATE
    # -------------------------
    async def activate_user(self, user_id: str):
        if not ObjectId.is_valid(user_id):
            raise HTTPException(status_code=400, detail="ID invalide")
        result = await self.collection.update_one(
            {"_id": ObjectId(user_id)}, {"$set": {"is_active": True}}
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        return await self.get_user_by_id(user_id)

    async def deactivate_user(self, user_id: str):
        if not ObjectId.is_valid(user_id):
            raise HTTPException(status_code=400, detail="ID invalide")
        result = await self.collection.update_one(
            {"_id": ObjectId(user_id)}, {"$set": {"is_active": False}}
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        return await self.get_user_by_id(user_id)

    # -------------------------
    # UPDATE USER (ADMIN)
    # -------------------------
    async def update_user(self, user_id: str, data: dict):
        if not ObjectId.is_valid(user_id):
            raise HTTPException(status_code=400, detail="ID invalide")

        update_data = {}
        if "email" in data:
            validate_email_format(data["email"])
            update_data["email"] = data["email"]
        if "role" in data:
            if data["role"] not in [r.value for r in RoleEnum]:
                raise HTTPException(status_code=422, detail="Rôle invalide (admin ou employer)")
            update_data["role"] = data["role"]
        if "is_active" in data:
            update_data["is_active"] = data["is_active"]
        if "password" in data:
            validate_password_strength(data["password"])
            update_data["password"] = hash_password(data["password"])

        if not update_data:
            raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")

        result = await self.collection.update_one(
            {"_id": ObjectId(user_id)}, {"$set": update_data}
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé ou aucun changement")
        return await self.get_user_by_id(user_id)

    # -------------------------
    # UPDATE PASSWORD (ADMIN)
    # -------------------------
    async def update_password(self, user_id: str, new_password: str):
        if not ObjectId.is_valid(user_id):
            raise HTTPException(status_code=400, detail="ID invalide")
        if not new_password or not new_password.strip():
            raise HTTPException(status_code=422, detail="Le nouveau mot de passe est requis")
        validate_password_strength(new_password)
        result = await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"password": hash_password(new_password)}}
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        return {"message": "Mot de passe mis à jour avec succès"}

    # -------------------------
    # DELETE USER
    # -------------------------
    async def delete_user(self, user_id: str):
        if not ObjectId.is_valid(user_id):
            raise HTTPException(status_code=400, detail="ID invalide")
        result = await self.collection.delete_one({"_id": ObjectId(user_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        return {"message": "Utilisateur supprimé avec succès"}

    # -------------------------
    # CREATE USER BY ADMIN
    # -------------------------
    async def create_user_by_admin(self, data: dict):
        if "email" not in data or not data["email"].strip():
            raise HTTPException(status_code=422, detail="L'email est requis")
        if "password" not in data or not data["password"].strip():
            raise HTTPException(status_code=422, detail="Le mot de passe est requis")
        if "role" not in data or not data["role"].strip():
            raise HTTPException(status_code=422, detail="Le rôle est requis")

        validate_email_format(data["email"])
        validate_password_strength(data["password"])

        if data["role"] not in [r.value for r in RoleEnum]:
            raise HTTPException(status_code=422, detail="Rôle invalide (admin ou employer)")

        existing = await self.collection.find_one({"email": data["email"]})
        if existing:
            raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")

        user_dict = {
            "email":      data["email"],
            "password":   hash_password(data["password"]),
            "role":       data["role"],
            "is_active":  data.get("is_active", True),
            "first_name": data.get("first_name", ""),
            "last_name":  data.get("last_name", ""),
            "face_photo": None,
        }
        result = await self.collection.insert_one(user_dict)
        return self._format_user({**user_dict, "_id": result.inserted_id})

    # -------------------------
    # FORGOT PASSWORD
    # -------------------------
    async def forgot_password(self, email: str):
        if not email or not email.strip():
            raise HTTPException(status_code=422, detail="L'email est requis")
        validate_email_format(email)
        user = await self.collection.find_one({"email": email})
        if not user:
            raise HTTPException(status_code=404, detail="Aucun compte associé à cet email")

        code = generate_code()
        expiry = datetime.utcnow() + timedelta(minutes=15)
        await self.collection.update_one(
            {"email": email},
            {"$set": {"reset_code": code, "reset_code_expiry": expiry}}
        )
        await send_verification_code(email, code)
        return {"message": "Code de vérification envoyé par email (valable 15 minutes)"}

    # -------------------------
    # RESET PASSWORD
    # -------------------------
    async def reset_password(self, email: str, code: str, new_password: str):
        if not email or not email.strip():
            raise HTTPException(status_code=422, detail="L'email est requis")
        if not code or not code.strip():
            raise HTTPException(status_code=422, detail="Le code de vérification est requis")
        if not new_password or not new_password.strip():
            raise HTTPException(status_code=422, detail="Le nouveau mot de passe est requis")

        validate_email_format(email)
        validate_code_format(code)
        validate_password_strength(new_password)

        user = await self.collection.find_one({"email": email})
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        if user.get("reset_code") != code.strip():
            raise HTTPException(status_code=400, detail="Code de vérification incorrect")
        if datetime.utcnow() > user.get("reset_code_expiry"):
            raise HTTPException(status_code=400, detail="Code expiré — veuillez en demander un nouveau")

        await self.collection.update_one(
            {"email": email},
            {
                "$set":   {"password": hash_password(new_password)},
                "$unset": {"reset_code": "", "reset_code_expiry": ""}
            }
        )
        return {"message": "Mot de passe réinitialisé avec succès"}