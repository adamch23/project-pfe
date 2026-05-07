# ================================================================
# explainable_AI.py - Routes API améliorées
# ================================================================

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer(auto_error=False)

PIPELINES = ["firewall", "os", "app", "apilogs", "database"]
PIPELINE_LABELS = {
    "firewall": "Firewall / Réseau",
    "os":       "OS & Infrastructure",
    "app":      "Logs Applicatifs",
    "apilogs":  "API Logs",
    "database": "Base de Données",
}

# Stockage mémoire des statuts
_analysis_status = {
    p: {"state": "idle", "message": "Aucune analyse", "progress": 0}
    for p in PIPELINES
}

RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


# ── Helpers ──────────────────────────────────────────────────────
def _get_engine():
    try:
        from explainable_AI.RAG import get_rag_engine
    except ImportError:
        from RAG import get_rag_engine
    return get_rag_engine()


async def _get_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Token manquant")
    try:
        from auth import decode_access_token
        payload = decode_access_token(credentials.credentials)
        if not payload:
            raise HTTPException(status_code=401, detail="Token invalide")
        return payload
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Token invalide")


# ================================================================
# TÂCHE D'ANALYSE EN ARRIÈRE-PLAN
# ================================================================
def _run_analysis(pipeline: str):
    _analysis_status[pipeline] = {
        "state": "running",
        "message": "Initialisation de l'analyse...",
        "progress": 0,
    }

    try:
        engine = _get_engine()

        def progress_cb(current_type: str, done: int, total: int):
            percent = int((done / total) * 100) if total > 0 else 0
            _analysis_status[pipeline] = {
                "state":        "running",
                "message":      f"Analyse : {current_type} ({done}/{total})",
                "progress":     percent,
                "current_type": current_type,
                "done":         done,
                "total":        total,
            }

        engine._progress_callback = progress_cb
        result = engine.analyze_pipeline(pipeline)
        engine._progress_callback = None

        total_anomalies = result.get("global_stats", {}).get("total_anomalies", 0)
        types_analyzed  = len(result.get("type_analyses", {}))

        _analysis_status[pipeline] = {
            "state":    "done",
            "message":  f"Analyse terminée — {total_anomalies} anomalies, {types_analyzed} types",
            "progress": 100,
        }

        # Persister le statut
        status_file = RESULTS_DIR / f"{pipeline}_status.json"
        with open(status_file, "w") as f:
            json.dump(_analysis_status[pipeline], f)

    except Exception as e:
        logger.error(f"Analyse {pipeline} échouée: {e}")
        _analysis_status[pipeline] = {
            "state":    "error",
            "message":  str(e),
            "progress": 0,
        }


# ================================================================
# ROUTES
# ================================================================

@router.get("/health")
async def health():
    """Vérifie l'état des services (Ollama, MongoDB)."""
    try:
        engine = _get_engine()
        return {
            "service":   "Explainable AI",
            "status":    "ok",
            "ollama":    engine.check_ollama(),
            "mongodb":   engine.check_mongodb(),
            "pipelines": PIPELINES,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {"status": "degraded", "error": str(e)}


@router.post("/{pipeline}/analyze")
async def analyze_pipeline(
    pipeline: str,
    background_tasks: BackgroundTasks,
    _user=Depends(_get_user),
):
    """Lance l'analyse IA de TOUTES les anomalies du pipeline en arrière-plan (sans limite)."""
    if pipeline not in PIPELINES:
        raise HTTPException(404, f"Pipeline '{pipeline}' inconnu. "
                                 f"Pipelines disponibles : {PIPELINES}")

    if _analysis_status[pipeline].get("state") == "running":
        raise HTTPException(409, "Une analyse est déjà en cours pour ce pipeline")

    engine = _get_engine()

    mongo_info = engine.check_mongodb()
    if not mongo_info.get("mongodb_running"):
        raise HTTPException(503, "MongoDB inaccessible — vérifiez la connexion")

    ollama_info = engine.check_ollama()
    if not ollama_info.get("ollama_running"):
        raise HTTPException(503, "Ollama inaccessible — vérifiez que le service tourne")

    # Afficher le nombre réel d'anomalies dans le statut initial
    try:
        config_map = {
            "firewall": ("firewall_db", "detected_anomalies"),
            "os":       ("OS_db", "detected_os_anomalies"),
            "app":      ("APP_db", "detected_app_anomalies"),
            "apilogs":  ("API_db", "detected_api_anomalies"),
            "database": ("basededonne_db", "detected_db_anomalies"),
        }
        db_name, coll_name = config_map[pipeline]
        total = engine._get_mongo_client()[db_name][coll_name].count_documents({"is_anomaly": 1})
        init_msg = f"En file d'attente... {total} anomalies détectées"
    except Exception:
        total = "?"
        init_msg = "En file d'attente..."

    _analysis_status[pipeline] = {
        "state":    "pending",
        "message":  init_msg,
        "progress": 0,
        "total_anomalies": total,
    }
    background_tasks.add_task(_run_analysis, pipeline)

    return {
        "message":     f"Analyse lancée pour {PIPELINE_LABELS[pipeline]}",
        "pipeline":    pipeline,
        "status_url":  f"/api/xai/{pipeline}/status",
        "results_url": f"/api/xai/{pipeline}/results",
    }


@router.get("/{pipeline}/status")
async def get_status(pipeline: str, _user=Depends(_get_user)):
    """Retourne l'état courant de l'analyse (idle / pending / running / done / error)."""
    if pipeline not in PIPELINES:
        raise HTTPException(404, "Pipeline inconnu")
    return _analysis_status[pipeline]


@router.get("/{pipeline}/results")
async def get_results(pipeline: str, _user=Depends(_get_user)):
    """
    Retourne les résultats complets de la dernière analyse :
    - global_stats      : statistiques globales
    - type_analyses     : rapport IA par type (cause, explication, recommandations…)
    - all_anomalies     : TOUTES les anomalies individuelles enrichies avec le rapport de leur type
    """
    if pipeline not in PIPELINES:
        raise HTTPException(404, "Pipeline inconnu")

    engine = _get_engine()
    result = engine.get_cached_result(pipeline)

    if not result:
        raise HTTPException(
            404,
            "Aucun résultat disponible. Lancez d'abord l'analyse via POST /{pipeline}/analyze"
        )

    return result


@router.get("/{pipeline}/anomaly/{anomaly_id}")
async def get_anomaly_detail(
    pipeline: str, anomaly_id: str, _user=Depends(_get_user)
):
    """
    Retourne le détail complet d'une anomalie individuelle,
    enrichi avec le rapport IA de son type.
    """
    if pipeline not in PIPELINES:
        raise HTTPException(404, "Pipeline inconnu")

    engine = _get_engine()
    result = engine.get_cached_result(pipeline)

    if not result:
        raise HTTPException(404, "Aucune analyse disponible")

    for anomaly in result.get("all_anomalies", []):
        if anomaly.get("_id") == anomaly_id or anomaly.get("anomaly_id") == anomaly_id:
            return anomaly

    raise HTTPException(404, f"Anomalie '{anomaly_id}' non trouvée dans le pipeline '{pipeline}'")


@router.get("/{pipeline}/type/{anomaly_type}")
async def get_type_report(
    pipeline: str, anomaly_type: str, _user=Depends(_get_user)
):
    """Retourne le rapport IA complet pour un type d'anomalie spécifique."""
    if pipeline not in PIPELINES:
        raise HTTPException(404, "Pipeline inconnu")

    engine = _get_engine()
    result = engine.get_cached_result(pipeline)

    if not result:
        raise HTTPException(404, "Aucune analyse disponible")

    type_analyses = result.get("type_analyses", {})
    if anomaly_type not in type_analyses:
        # Recherche insensible à la casse
        for key in type_analyses:
            if key.lower() == anomaly_type.lower():
                return type_analyses[key]
        raise HTTPException(404, f"Type '{anomaly_type}' non trouvé")

    return type_analyses[anomaly_type]


@router.get("/correlation/{pipeline}")
async def get_type_correlation(pipeline: str, _user=Depends(_get_user)):
    """Retourne les statistiques de corrélation par type d'anomalie."""
    if pipeline not in PIPELINES:
        raise HTTPException(404, "Pipeline inconnu")

    engine = _get_engine()
    result = engine.get_cached_result(pipeline)

    if not result:
        raise HTTPException(404, "Aucune analyse disponible")

    return {
        "pipeline":       pipeline,
        "type_analyses":  {
            k: {
                "count":          v["count"],
                "risk_avg":       v.get("risk_avg", 0),
                "risk_max":       v.get("risk_max", 0),
                "critical_count": v.get("critical_count", 0),
                "rag_used":       v.get("rag_used", False),
            }
            for k, v in result.get("type_analyses", {}).items()
        },
        "global_stats":   result.get("global_stats", {}),
    }


@router.post("/reload-kb")
async def reload_kb(_user=Depends(_get_user)):
    """Recharge la base de connaissances (knowledge_base.py) dans les index vectoriels."""
    engine = _get_engine()
    ok = engine.reload_knowledge_base()
    return {
        "success": ok,
        "message": "Base de connaissances rechargée avec succès" if ok else "Échec du rechargement",
    }


@router.delete("/{pipeline}/results")
async def delete_results(pipeline: str, _user=Depends(_get_user)):
    """Supprime le fichier de résultats mis en cache pour un pipeline."""
    if pipeline not in PIPELINES:
        raise HTTPException(404, "Pipeline inconnu")

    result_file = RESULTS_DIR / f"{pipeline}_analysis.json"
    status_file = RESULTS_DIR / f"{pipeline}_status.json"

    deleted = []
    for f in (result_file, status_file):
        if f.exists():
            f.unlink()
            deleted.append(f.name)

    _analysis_status[pipeline] = {
        "state":    "idle",
        "message":  "Résultats supprimés",
        "progress": 0,
    }

    return {"deleted": deleted, "pipeline": pipeline}