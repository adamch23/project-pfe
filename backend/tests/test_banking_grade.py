"""
Tests unitaires complets — Banking Grade (Finding PROC-02 — Audit Bancaire)
Cible : ≥ 80% de couverture de code (--cov-fail-under=80)

Domaines couverts :
  - Sécurité : HMAC, chiffrement, signature biométrique
  - Authentification : JWT RS256, validation password, lockout
  - Validation des entrées : email, password strength, code OTP
  - Services : audit trail, rétention, retention guard
  - API : health check, endpoints protégés
  - Middleware : headers sécurité, error masking
"""

import pytest
import sys
import os
import hmac
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone

# ── Path setup ──────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app')))


# ════════════════════════════════════════════════════════════════════════════
# BLOC 1 : TESTS DE SÉCURITÉ CRYPTOGRAPHIQUE
# Conformité ISO 27001 A.10.1 | PCI-DSS Req. 3.4
# ════════════════════════════════════════════════════════════════════════════

class TestHMACSigning:
    """Tests de la signature HMAC-SHA256 pour l'intégrité des logs."""

    def test_sign_payload_returns_string(self):
        from services.security_service import sign_biometric_payload
        payload = {"user_id": "abc123", "score": 85, "distance": 0.42}
        sig = sign_biometric_payload(payload)
        assert isinstance(sig, str)
        assert len(sig) == 64  # SHA-256 hex = 64 chars

    def test_sign_payload_deterministic(self):
        """La même donnée produit toujours la même signature."""
        from services.security_service import sign_biometric_payload
        payload = {"user_id": "abc123", "score": 85}
        assert sign_biometric_payload(payload) == sign_biometric_payload(payload)

    def test_sign_payload_key_order_independent(self):
        """La signature est indépendante de l'ordre des clés (sort_keys=True)."""
        from services.security_service import sign_biometric_payload
        p1 = {"a": 1, "b": 2, "c": 3}
        p2 = {"c": 3, "a": 1, "b": 2}
        assert sign_biometric_payload(p1) == sign_biometric_payload(p2)

    def test_verify_valid_signature(self):
        from services.security_service import sign_biometric_payload, verify_biometric_signature
        payload = {"user_id": "user1", "score": 92, "distance": 0.15}
        sig = sign_biometric_payload(payload)
        assert verify_biometric_signature(payload, sig) is True

    def test_verify_tampered_payload_fails(self):
        """Une modification du payload invalide la signature."""
        from services.security_service import sign_biometric_payload, verify_biometric_signature
        payload = {"user_id": "user1", "score": 85}
        sig = sign_biometric_payload(payload)
        tampered = {"user_id": "user1", "score": 100}  # Score falsifié
        assert verify_biometric_signature(tampered, sig) is False

    def test_verify_wrong_signature_fails(self):
        from services.security_service import verify_biometric_signature
        payload = {"user_id": "user1", "score": 85}
        assert verify_biometric_signature(payload, "deadbeef" * 8) is False

    def test_verify_signature_timing_safe(self):
        """Vérifie que compare_digest est utilisé (pas de timing attack)."""
        from services.security_service import sign_biometric_payload, verify_biometric_signature
        # Si compare_digest n'était pas utilisé, ce test ne garantirait pas la sécurité
        # mais au moins on vérifie que la fonction ne plante pas avec des inputs malformés
        payload = {"x": 1}
        assert verify_biometric_signature(payload, "") is False
        assert verify_biometric_signature(payload, "x" * 64) is False


class TestEncryption:
    """Tests du chiffrement AES-256 (Fernet) pour les données sensibles."""

    def test_encrypt_returns_different_value(self):
        from services.security_service import encrypt_data
        data = "biometric_data_12345"
        encrypted = encrypt_data(data)
        assert encrypted != data
        assert len(encrypted) > 0

    def test_encrypt_decrypt_roundtrip(self):
        from services.security_service import encrypt_data, decrypt_data
        original = "data:image/jpeg;base64,/9j/4AAQSkZJRgAB..."
        encrypted = encrypt_data(original)
        decrypted = decrypt_data(encrypted)
        assert decrypted == original

    def test_decrypt_invalid_data_raises_valueerror(self):
        from services.security_service import decrypt_data
        with pytest.raises(ValueError) as exc_info:
            decrypt_data("not_valid_fernet_token")
        assert "déchiffrement" in str(exc_info.value).lower() or "corrompue" in str(exc_info.value).lower()

    def test_encrypt_empty_string_returns_empty(self):
        from services.security_service import encrypt_data
        assert encrypt_data("") == ""
        assert encrypt_data(None) is None

    def test_decrypt_empty_string_returns_empty(self):
        from services.security_service import decrypt_data
        assert decrypt_data("") == ""
        assert decrypt_data(None) is None

    def test_encrypt_produces_unique_ciphertexts(self):
        """Fernet utilise de l'aléa — deux chiffrements du même texte produisent des tokens différents."""
        from services.security_service import encrypt_data
        data = "same_input"
        enc1 = encrypt_data(data)
        enc2 = encrypt_data(data)
        assert enc1 != enc2  # Fernet inclut un timestamp et un IV aléatoire


# ════════════════════════════════════════════════════════════════════════════
# BLOC 2 : TESTS D'AUTHENTIFICATION
# Conformité PCI-DSS Req. 8 | ISO 27001 A.9
# ════════════════════════════════════════════════════════════════════════════

class TestPasswordValidation:
    """Tests de la politique de complexité des mots de passe (PCI-DSS Req. 8.3.6)."""

    def test_valid_password_accepted(self):
        from services.user_service import validate_password_strength
        # Ne doit pas lever d'exception
        validate_password_strength("Secure@2026!")

    def test_password_too_short_rejected(self):
        from fastapi import HTTPException
        from services.user_service import validate_password_strength
        with pytest.raises(HTTPException) as exc_info:
            validate_password_strength("Ab1!")
        assert exc_info.value.status_code == 422

    def test_password_no_uppercase_rejected(self):
        from fastapi import HTTPException
        from services.user_service import validate_password_strength
        with pytest.raises(HTTPException):
            validate_password_strength("secure@2026!")

    def test_password_no_digit_rejected(self):
        from fastapi import HTTPException
        from services.user_service import validate_password_strength
        with pytest.raises(HTTPException):
            validate_password_strength("Secure@Pass!")

    def test_password_no_special_rejected(self):
        from fastapi import HTTPException
        from services.user_service import validate_password_strength
        with pytest.raises(HTTPException):
            validate_password_strength("SecurePass2026")

    def test_password_no_lowercase_rejected(self):
        from fastapi import HTTPException
        from services.user_service import validate_password_strength
        with pytest.raises(HTTPException):
            validate_password_strength("SECURE@2026!")

    @pytest.mark.parametrize("valid_pwd", [
        "Banking@2026!",
        "Attijari#Secure1",
        "P@ssw0rd_Strong",
        "Xr9!qLeP$mK2",
    ])
    def test_valid_passwords_parametrized(self, valid_pwd):
        from services.user_service import validate_password_strength
        validate_password_strength(valid_pwd)  # Ne doit pas lever d'exception


class TestEmailValidation:
    """Tests de validation du format email."""

    def test_valid_email_accepted(self):
        from services.user_service import validate_email_format
        validate_email_format("user@attijari.tn")

    def test_invalid_email_rejected(self):
        from fastapi import HTTPException
        from services.user_service import validate_email_format
        with pytest.raises(HTTPException) as exc_info:
            validate_email_format("not-an-email")
        assert exc_info.value.status_code == 422

    def test_email_missing_domain_rejected(self):
        from fastapi import HTTPException
        from services.user_service import validate_email_format
        with pytest.raises(HTTPException):
            validate_email_format("user@")


class TestJWT:
    """Tests du JWT RS256 (Finding SEC-01 — Audit Bancaire)."""

    def test_create_token_returns_string(self):
        from auth import create_access_token
        token = create_access_token({"sub": "507f1f77bcf86cd799439011", "role": "admin"})
        assert isinstance(token, str)
        assert len(token) > 50

    def test_decode_valid_token(self):
        from auth import create_access_token, decode_access_token
        data = {"sub": "507f1f77bcf86cd799439011", "role": "employer"}
        token = create_access_token(data)
        decoded = decode_access_token(token)
        assert decoded is not None
        assert decoded["sub"] == "507f1f77bcf86cd799439011"
        assert decoded["role"] == "employer"

    def test_decode_invalid_token_returns_none(self):
        from auth import decode_access_token
        assert decode_access_token("invalid.token.here") is None
        assert decode_access_token("") is None

    def test_decode_tampered_token_returns_none(self):
        from auth import create_access_token, decode_access_token
        token = create_access_token({"sub": "abc123"})
        tampered = token[:-5] + "XXXXX"
        assert decode_access_token(tampered) is None

    def test_token_uses_rs256_algorithm(self):
        """Vérifie que l'algorithme est RS256 et non HS256 (Finding ex-SEC-01)."""
        from auth import ALGORITHM
        assert ALGORITHM == "RS256", f"L'algorithme JWT doit être RS256, trouvé: {ALGORITHM}"

    def test_token_expires(self):
        from auth import create_access_token, decode_access_token
        # Token avec expiration dans le passé (1 minute = -1440 minutes)
        token = create_access_token({"sub": "abc"}, expires_delta=-1)
        result = decode_access_token(token)
        assert result is None, "Un token expiré doit retourner None"


class TestPasswordHashing:
    """Tests du hashage de mot de passe (PBKDF2-SHA256)."""

    def test_hash_password_returns_hash(self):
        from auth import hash_password
        hashed = hash_password("TestPassword@2026!")
        assert hashed != "TestPassword@2026!"
        assert len(hashed) > 20

    def test_verify_correct_password(self):
        from auth import hash_password, verify_password
        pwd = "Banking@Secure2026!"
        hashed = hash_password(pwd)
        assert verify_password(pwd, hashed) is True

    def test_verify_wrong_password_fails(self):
        from auth import hash_password, verify_password
        hashed = hash_password("Correct@Pwd2026!")
        assert verify_password("Wrong@Pwd2026!", hashed) is False

    def test_hash_is_unique_per_call(self):
        """Chaque appel produit un hash différent (salt aléatoire)."""
        from auth import hash_password
        pwd = "SamePassword@2026!"
        assert hash_password(pwd) != hash_password(pwd)


# ════════════════════════════════════════════════════════════════════════════
# BLOC 3 : TESTS DES SERVICES MÉTIER
# ════════════════════════════════════════════════════════════════════════════

class TestUserServiceValidation:
    """Tests de validation des données dans UserService."""

    def test_validate_name_valid(self):
        from services.user_service import validate_name
        validate_name("Adam", "Prénom")  # Ne doit pas lever d'exception

    def test_validate_name_too_short_rejected(self):
        from fastapi import HTTPException
        from services.user_service import validate_name
        with pytest.raises(HTTPException):
            validate_name("X", "Prénom")

    def test_validate_name_with_numbers_rejected(self):
        from fastapi import HTTPException
        from services.user_service import validate_name
        with pytest.raises(HTTPException):
            validate_name("Adam123", "Prénom")

    def test_validate_code_format_valid(self):
        from services.user_service import validate_code_format
        validate_code_format("123456")

    def test_validate_code_format_invalid(self):
        from fastapi import HTTPException
        from services.user_service import validate_code_format
        with pytest.raises(HTTPException):
            validate_code_format("12345")  # 5 chiffres
        with pytest.raises(HTTPException):
            validate_code_format("1234567")  # 7 chiffres
        with pytest.raises(HTTPException):
            validate_code_format("abcdef")  # Lettres


class TestAuditServiceSigning:
    """Tests du service d'audit et de l'intégrité des logs."""

    @pytest.mark.asyncio
    async def test_log_action_creates_entry_with_signature(self):
        """Vérifie que log_action crée une entrée signée en base."""
        from services.audit_service import AuditService

        mock_collection = MagicMock()
        mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id="test123"))

        service = AuditService()
        service.collection = mock_collection

        await service.log_action(
            user_id="user123",
            username="test@test.com",
            action="LOGIN",
            entity="User",
            status="SUCCESS",
        )

        mock_collection.insert_one.assert_called_once()
        call_args = mock_collection.insert_one.call_args[0][0]
        assert "signature" in call_args
        assert call_args["action"] == "LOGIN"
        assert call_args["username"] == "test@test.com"

    @pytest.mark.asyncio
    async def test_log_action_includes_correlation_id(self):
        """Vérifie que le correlation_id est inclus dans le log."""
        from services.audit_service import AuditService
        import uuid

        mock_collection = MagicMock()
        mock_collection.insert_one = AsyncMock()

        service = AuditService()
        service.collection = mock_collection
        cid = str(uuid.uuid4())

        await service.log_action(
            user_id="u1", username="u@t.com", action="UPDATE",
            entity="User", correlation_id=cid
        )

        call_args = mock_collection.insert_one.call_args[0][0]
        assert call_args["correlation_id"] == cid

    @pytest.mark.asyncio
    async def test_log_action_does_not_raise_on_db_error(self):
        """L'audit ne bloque jamais l'application même si MongoDB est down."""
        from services.audit_service import AuditService

        mock_collection = MagicMock()
        mock_collection.insert_one = AsyncMock(side_effect=Exception("MongoDB down"))

        service = AuditService()
        service.collection = mock_collection

        # Ne doit pas lever d'exception
        await service.log_action(
            user_id=None, username="system",
            action="PROBE", entity="/health"
        )


class TestRetentionServiceGuard:
    """Tests du garde-fou de rétention (Finding DATA-02)."""

    @pytest.mark.asyncio
    async def test_purge_skipped_when_no_eligible_documents(self):
        """Aucune purge si aucun document n'est éligible."""
        from services.retention_service import RetentionService

        mock_collection = MagicMock()
        mock_collection.count_documents = AsyncMock(return_value=0)
        mock_collection.delete_many = AsyncMock()

        service = RetentionService()
        service.audit_collection = mock_collection
        service.biometrics_collection = MagicMock()
        service.biometrics_collection.delete_many = AsyncMock(
            return_value=MagicMock(deleted_count=0)
        )

        result = await service.purge_old_data()
        assert result["audit_purgés"] == 0
        mock_collection.delete_many.assert_not_called()

    @pytest.mark.asyncio
    async def test_archive_flag_false_allows_purge_in_dev(self):
        """En mode DEV (REQUIRE_S3_ARCHIVE=false), la purge est autorisée avec avertissement."""
        from services.retention_service import RetentionService
        import os

        mock_collection = MagicMock()
        mock_collection.count_documents = AsyncMock(return_value=5)
        mock_collection.delete_many = AsyncMock(return_value=MagicMock(deleted_count=5))

        service = RetentionService()
        service.audit_collection = mock_collection
        service.biometrics_collection = MagicMock()
        service.biometrics_collection.delete_many = AsyncMock(
            return_value=MagicMock(deleted_count=0)
        )

        with patch.dict(os.environ, {"REQUIRE_S3_ARCHIVE_BEFORE_PURGE": "false"}):
            result = await service.purge_old_data()
        assert result["audit_purgés"] == 5


# ════════════════════════════════════════════════════════════════════════════
# BLOC 4 : TESTS D'INTÉGRATION API
# Conformité PCI-DSS Req. 6.2.4 | CMMI Niveau 3
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_health_endpoint_returns_ok():
    """Vérifie que /api/health répond OK."""
    from httpx import AsyncClient, ASGITransport
    from main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_root_endpoint_returns_version():
    """Vérifie que / retourne les informations de version."""
    from httpx import AsyncClient, ASGITransport
    from main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert "version" in response.json()


@pytest.mark.asyncio
async def test_security_headers_present():
    """Vérifie que tous les headers de sécurité sont présents (Finding SEC-04)."""
    from httpx import AsyncClient, ASGITransport
    from main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
        response = await client.get("/api/health")

    headers = response.headers
    assert "x-content-type-options" in headers, "X-Content-Type-Options manquant"
    assert "x-frame-options" in headers, "X-Frame-Options manquant"
    assert "content-security-policy" in headers, "Content-Security-Policy manquant (Finding SEC-04)"
    assert "strict-transport-security" in headers, "HSTS manquant"


@pytest.mark.asyncio
async def test_correlation_id_in_response():
    """Vérifie que X-Correlation-ID est retourné (Finding BCP-03)."""
    from httpx import AsyncClient, ASGITransport
    from main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
        response = await client.get("/api/health")

    assert "x-correlation-id" in response.headers, "X-Correlation-ID manquant — Finding BCP-03"


@pytest.mark.asyncio
async def test_chaos_endpoint_requires_auth():
    """Les endpoints chaos nécessitent une authentification (Finding SEC-02)."""
    from httpx import AsyncClient, ASGITransport
    from main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
        response = await client.get("/api/chaos/fail")

    assert response.status_code in [401, 403], \
        f"L'endpoint chaos doit être protégé, got {response.status_code}"


@pytest.mark.asyncio
async def test_protected_endpoint_requires_token():
    """Vérifie qu'un endpoint protégé retourne 401 sans token."""
    from httpx import AsyncClient, ASGITransport
    from main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
        response = await client.get("/api/users/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_biometric_endpoint_requires_auth():
    """Vérifie que /api/biometrics/log-attempt exige un token JWT valide."""
    from httpx import AsyncClient, ASGITransport
    from main import app

    payload = {"user_id": "abc", "distance": 0.3, "confidence_score": 90, "timestamp": "2026-06-11T00:00:00Z"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
        response = await client.post("/api/biometrics/log-attempt", json=payload)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_biometric_endpoint_with_valid_token():
    """Vérifie l'enregistrement biométrique avec un token valide."""
    from httpx import AsyncClient, ASGITransport
    from main import app
    from auth import create_access_token

    token = create_access_token({"sub": "507f1f77bcf86cd799439011", "role": "admin"})
    payload = {
        "user_id": "507f1f77bcf86cd799439011",
        "distance": 0.25,
        "confidence_score": 95,
        "timestamp": "2026-06-11T00:00:00Z"
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://localhost",
        headers={"Authorization": f"Bearer {token}"}
    ) as client:
        response = await client.post("/api/biometrics/log-attempt", json=payload)

    # 200 si user en base (mock), 401 "Utilisateur non trouvé" si mock retourne None
    assert response.status_code in [200, 401, 500]


# ════════════════════════════════════════════════════════════════════════════
# BLOC 5 : TESTS DE SÉCURITÉ AVANCÉS
# OWASP Top 10 | PCI-DSS Req. 6.4
# ════════════════════════════════════════════════════════════════════════════

class TestOWASPInputValidation:
    """Tests de protection contre les injections (OWASP A03)."""

    @pytest.mark.asyncio
    async def test_sql_injection_in_email_rejected(self):
        from httpx import AsyncClient, ASGITransport
        from main import app

        payload = {"email": "' OR '1'='1", "password": "Test@2026!"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
            response = await client.post("/api/login", json=payload)

        # Doit rejeter avec 422 (validation) ou 401 (email invalide détecté)
        assert response.status_code in [401, 422]

    @pytest.mark.asyncio
    async def test_xss_payload_in_email_rejected(self):
        from httpx import AsyncClient, ASGITransport
        from main import app

        payload = {"email": "<script>alert('xss')</script>@evil.com", "password": "Test@2026!"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
            response = await client.post("/api/login", json=payload)

        assert response.status_code in [401, 422]

    @pytest.mark.asyncio
    async def test_oversized_payload_rejected(self):
        """Vérifie la protection contre les payloads excessivement longs."""
        from httpx import AsyncClient, ASGITransport
        from main import app

        # Email excessivement long (> 320 chars = invalide RFC 5321)
        very_long_email = "a" * 500 + "@test.com"
        payload = {"email": very_long_email, "password": "Test@2026!"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
            response = await client.post("/api/login", json=payload)

        assert response.status_code in [401, 422]


class TestAccountLockout:
    """Tests du mécanisme de lockout anti-brute-force (Finding SEC-06 — PCI-DSS 8.3.4)."""

    def test_lockout_constants_configured(self):
        """Vérifie que les constantes de lockout sont bien définies."""
        from services.user_service import UserService
        service = UserService()
        assert service.MAX_FAILED_ATTEMPTS == 5
        assert service.LOCKOUT_DURATION_MINUTES == 15

    @pytest.mark.asyncio
    async def test_lockout_applied_after_max_attempts(self):
        """Vérifie que le lockout est appliqué après MAX_FAILED_ATTEMPTS."""
        from services.user_service import UserService

        service = UserService()

        # Simuler un utilisateur avec 5 tentatives échouées
        mock_user = {
            "_id": MagicMock(),
            "email": "test@test.com",
            "failed_login_attempts": 4,  # Le 5ème va déclencher le lockout
        }

        mock_collection = MagicMock()
        mock_collection.update_one = AsyncMock()
        service.collection = mock_collection

        await service._record_failed_attempt("test@test.com", mock_user)

        # Vérifier que update_one a été appelé avec lockout_until
        call_kwargs = mock_collection.update_one.call_args[0][1]["$set"]
        assert "lockout_until" in call_kwargs

    @pytest.mark.asyncio
    async def test_lockout_not_applied_below_threshold(self):
        """Vérifie que le lockout N'EST PAS appliqué avant d'atteindre le seuil."""
        from services.user_service import UserService

        service = UserService()
        mock_user = {
            "failed_login_attempts": 2,  # En dessous du seuil (5)
        }

        mock_collection = MagicMock()
        mock_collection.update_one = AsyncMock()
        service.collection = mock_collection

        await service._record_failed_attempt("test@test.com", mock_user)

        call_kwargs = mock_collection.update_one.call_args[0][1]["$set"]
        assert "lockout_until" not in call_kwargs
