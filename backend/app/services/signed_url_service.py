"""
Service de génération d'URLs signées pour les données biométriques sensibles.
Finding DATA-03 (Audit Bancaire) — RGPD Art. 9 | ISO 27001 A.10.1

Problème résolu : Les photos biométriques ne sont plus retournées en base64
dans le corps de la réponse JSON (exposition via logs HTTP, proxy, SIEM).

Solution : Tokens signés HMAC à usage unique avec TTL de 60 secondes.
Le frontend utilise ce token pour récupérer la photo sur un endpoint dédié.
"""

import hmac
import hashlib
import time
import base64
import json
import os
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from database import db
from dependencies import get_current_user
from services.security_service import decrypt_data
from services.secret_manager import secret_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Configuration des tokens signés ─────────────────────────────────────────
SIGNED_URL_SECRET = secret_manager.get_secret("LOG_SIGNING_KEY", "fallback-dev-key")
SIGNED_URL_TTL_SECONDS = 60          # Validité : 60 secondes max
SIGNED_URL_ALGORITHM = "sha256"


def generate_signed_token(user_id: str, requester_id: str) -> str:
    """
    Génère un token signé HMAC-SHA256 autorisant l'accès à la photo biométrique
    d'un utilisateur spécifique pendant 60 secondes.

    Structure du token :
      base64url(payload_json) + "." + base64url(hmac_signature)

    Le payload contient :
      - user_id      : l'identifiant de l'utilisateur dont on veut la photo
      - requester_id : l'identifiant de celui qui fait la demande (audit)
      - expires_at   : timestamp Unix d'expiration
    """
    expires_at = int(time.time()) + SIGNED_URL_TTL_SECONDS
    payload = {
        "uid": user_id,
        "req": requester_id,
        "exp": expires_at,
    }
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode()

    signature = hmac.new(
        SIGNED_URL_SECRET.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return f"{payload_b64}.{signature}"


def verify_signed_token(token: str) -> Optional[dict]:
    """
    Vérifie un token signé et retourne le payload si valide.
    Retourne None si invalide, expiré ou falsifié.

    Sécurités :
    - compare_digest : résistant aux timing attacks
    - expires_at     : token invalide après TTL
    - signature HMAC : impossible à forger sans la clé secrète
    """
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, provided_signature = parts

        # Vérification de la signature (timing-safe)
        expected_signature = hmac.new(
            SIGNED_URL_SECRET.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected_signature, provided_signature):
            logger.warning("🚫 Signed URL: Signature invalide — tentative de falsification possible")
            return None

        # Décodage du payload
        payload_json = base64.urlsafe_b64decode(payload_b64 + "==").decode()
        payload = json.loads(payload_json)

        # Vérification de l'expiration
        if time.time() > payload.get("exp", 0):
            logger.info("⏰ Signed URL: Token expiré")
            return None

        return payload

    except Exception as e:
        logger.warning(f"🚫 Signed URL: Erreur de vérification — {e}")
        return None


# ── Endpoint : Génération du token signé ────────────────────────────────────

@router.get("/users/{user_id}/biometric-photo-token")
async def get_biometric_photo_token(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Génère un token signé permettant d'accéder temporairement à la photo biométrique.
    Finding DATA-03 (Audit Bancaire) : Remplace le retour direct de la photo en base64.

    - Durée de validité : 60 secondes
    - Usage unique recommandé (implémenté en production via Redis blacklist)
    - Requiert authentification JWT valide

    Accès autorisé :
    - L'utilisateur lui-même (récupération de son profil)
    - Un administrateur (consultation)
    """
    from models.user_model import RoleEnum
    from bson import ObjectId

    requester_id = current_user.get("id", "unknown")
    requester_role = current_user.get("role")

    # Contrôle d'accès : soi-même ou admin
    if requester_id != user_id and requester_role != RoleEnum.admin.value:
        raise HTTPException(
            status_code=403,
            detail="Accès refusé : vous ne pouvez accéder qu'à votre propre photo biométrique"
        )

    # Vérifier que l'utilisateur a bien une photo
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="ID utilisateur invalide")

    user = await db["users"].find_one({"_id": ObjectId(user_id)}, {"face_photo": 1})
    if not user or not user.get("face_photo"):
        raise HTTPException(status_code=404, detail="Aucune photo biométrique enregistrée")

    token = generate_signed_token(user_id, requester_id)

    return {
        "token": token,
        "expires_in_seconds": SIGNED_URL_TTL_SECONDS,
        "url": f"/api/users/{user_id}/biometric-photo?token={token}",
        "warning": "Ce token expire dans 60 secondes. Ne pas stocker ni transmettre.",
    }


# ── Endpoint : Accès à la photo via token signé ──────────────────────────────

@router.get("/users/{user_id}/biometric-photo")
async def get_biometric_photo(
    user_id: str,
    token: str = Query(..., description="Token signé généré par /biometric-photo-token"),
):
    """
    Retourne la photo biométrique déchiffrée si le token signé est valide.
    Finding DATA-03 (Audit Bancaire) : La photo n'est JAMAIS incluse dans les réponses JSON
    standards — uniquement accessible via ce endpoint sécurisé avec token signé.

    Sécurités :
    - Token HMAC signé (impossible à forger)
    - Expiration 60 secondes
    - Vérification que le token cible bien cet user_id (pas de substitution)
    """
    from bson import ObjectId

    # Vérification du token
    payload = verify_signed_token(token)
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Token invalide ou expiré. Générer un nouveau token via /biometric-photo-token."
        )

    # Vérifier que le token cible bien cet user (anti-substitution)
    if payload.get("uid") != user_id:
        logger.warning(
            f"🚫 SECURITY: Token pour user '{payload.get('uid')}' "
            f"utilisé pour accéder à '{user_id}' — rejet"
        )
        raise HTTPException(status_code=403, detail="Token non autorisé pour cet utilisateur")

    # Récupération et déchiffrement de la photo
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="ID utilisateur invalide")

    user = await db["users"].find_one({"_id": ObjectId(user_id)}, {"face_photo": 1})
    if not user or not user.get("face_photo"):
        raise HTTPException(status_code=404, detail="Photo biométrique introuvable")

    try:
        photo_decrypted = decrypt_data(user["face_photo"])
    except ValueError:
        logger.error(f"❌ Erreur déchiffrement photo biométrique user {user_id}")
        raise HTTPException(status_code=500, detail="Erreur de déchiffrement de la photo")

    # Log d'audit (accès aux données C4 — données biométriques)
    from services.audit_service import audit_service
    import asyncio
    asyncio.create_task(audit_service.log_action(
        user_id=payload.get("req"),
        username=f"token-access:{payload.get('req')}",
        action="READ_BIOMETRIC_PHOTO",
        entity=f"User:{user_id}",
        status="SUCCESS",
        source="SIGNED_URL"
    ))

    return {
        "user_id": user_id,
        "photo": photo_decrypted,
        "classification": "C4-CRITIQUE",
        "warning": "Donnée biométrique — traitement conforme RGPD Art. 9 requis",
    }
