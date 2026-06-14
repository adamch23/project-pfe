"""
security_service.py — Services de sécurité cryptographique (Banking Grade)
Conformité ISO 27001 A.10.1 | PCI-DSS Req. 3.4 | DORA Art. 9

Finding SEC-07 résolu : Utilisation explicite de hmac.new() avec digestmod nommé
pour améliorer la lisibilité et la maintenabilité du code de sécurité critique.
"""
import hmac
import hashlib
import json
from typing import Optional
from cryptography.fernet import Fernet
from services.secret_manager import secret_manager

# ── Clés Cryptographiques (via SecretManager — Vault-ready) ─────────────────
# En production : SECRET_MANAGER → HashiCorp Vault → AWS Secrets Manager
# En développement : Variables d'environnement (.env local)

SECRET_SIGNING_KEY: str = secret_manager.get_secret("LOG_SIGNING_KEY")
if not SECRET_SIGNING_KEY:
    raise RuntimeError(
        "🚨 CRITICAL: LOG_SIGNING_KEY manquante. "
        "L'intégrité des logs d'audit ne peut pas être garantie. "
        "Définissez LOG_SIGNING_KEY dans vos variables d'environnement ou Vault."
    )

ENCRYPTION_KEY: str = secret_manager.get_secret("DATA_ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    raise RuntimeError(
        "🚨 CRITICAL: DATA_ENCRYPTION_KEY non définie. "
        "Le serveur refuse de démarrer sans clé de chiffrement. "
        "Générez une clé Fernet avec : python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    )

# Initialisation du chiffrement AES-256 Fernet
_fernet_key = ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY
cipher_suite = Fernet(_fernet_key)


# ── Chiffrement AES-256 ───────────────────────────────────────────────────────

def encrypt_data(data: Optional[str]) -> Optional[str]:
    """
    Chiffre une chaîne de caractères (ex: photo biométrique en base64).
    Utilise Fernet (AES-256-CBC + HMAC-SHA256) — PCI-DSS Req. 3.4, RGPD Art. 9.
    """
    if not data:
        return data
    return cipher_suite.encrypt(data.encode()).decode()


def decrypt_data(token: Optional[str]) -> Optional[str]:
    """
    Déchiffre un token Fernet pour récupérer la donnée originale.
    En contexte bancaire, le déchiffrement échoue proprement si la donnée est corrompue
    ou si la clé a changé (évite de traiter des données non-chiffrées par erreur).
    """
    if not token:
        return token
    try:
        return cipher_suite.decrypt(token.encode()).decode()
    except Exception as e:
        raise ValueError(
            f"❌ Erreur de déchiffrement : Donnée corrompue ou clé invalide. Détails: {e}"
        )


# ── Signature HMAC-SHA256 ─────────────────────────────────────────────────────

def sign_biometric_payload(payload: dict) -> str:
    """
    Génère une signature HMAC-SHA256 garantissant l'intégrité du log biométrique.
    Empêche toute altération des scores ou résultats en base de données.

    Conformité ISO 27001 A.12.4.2 (Protection des informations de journalisation).

    Finding SEC-07 résolu : digestmod explicitement nommé pour la lisibilité.
    """
    # Sérialisation déterministe : clés triées pour hash consistant
    payload_string = json.dumps(payload, sort_keys=True, default=str)

    # Fix SEC-07 : digestmod nommé explicitement (best practice Python ≥ 3.4)
    signature = hmac.new(
        key=SECRET_SIGNING_KEY.encode("utf-8"),
        msg=payload_string.encode("utf-8"),
        digestmod=hashlib.sha256
    ).hexdigest()

    return signature


def verify_biometric_signature(payload: dict, signature: str) -> bool:
    """
    Vérifie qu'un log d'audit n'a pas été altéré depuis son enregistrement.
    Utilisé lors des audits de conformité ISO 27001.

    Sécurité : compare_digest() protège contre les timing attacks.
    """
    if not signature:
        return False
    try:
        expected_signature = sign_biometric_payload(payload)
        return hmac.compare_digest(expected_signature, signature)
    except Exception:
        return False
