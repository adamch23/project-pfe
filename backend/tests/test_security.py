import pytest
import sys
import os

# Ajout du chemin app pour permettre les imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app')))

from services.security_service import sign_biometric_payload, verify_biometric_signature, encrypt_data, decrypt_data

def test_biometric_signature():
    """Vérifie que la signature HMAC est valide et détecte les altérations."""
    payload = {"user_id": "123", "distance": 0.45, "score": 85}
    signature = sign_biometric_payload(payload)
    
    assert verify_biometric_signature(payload, signature) is True
    
    # Altération malveillante du score
    malicious_payload = payload.copy()
    malicious_payload["score"] = 100
    assert verify_biometric_signature(malicious_payload, signature) is False

def test_encryption_at_rest():
    """Vérifie que le chiffrement AES-256 (Fernet) fonctionne correctement."""
    secret_data = "data:image/jpeg;base64,sensitive_biometric_data"
    encrypted = encrypt_data(secret_data)
    
    assert encrypted != secret_data
    assert decrypt_data(encrypted) == secret_data

def test_decryption_failure():
    """Vérifie que le système refuse de traiter des données non chiffrées/invalides."""
    plain_text = "not_encrypted_data"
    with pytest.raises(ValueError):
        decrypt_data(plain_text)
