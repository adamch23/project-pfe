from fastapi import APIRouter, HTTPException, Depends
from dependencies import get_current_user
from pydantic import BaseModel
from typing import Optional
import logging
from datetime import datetime, timezone
from database import db

router = APIRouter()
logger = logging.getLogger(__name__)

class BiometricLog(BaseModel):
    user_id: Optional[str] = None
    distance: float
    confidence_score: int
    timestamp: str

@router.post("/biometrics/log-attempt")
async def log_biometric_attempt(log: BiometricLog, current_user: dict = Depends(get_current_user)):
    """
    Enregistre une tentative biométrique avec signature cryptographique.
    Requiert une authentification JWT valide (Bank Grade — ISO 27001 A.12.4).
    """
    try:
        from services.security_service import sign_biometric_payload

        log_entry = log.dict()
        log_entry["created_at"] = datetime.now(timezone.utc).isoformat()  # UTC-aware timestamp

        # Signature cryptographique pour non-répudiation (Bank Grade)
        log_entry["signature_proof"] = sign_biometric_payload(log_entry)

        # Insertion dans MongoDB pour audit
        await db["biometric_logs"].insert_one(log_entry)

        logger.info(f"💾 Log biométrique SIGNÉ enregistré pour l'utilisateur {log.user_id} (Score: {log.confidence_score}%)")
        return {"status": "success", "message": "Log recorded"}

    except HTTPException:
        # ← FIX: Re-propagation directe — ne pas masquer les 401/403 en 500
        raise
    except Exception as e:
        logger.error(f"❌ Erreur inattendue lors de l'enregistrement du log biométrique : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erreur interne lors de l'enregistrement du log")
