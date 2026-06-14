import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReadPreference

logger = logging.getLogger(__name__)

# ── Configuration MongoDB (Finding ARCH-01 / ARCH-04 — Audit Bancaire) ──────
# Timeouts et pool configurés pour éviter les blocages en cas de lenteur DB.
# En production, MONGO_URL doit pointer vers le Replica Set :
#   mongodb://mongo1:27017,mongo2:27017,mongo3:27017/?replicaSet=rs0&authSource=admin
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "fastapi_mvc_db")

# ── Options de connexion robustes (circuit-breaker-like) ─────────────────────
MONGO_OPTIONS = {
    # Timeouts — Finding ARCH-04 : éviter les blocages indéfinis
    "serverSelectionTimeoutMS": 5000,       # Attente max pour trouver un serveur primaire
    "connectTimeoutMS": 3000,               # Timeout de connexion TCP
    "socketTimeoutMS": 30000,              # Timeout sur les opérations socket
    # Pool de connexions
    "maxPoolSize": 50,                     # Max connexions simultanées
    "minPoolSize": 5,                      # Min connexions maintenues
    "maxIdleTimeMS": 60000,               # Fermeture des connexions inactives après 60s
    # Résilience — Retry automatique des opérations (Finding ARCH-04)
    "retryWrites": True,
    "retryReads": True,
    # Haute disponibilité avec Replica Set (Finding ARCH-01)
    # En mode Replica Set, les lectures peuvent être distribuées sur les secondaires
    "readPreference": "primaryPreferred",   # Primary par défaut, secondary si primary down
    # Compression réseau
    "compressors": "zlib",
}

try:
    client = AsyncIOMotorClient(MONGO_URL, **MONGO_OPTIONS)
    db = client[DATABASE_NAME]
    logger.info(f"✅ MongoDB client initialisé — URL: {MONGO_URL.split('@')[-1]}, DB: {DATABASE_NAME}")
except Exception as e:
    logger.critical(f"🚨 CRITIQUE: Impossible d'initialiser le client MongoDB: {e}")
    raise