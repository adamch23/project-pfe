from datetime import datetime, timezone
from typing import Any, Optional
from database import db
from services.security_service import sign_biometric_payload
import logging

logger = logging.getLogger(__name__)

class AuditService:
    def __init__(self):
        self.collection = db["audit_logs"]

    async def log_action(
        self,
        user_id: Optional[str],
        username: Optional[str],
        action: str,           # CREATE, UPDATE, DELETE, LOGIN, LOGOUT
        entity: str,           # User, Biometric, Pipeline...
        before: Optional[Any] = None,
        after: Optional[Any] = None,
        status: str = "SUCCESS",
        ip_address: Optional[str] = None,
        source: str = "API",
        correlation_id: Optional[str] = None,   # Finding BCP-03 — Corrélation des événements
    ):
        """
        Enregistre une action d'audit de manière asynchrone.
        Chaque entrée est signée HMAC-SHA256 pour garantir l'intégrité (Finding SEC-03).
        Le champ correlation_id permet de tracer un flux de bout en bout dans le SIEM.
        """
        try:
            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "correlation_id": correlation_id,
                "user_id": user_id,
                "username": username,
                "action": action,
                "entity": entity,
                "before": before,
                "after": after,
                "status": status,
                "ip_address": ip_address,
                "source": source,
            }

            # 🔐 Signature d'intégrité (Standard Bancaire — ISO 27001 A.12.4.2)
            # Garantit qu'un administrateur ne peut modifier le log sans invalider la signature.
            log_entry["signature"] = sign_biometric_payload(log_entry)

            # Insertion en base de données
            await self.collection.insert_one(log_entry)

        except Exception as e:
            # On ne bloque jamais l'application si l'audit échoue,
            # mais on log l'erreur critique pour investigation ultérieure.
            logger.error(f"❌ Échec de l'enregistrement de l'audit trail: {e}")

    async def verify_log_integrity(self, log_id: str) -> bool:
        """
        Vérifie l'intégrité d'une entrée d'audit via sa signature HMAC.
        Utilisé lors des audits de conformité ISO 27001.
        """
        from bson import ObjectId
        from services.security_service import verify_biometric_signature
        try:
            log = await self.collection.find_one({"_id": ObjectId(log_id)})
            if not log:
                return False
            stored_signature = log.pop("signature", None)
            log.pop("_id", None)
            return verify_biometric_signature(log, stored_signature)
        except Exception as e:
            logger.error(f"❌ Erreur vérification intégrité log {log_id}: {e}")
            return False


# Singleton
audit_service = AuditService()
