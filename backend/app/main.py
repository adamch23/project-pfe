# ================================================================
# main.py — FastAPI Entry Point (Banking Grade — Post-Audit v3.0)
# ================================================================

import logging
import sys
import os
import uuid
from dotenv import load_dotenv

# 🚀 CHARGEMENT DES SECRETS (Doit être fait avant tout autre import local)
load_dotenv()

import signal
import asyncio
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from database import db
from services.monitoring_service import monitoring_manager

# Configuration du logging JSON structuré (Finding BCP-03 — Audit Bancaire)
# Format structuré pour faciliter l'ingestion SIEM (Splunk, Elastic, Loki)
logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("server.log", encoding="utf-8")
    ],
)
logger = logging.getLogger(__name__)

# Forcer le flush des logs
sys.stdout.reconfigure(line_buffering=True)

# ── Variable globale IS_HEALTHY (déclarée en haut — Finding PROC-04) ────────
# Contrôle l'état du service pour les health checks.
# En multi-instance, externaliser vers Redis (Finding ARCH-01).
IS_HEALTHY = True


# ── Lifespan ─────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("=" * 60)
    logger.info("=== Démarrage du serveur FastAPI ===")

    # ── STARTUP GUARD (Audit SEC — Finding GOV-01) ────────────────
    # Empêche un démarrage accidentel en mode DEV sur une DB non-dédiée
    current_env = os.getenv("ENV", "dev").lower()
    mongo_url = os.getenv("MONGO_URL", "")
    if current_env == "prod" and "localhost" in mongo_url:
        raise RuntimeError(
            "🚨 STARTUP GUARD: ENV=prod mais MONGO_URL pointe vers localhost. "
            "Veuillez configurer une instance MongoDB de production."
        )
    logger.info(f"✅ Startup Guard passé — ENV={current_env}")

    try:
        from auth import create_default_admin
        await create_default_admin()
        logger.info("✅ Admin par défaut créé/vérifié.")
    except Exception as e:
        logger.error(f"❌ Erreur création admin: {e}", exc_info=True)

    # Pré-initialiser le RAG engine (optionnel)
    try:
        from explainable_AI.RAG import get_rag_engine
        engine = get_rag_engine()
        logger.info(f"✅ RAG engine initialisé — GPU: {engine._gpu_available}")
    except Exception as e:
        logger.warning(f"⚠️ RAG engine non initialisé au démarrage: {e}")

    # 🚀 DÉMARRAGE DU MONITORING (Audit BCP-02)
    try:
        monitoring_manager.start_all()
        logger.info("✅ Stack de monitoring locale (Windows) lancée.")
    except Exception as e:
        logger.error(f"❌ Échec démarrage monitoring: {e}")

    # ♻️ RÉTENTION DES DONNÉES (GDPR/PCI)
    try:
        from services.retention_service import retention_service
        asyncio.create_task(retention_service.purge_old_data())
        logger.info("✅ Politique de rétention des données appliquée.")
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'application de la rétention : {e}")

    logger.info("=== Serveur prêt ===")
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("=== Arrêt du serveur FastAPI ===")
    monitoring_manager.stop_all()
    logger.info("✅ Stack de monitoring arrêtée.")


# ── Application ───────────────────────────────────────────────────
app = FastAPI(
    title="XAI Anomaly Detection API",
    version="3.0.0",
    description="API d'analyse des anomalies avec IA explicable (RAG + Ollama) — Banking Grade",
    lifespan=lifespan,
    # Désactiver la documentation en production (Finding SEC-05)
    docs_url="/docs" if os.getenv("ENV", "dev").lower() != "prod" else None,
    redoc_url="/redoc" if os.getenv("ENV", "dev").lower() != "prod" else None,
)

# ── Trusted Hosts (Désactivé) ────────────────────────────────────────────────
# app.add_middleware(
#    TrustedHostMiddleware, allowed_hosts=["*"]
# )

# ── CORS (Ouvert) ────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:3001"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Security Headers Middleware (Finding SEC-04 — Audit Bancaire) ──────────────
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Injecte un correlation_id unique pour chaque requête (Finding BCP-03)."""
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    request.state.correlation_id = correlation_id
    return await call_next(request)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    # ── Headers de sécurité obligatoires (PCI-DSS, OWASP) ─────────
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # ── Correlation ID tracé (Finding BCP-03) ──────────────────────
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    response.headers["X-Correlation-ID"] = correlation_id
    return response

@app.middleware("http")
async def cookie_to_auth_header_middleware(request: Request, call_next):
    from auth import COOKIE_NAME
    token = request.cookies.get(COOKIE_NAME)
    if token:
        # Le frontend (React) a des restes de code envoyant "Authorization: Bearer undefined"
        # On force l'écrasement avec le vrai token du cookie HttpOnly
        h = list(request.scope["headers"])
        h = [header for header in h if header[0] != b"authorization"]
        h.append((b"authorization", f"Bearer {token}".encode("latin-1")))
        request.scope["headers"] = h
        print(f"🔑 [AUTH] Cookie '{COOKIE_NAME}' injecté avec succès (écrasement frontal).")
    return await call_next(request)


# ── Middleware pour logger toutes les requêtes (structuré) ────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    correlation_id = getattr(request.state, "correlation_id", "N/A")
    logger.info(f"📥 {request.method} {request.url.path} [correlation_id={correlation_id}]")
    try:
        response = await call_next(request)
        logger.info(
            f"📤 {response.status_code} ← {request.url.path} [correlation_id={correlation_id}]"
        )
        return response
    except Exception as e:
        logger.error(
            f"❌ Erreur sur {request.url.path} [correlation_id={correlation_id}]: {e}",
            exc_info=True
        )
        # Finding SEC-05 (Audit Bancaire) : Ne pas exposer les détails d'erreur en prod
        env = os.getenv("ENV", "dev").lower()
        if env == "prod":
            return JSONResponse(
                status_code=500,
                content={"detail": "Erreur interne.", "correlation_id": correlation_id}
            )
        return JSONResponse(
            status_code=500,
            content={"detail": f"Erreur interne: {str(e)}", "correlation_id": correlation_id}
        )


# ── Middleware Audit Global (Finding SEC-03 — Audit Bancaire) ─────────────
# Capture l'identité JWT pour tous les appels mutants (POST/PUT/DELETE)
@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    # On ignore le health check pour ne pas polluer l'audit trail
    if request.url.path in ["/api/health", "/", "/api/health/monitoring", "/health"]:
        return await call_next(request)

    # Fix SEC-03 (Audit Bancaire) : Décoder le JWT pour capturer l'identité utilisateur
    user_id = None
    username = "Anonymous"
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ").strip()
        try:
            from auth import decode_access_token
            payload = decode_access_token(token)
            if payload:
                user_id = payload.get("sub")
                username = payload.get("email", f"user:{user_id}")
        except Exception:
            pass  # Token invalide — l'auth middleware gérera le 401

    start_time = datetime.now(timezone.utc)
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))

    try:
        response = await call_next(request)
        status = "SUCCESS" if response.status_code < 400 else "FAILED"

        # Logguer toutes les mutationsavec identité capturée
        if request.method != "GET":
            from services.audit_service import audit_service
            asyncio.create_task(audit_service.log_action(
                user_id=user_id,
                username=username,
                action=request.method,
                entity=request.url.path,
                status=status,
                ip_address=request.client.host if request.client else "unknown",
                source="GLOBAL_MIDDLEWARE",
                correlation_id=correlation_id
            ))

        return response
    except Exception as e:
        from services.audit_service import audit_service
        asyncio.create_task(audit_service.log_action(
            user_id=user_id,
            username=username,
            action=request.method,
            entity=request.url.path,
            status="CRITICAL_ERROR",
            after={"error": str(e)},
            ip_address=request.client.host if request.client else "unknown",
            source="GLOBAL_MIDDLEWARE",
            correlation_id=correlation_id
        ))
        raise e


# ── Global exception handler ──────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    correlation_id = getattr(request.state, "correlation_id", "N/A")
    logger.error(
        f"❌ Exception non gérée sur {request.url} [correlation_id={correlation_id}]: {exc}",
        exc_info=True
    )
    # Finding SEC-05 (Audit Bancaire) : Masquer les détails d'erreur en production
    env = os.getenv("ENV", "dev").lower()
    if env == "prod":
        return JSONResponse(
            status_code=500,
            content={"detail": "Une erreur interne s'est produite.", "correlation_id": correlation_id},
        )
    return JSONResponse(
        status_code=500,
        content={"detail": f"Erreur interne: {str(exc)}", "correlation_id": correlation_id},
    )


# ── Routers ───────────────────────────────────────────────────────
try:
    from controllers import user_controller
    app.include_router(user_controller.router, prefix="/api", tags=["users"])
    logger.info("✅ Router users chargé.")
except Exception as e:
    logger.error(f"❌ Erreur chargement router users: {e}", exc_info=True)

try:
    from controllers import biometrics_controller
    app.include_router(biometrics_controller.router, prefix="/api", tags=["Biometrics"])
    logger.info("✅ Router Biometrics chargé.")
except Exception as e:
    logger.error(f"❌ Erreur chargement router Biometrics: {e}", exc_info=True)

try:
    from services.signed_url_service import router as signed_url_router
    app.include_router(signed_url_router, prefix="/api", tags=["Biometric Signed URLs"])
    logger.info("✅ Router Signed URLs (DATA-03) chargé.")
except Exception as e:
    logger.error(f"❌ Erreur chargement router Signed URLs: {e}", exc_info=True)

try:
    from explainable_AI.explainable_AI import router as xai_router
    app.include_router(xai_router, prefix="/api/xai", tags=["Explainable AI"])
    logger.info("✅ Router XAI chargé.")
except Exception as e:
    logger.error(f"❌ Erreur chargement router XAI: {e}", exc_info=True)


# ── Health check racine ───────────────────────────────────────────
@app.get("/health")
async def health_check():
    """Expert Health Check : Vérifie l'état de l'API et de ses dépendances critiques."""
    if not IS_HEALTHY:
        raise HTTPException(status_code=503, detail="Service Unhealthy (Simulated)")

    import socket
    health_status = {
        "service": "fastapi-backend",
        "status": "healthy",
        "container_id": socket.gethostname(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dependencies": {
            "mongodb": "unknown",
            "audit_service": "active"
        }
    }

    try:
        await db.command("ping")
        health_status["dependencies"]["mongodb"] = "connected"
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["dependencies"]["mongodb"] = f"error: {str(e)}"

    return health_status


@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "service": "XAI Anomaly Detection API", "version": "3.0.0"}


# ── Chaos Engineering Endpoints ───────────────────────────────────
# Finding SEC-02 (Audit Bancaire) : Ces endpoints nécessitent une authentification
# admin ET sont désactivés en production.

@app.get("/api/chaos/fail", tags=["Chaos"])
async def simulate_failure(request: Request):
    """⚠️ TEST ONLY — Requiert rôle admin. Désactivé en production."""
    _require_chaos_access(request)
    global IS_HEALTHY
    IS_HEALTHY = False
    return {"message": "Service is now UNHEALTHY (for testing — dev/uat only)"}


@app.get("/api/chaos/recover", tags=["Chaos"])
async def simulate_recovery(request: Request):
    """⚠️ TEST ONLY — Requiert rôle admin. Désactivé en production."""
    _require_chaos_access(request)
    global IS_HEALTHY
    IS_HEALTHY = True
    return {"message": "Service is now HEALTHY"}


def _require_chaos_access(request: Request):
    """
    Vérifie que :
    1. L'environnement n'est pas prod (Finding SEC-02)
    2. L'appelant est authentifié avec le rôle admin
    """
    if os.getenv("ENV", "dev").lower() == "prod":
        raise HTTPException(
            status_code=403,
            detail="🚫 Endpoint de chaos désactivé en production (Politique de sécurité bancaire)"
        )
    # Vérification du token JWT admin
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token d'authentification requis")
    try:
        from auth import decode_access_token
        from models.user_model import RoleEnum
        payload = decode_access_token(auth_header.removeprefix("Bearer ").strip())
        if not payload or payload.get("role") != RoleEnum.admin.value:
            raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Token invalide")


@app.get("/api/health", tags=["Health"])
async def api_health():
    if not IS_HEALTHY:
        raise HTTPException(status_code=503, detail="Service Unhealthy (Simulated)")
    return {
        "status": "ok",
        "service": "FastAPI Backend",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/health/monitoring", tags=["Health"])
async def monitoring_health():
    """Vérifie l'état des processus de monitoring."""
    status = monitoring_manager.get_status()
    return {
        "status": "ok" if all(s == "running" for s in status.values()) else "degraded",
        "processes": status
    }


# ── Entrée directe ────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info",
        timeout_keep_alive=300,
        limit_concurrency=10,
        limit_max_requests=1000,
    )