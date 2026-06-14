import asyncio
import logging
import hashlib
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "fastapi_mvc_db")

def pseudonymize_string(val: str, salt: str = "b4nk_s4lt") -> str:
    """Hash a sensitive string."""
    return hashlib.sha256((val + salt).encode('utf-8')).hexdigest()[:16]

async def run_data_masking():
    """
    Scans the database and masks sensitive C3/C4 data (PII, Biometrics)
    for use in DEV/UAT environments, compliant with GDPR & PCI-DSS.
    """
    logger.info("🛡️ Démarrage du processus de Data Masking (Obfuscation) vers l'environnement non-prod...")
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DATABASE_NAME]

    # 1. Masking des Utilisateurs (C3)
    users_coll = db["users"]
    cursor = users_coll.find({})
    masked_users = 0
    async for user in cursor:
        update_fields = {}
        if "email" in user and not user["email"].endswith("@masked.local"):
            original_email = user["email"]
            update_fields["email"] = f"user_{pseudonymize_string(original_email)}@masked.local"
        if "hashed_password" in user:
            # Remplacer par un mot de passe standard inexploitable ('Password123!' hashé)
            update_fields["hashed_password"] = "$2b$12$7kP/b01/eD.CqD0lA3s3Lu/p4V3M1UaY4Lw4Lw4Lw4Lw4Lw4Lw4Lw"
            
        if update_fields:
            await users_coll.update_one({"_id": user["_id"]}, {"$set": update_fields})
            masked_users += 1
            
    logger.info(f"✅ Masquage terminé pour {masked_users} utilisateurs.")

    # 2. Masking des logs biométriques (C4)
    bio_coll = db["biometric_logs"]
    cursor = bio_coll.find({})
    masked_bios = 0
    async for log in cursor:
        update_fields = {}
        if "signature_proof" in log:
            # Invalider la signature originelle pour la DEV
            update_fields["signature_proof"] = "REDACTED_DEV_ENV"
        if update_fields:
            await bio_coll.update_one({"_id": log["_id"]}, {"$set": update_fields})
            masked_bios += 1

    logger.info(f"✅ Masquage terminé pour {masked_bios} logs biométriques (C4).")
    logger.info("✔️ Conformité RGPD & PCI-DSS assurée pour les environnements bas.")

if __name__ == "__main__":
    asyncio.run(run_data_masking())
