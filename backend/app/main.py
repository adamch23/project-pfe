# ================================================================
# main.py — FastAPI Entry Point (Version robuste)
# ================================================================

import logging
import sys
import signal
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Configuration du logging avec flush immédiat
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("server.log", encoding="utf-8")
    ],
)
logger = logging.getLogger(__name__)

# Forcer le flush des logs
sys.stdout.reconfigure(line_buffering=True)


# ── Lifespan ─────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("=" * 60)
    logger.info("=== Démarrage du serveur FastAPI ===")
    
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

    logger.info("=== Serveur prêt ===")
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("=== Arrêt du serveur FastAPI ===")


# ── Application ───────────────────────────────────────────────────
app = FastAPI(
    title="XAI Anomaly Detection API",
    version="2.0.0",
    description="API d'analyse des anomalies avec IA explicable (RAG + Ollama)",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Middleware pour logger toutes les requêtes ────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"📥 {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        logger.info(f"📤 {response.status_code} ← {request.url.path}")
        return response
    except Exception as e:
        logger.error(f"❌ Erreur sur {request.url.path}: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": f"Erreur interne: {str(e)}"}
        )


# ── Global exception handler ──────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"❌ Exception non gérée sur {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Erreur interne: {str(exc)}"},
    )


# ── Routers ───────────────────────────────────────────────────────
try:
    from controllers import user_controller
    app.include_router(user_controller.router, prefix="/api", tags=["users"])
    logger.info("✅ Router users chargé.")
except Exception as e:
    logger.error(f"❌ Erreur chargement router users: {e}", exc_info=True)

try:
    from explainable_AI.explainable_AI import router as xai_router
    app.include_router(xai_router, prefix="/api/xai", tags=["Explainable AI"])
    logger.info("✅ Router XAI chargé.")
except Exception as e:
    logger.error(f"❌ Erreur chargement router XAI: {e}", exc_info=True)


# ── Health check racine ───────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "service": "XAI Anomaly Detection API", "version": "2.0.0"}


@app.get("/api/health", tags=["Health"])
async def api_health():
    return {"status": "ok", "timestamp": str(__import__("datetime").datetime.now())}


# ── Entrée directe ────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    
    # Configuration pour éviter les timeouts
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,  # Désactiver le reload pour éviter les problèmes
        log_level="info",
        timeout_keep_alive=300,  # 5 minutes pour les requêtes longues
        limit_concurrency=10,
        limit_max_requests=1000,
    )