from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse
from bson import ObjectId
from typing import List
import subprocess, sys, os
from datetime import datetime, timezone

from models.user_model import RoleEnum
from schemas.user_schema import UserCreate, UserOut, LoginSchema, Token
from services.user_service import UserService
from auth import decode_access_token

router   = APIRouter()
service  = UserService()
security = HTTPBearer(auto_error=False)

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IA_DIR  = os.path.join(APP_DIR, "IA_anomaly_detection")

# ================================================================
# CONFIGURATION DES PIPELINES
# ================================================================

# Firewall
FIREWALL_SCRIPT      = os.path.join(IA_DIR, "FirewallReseauLogs.py")
FIREWALL_INFO_DIR    = os.path.join(IA_DIR, "Firewall_info")
FIREWALL_OUTPUT_CSV  = os.path.join(FIREWALL_INFO_DIR, "Detected_Anomalies.csv")
FIREWALL_ANOMALY_CSV = os.path.join(FIREWALL_INFO_DIR, "Detected_Anomalies_anomalies_only.csv")
FIREWALL_TEST_CSV    = os.path.join(IA_DIR, "Firewall_Logstest.csv")
FIREWALL_DONE_FLAG   = os.path.join(FIREWALL_INFO_DIR, ".pipeline_done")

# Database
DB_SCRIPT      = os.path.join(IA_DIR, "BaseDeDonnees.py")
DB_INFO_DIR    = os.path.join(IA_DIR, "DB_info")
DB_OUTPUT_CSV  = os.path.join(DB_INFO_DIR, "Detected_DB_Anomalies.csv")
DB_ANOMALY_CSV = os.path.join(DB_INFO_DIR, "Detected_DB_Anomalies_anomalies_only.csv")
DB_TEST_CSV    = os.path.join(IA_DIR, "BasedeDonneestest.csv")
DB_DONE_FLAG   = os.path.join(DB_INFO_DIR, ".pipeline_done")

# OS Infrastructure
OS_SCRIPT      = os.path.join(IA_DIR, "OS_Infrastructure.py")
OS_INFO_DIR    = os.path.join(IA_DIR, "OS_info")
OS_OUTPUT_CSV  = os.path.join(OS_INFO_DIR, "Detected_OS_Anomalies.csv")
OS_ANOMALY_CSV = os.path.join(OS_INFO_DIR, "Detected_OS_Anomalies_anomalies_only.csv")
OS_TEST_CSV    = os.path.join(IA_DIR, "OS&Infrastructure_test.csv")
OS_DONE_FLAG   = os.path.join(OS_INFO_DIR, ".pipeline_done")

# Applicatif
APP_SCRIPT      = os.path.join(IA_DIR, "LogsApplicatifs.py")
APP_INFO_DIR    = os.path.join(IA_DIR, "App_info")
APP_OUTPUT_CSV  = os.path.join(APP_INFO_DIR, "Detected_App_Anomalies.csv")
APP_ANOMALY_CSV = os.path.join(APP_INFO_DIR, "Detected_App_Anomalies_anomalies_only.csv")
APP_TEST_CSV    = os.path.join(IA_DIR, "Logs_Applicatifs_test.csv")
APP_DONE_FLAG   = os.path.join(APP_INFO_DIR, ".pipeline_done")

# API Logs
APILOGS_SCRIPT      = os.path.join(IA_DIR, "API_Logs.py")
APILOGS_INFO_DIR    = os.path.join(IA_DIR, "API_info")
APILOGS_OUTPUT_CSV  = os.path.join(APILOGS_INFO_DIR, "Detected_API_Anomalies.csv")
APILOGS_ANOMALY_CSV = os.path.join(APILOGS_INFO_DIR, "Detected_API_Anomalies_anomalies_only.csv")
APILOGS_TEST_CSV    = os.path.join(IA_DIR, "Testlogs.csv")
APILOGS_DONE_FLAG   = os.path.join(APILOGS_INFO_DIR, ".pipeline_done")

# ================================================================
# REGISTRE CENTRAL DES STATUTS
# ================================================================
# REGLE ABSOLUE : on ne fait JAMAIS _PIPELINE_REGISTRY["x"] = {...}
# On utilise TOUJOURS .update() ou accès par clé pour modifier EN PLACE.
# Raison : _run_pipeline_background garde la référence du dict original.
# Si on réassigne, le background thread pointe vers l'ancien dict
# et le statut affiché au frontend ne change jamais.
# ================================================================
_PIPELINE_REGISTRY = {
    "firewall": {"state": "idle", "message": "Aucune exécution lancée"},
    "database": {"state": "idle", "message": "Aucune exécution lancée"},
    "os":       {"state": "idle", "message": "Aucune exécution lancée"},
    "app":      {"state": "idle", "message": "Aucune exécution lancée"},
    "apilogs":  {"state": "idle", "message": "Aucune exécution lancée"},
}

def _get_status(name: str) -> dict:
    return _PIPELINE_REGISTRY[name]

def _update_status(name: str, **kwargs):
    """Modifie le dict de statut EN PLACE — ne jamais réassigner."""
    _PIPELINE_REGISTRY[name].update(kwargs)

def _clear_status(name: str, message: str = "Pipeline réinitialisé manuellement"):
    """Remet à idle EN PLACE."""
    st = _PIPELINE_REGISTRY[name]
    st.clear()
    st.update({"state": "idle", "message": message})


# ================================================================
# AUTO-RECOVERY AU DÉMARRAGE
# ================================================================
def _reset_stuck_pipelines():
    """Au redémarrage serveur, tout pipeline bloqué en running/pending → idle."""
    for name in _PIPELINE_REGISTRY:
        st = _PIPELINE_REGISTRY[name]
        if st.get("state") in ("running", "pending"):
            st.update({
                "state":   "idle",
                "message": "Pipeline réinitialisé (redémarrage serveur)",
            })

_reset_stuck_pipelines()


# ================================================================
# MOTEUR D'EXÉCUTION — FONCTION SYNCHRONE (DEF, PAS ASYNC DEF)
# ================================================================
# POURQUOI def et pas async def ?
# ─────────────────────────────
# FastAPI/Starlette's BackgroundTasks appelle les fonctions via
# anyio.to_thread.run_sync() si elles sont synchrones.
# Si on met async def, FastAPI crée une coroutine mais NE L'ATTEND PAS
# dans le thread background → la fonction se termine immédiatement
# sans exécuter le subprocess → le statut reste "running" indéfiniment.
#
# Avec def + subprocess.run() (bloquant), le thread reste occupé
# pendant toute la durée du pipeline, puis met le statut à "done".
# ================================================================

def _run_pipeline_background(name: str, script: str, test_csv: str,
                              label: str, done_flag: str):
    """
    Exécute un pipeline IA en subprocess bloquant.
    Met à jour _PIPELINE_REGISTRY[name] directement (même référence dict).
    Cette fonction DOIT rester synchrone (def, pas async def).
    """

    # ── Étape 1 : marquer comme "running" ──────────────────────
    _update_status(name,
                   state="running",
                   message=f"Pipeline {label} en cours d'exécution…",
                   started_at=datetime.now(timezone.utc).isoformat())

    # ── Étape 2 : vérifications préalables ─────────────────────
    if not os.path.exists(script):
        _update_status(name,
                       state="error",
                       message=f"Script introuvable : {script}",
                       error_at=datetime.now(timezone.utc).isoformat())
        return

    if not os.path.exists(test_csv):
        _update_status(name,
                       state="error",
                       message=f"Fichier test manquant : {os.path.basename(test_csv)}",
                       error_at=datetime.now(timezone.utc).isoformat())
        return

    # ── Étape 3 : supprimer l'ancien flag ──────────────────────
    if os.path.exists(done_flag):
        try:
            os.remove(done_flag)
        except OSError:
            pass

    # ── Étape 4 : lancer le subprocess (BLOQUANT) ──────────────
    try:
        r = subprocess.run(
            [sys.executable, script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3600,
            cwd=IA_DIR,
        )

        completed_at = datetime.now(timezone.utc).isoformat()

        if r.returncode == 0:
            summary = "\n".join(r.stdout.strip().splitlines()[-20:])
            _update_status(name,
                           state="done",
                           message=f"Pipeline {label} terminé avec succès",
                           summary=summary,
                           completed_at=completed_at)
        else:
            full_output = ""
            if r.stdout.strip():
                full_output += (
                    "=== STDOUT ===\n"
                    + "\n".join(r.stdout.strip().splitlines()[-50:])
                    + "\n\n"
                )
            if r.stderr.strip():
                full_output += f"=== STDERR ===\n{r.stderr.strip()}"
            _update_status(name,
                           state="error",
                           message=f"Pipeline {label} échoué (code={r.returncode})",
                           stderr=full_output or "(aucune sortie)",
                           error_at=completed_at)

    except subprocess.TimeoutExpired:
        _update_status(name,
                       state="error",
                       message=f"Pipeline {label} : timeout > 1 heure",
                       error_at=datetime.now(timezone.utc).isoformat())
    except Exception as e:
        _update_status(name,
                       state="error",
                       message=f"Pipeline {label} : erreur inattendue : {e}",
                       error_at=datetime.now(timezone.utc).isoformat())


# ================================================================
# HELPERS COMMUNS
# ================================================================

async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Token manquant")
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Token invalide")
    user_id = payload.get("sub")
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="ID invalide dans le token")
    user = await service.collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    user["id"] = str(user["_id"])
    return user


async def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != RoleEnum.admin.value:
        raise HTTPException(status_code=403, detail="Accès admin uniquement")
    return current_user


def _build_results(pipeline_name: str, output_dir: str,
                   anomaly_csv: str, test_csv: str):
    """
    Lit directement le CSV — ne vérifie PAS le statut en mémoire.
    Fonctionne même après redémarrage serveur.
    """
    import pandas as pd
    if not os.path.exists(anomaly_csv):
        raise HTTPException(
            status_code=404,
            detail="Aucun résultat disponible. Lancez le pipeline d'abord.",
        )
    df = pd.read_csv(anomaly_csv)
    total = (
        sum(1 for _ in open(test_csv, encoding="utf-8")) - 1
        if os.path.exists(test_csv)
        else len(df)
    )
    return {
        "pipeline":   pipeline_name,
        "output_dir": output_dir,
        "stats": {
            "total_processed": total,
            "total_anomalies": len(df),
            "anomaly_rate":    round(len(df) / total * 100, 2) if total > 0 else 0,
            "critical_alerts": int((df["Risk"] >= 8).sum()) if "Risk" in df.columns else 0,
        },
        "distributions": {
            "by_type": (
                df["Anomaly_type"].value_counts().to_dict()
                if "Anomaly_type" in df.columns else {}
            ),
            "by_vote": (
                {
                    "Unanime (3/3)":     int((df["ensemble_votes"] == 3).sum()),
                    "Majoritaire (2/3)": int((df["ensemble_votes"] == 2).sum()),
                    "Faible (1/3)":      int((df["ensemble_votes"] == 1).sum()),
                }
                if "ensemble_votes" in df.columns else {}
            ),
        },
        "top20": (
            df.sort_values(["Risk", "composite_score"], ascending=False)
              .head(20)
              .to_dict(orient="records")
            if "Risk" in df.columns and "composite_score" in df.columns
            else []
        ),
    }


async def _upload_csv(file, dest_path: str,
                      filename_label: str, next_route: str):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Seuls les .csv sont acceptés.")
    contents = await file.read()
    if len(contents) > 500 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (max 500 Mo).")
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, "wb") as f:
        f.write(contents)
    return {
        "message":       f"Fichier {filename_label} uploadé",
        "filename":      os.path.basename(dest_path),
        "saved_to":      dest_path,
        "size_kb":       round(len(contents) / 1024, 1),
        "original_name": file.filename,
        "next_step":     next_route,
    }


def _csv_info(csv_path: str, label: str):
    if not os.path.exists(csv_path):
        return {"exists": False, "message": f"Aucun fichier {label} présent."}
    stat = os.stat(csv_path)
    try:
        import pandas as pd
        df   = pd.read_csv(csv_path, nrows=0)
        cols = list(df.columns)
        rows = sum(1 for _ in open(csv_path, encoding="utf-8")) - 1
    except Exception:
        cols, rows = [], -1
    return {
        "exists":      True,
        "filename":    os.path.basename(csv_path),
        "size_kb":     round(stat.st_size / 1024, 1),
        "rows":        rows,
        "columns":     cols,
        "modified_at": stat.st_mtime,
    }


def _pipeline_run_guard(name: str, test_csv: str, label: str):
    """Vérifie qu'on peut lancer. Met à 'pending' si OK. Lève HTTPException sinon."""
    if not os.path.exists(test_csv):
        raise HTTPException(
            status_code=400,
            detail=f"{os.path.basename(test_csv)} manquant.",
        )
    current_state = _get_status(name).get("state")
    if current_state in ("running", "pending"):
        raise HTTPException(
            status_code=409,
            detail=f"Pipeline {label} déjà en cours (état: {current_state}).",
        )
    _update_status(name,
                   state="pending",
                   message=f"Pipeline {label} initialisé, démarrage en cours…",
                   started_at=datetime.now(timezone.utc).isoformat())


# ================================================================
# AUTH ROUTES
# ================================================================

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(user: UserCreate):
    return await service.signup(user)

@router.post("/login")
async def login(form_data: LoginSchema):
    return await service.login(form_data.email, form_data.password)

@router.post("/forgot-password")
async def forgot_password(data: dict):
    email = data.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email requis")
    return await service.forgot_password(email)

@router.post("/reset-password")
async def reset_password(data: dict):
    email        = data.get("email")
    code         = data.get("code")
    new_password = data.get("new_password")
    if not all([email, code, new_password]):
        raise HTTPException(status_code=400,
                            detail="Email, code et nouveau mot de passe requis")
    return await service.reset_password(email, code, new_password)


# ================================================================
# USER PROFILE (SELF)
# ================================================================

@router.get("/users/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return await service.get_my_profile(current_user["id"])

@router.put("/users/me")
async def update_my_profile(data: dict,
                             current_user: dict = Depends(get_current_user)):
    return await service.update_my_profile(current_user["id"], data)

@router.put("/users/me/password")
async def change_my_password(data: dict,
                              current_user: dict = Depends(get_current_user)):
    old_password = data.get("old_password")
    new_password = data.get("new_password")
    if not old_password or not new_password:
        raise HTTPException(status_code=400,
                            detail="Ancien et nouveau mot de passe requis")
    return await service.change_my_password(
        current_user["id"], old_password, new_password)

@router.post("/users/me/face-photo")
async def upload_face_photo(data: dict,
                             current_user: dict = Depends(get_current_user)):
    image_b64 = data.get("image")
    if not image_b64:
        raise HTTPException(status_code=400, detail="Image requise (base64)")
    return await service.upload_face_photo(current_user["id"], image_b64)

@router.delete("/users/me/face-photo")
async def delete_face_photo(current_user: dict = Depends(get_current_user)):
    return await service.delete_face_photo(current_user["id"])


# ================================================================
# USER MANAGEMENT (ADMIN ONLY)
# ================================================================

@router.get("/users")
async def list_users(admin=Depends(require_admin)):
    return await service.list_users()

@router.post("/users")
async def create_user_by_admin(data: dict, admin=Depends(require_admin)):
    return await service.create_user_by_admin(data)

@router.put("/users/{user_id}/activate")
async def activate_user(user_id: str, admin=Depends(require_admin)):
    return await service.activate_user(user_id)

@router.put("/users/{user_id}/deactivate")
async def deactivate_user(user_id: str, admin=Depends(require_admin)):
    return await service.deactivate_user(user_id)

@router.put("/users/{user_id}")
async def update_user(user_id: str, data: dict,
                      admin=Depends(require_admin)):
    return await service.update_user(user_id, data)

@router.put("/users/{user_id}/password")
async def update_password(user_id: str, data: dict,
                           current_user: dict = Depends(get_current_user)):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="ID invalide")
    new_password = data.get("password")
    if not new_password:
        raise HTTPException(status_code=400, detail="Mot de passe requis")
    if (current_user["role"] != RoleEnum.admin.value
            and current_user["id"] != user_id):
        raise HTTPException(status_code=403, detail="Action non autorisée")
    return await service.update_password(user_id, new_password)

@router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin=Depends(require_admin)):
    return await service.delete_user(user_id)


# ================================================================
# PIPELINE FIREWALL
# ================================================================

@router.post("/firewall/upload-test-csv", tags=["Pipeline Firewall"])
async def firewall_upload(file: UploadFile = File(...),
                          current_user: dict = Depends(get_current_user)):
    return await _upload_csv(file, FIREWALL_TEST_CSV, "Firewall", "POST /firewall/run")

@router.get("/firewall/test-csv-info", tags=["Pipeline Firewall"])
async def firewall_csv_info(current_user: dict = Depends(get_current_user)):
    return _csv_info(FIREWALL_TEST_CSV, "Firewall")

@router.post("/firewall/run", status_code=status.HTTP_202_ACCEPTED, tags=["Pipeline Firewall"])
async def firewall_run(background_tasks: BackgroundTasks,
                       current_user: dict = Depends(get_current_user)):
    _pipeline_run_guard("firewall", FIREWALL_TEST_CSV, "Firewall")
    background_tasks.add_task(_run_pipeline_background,
        "firewall", FIREWALL_SCRIPT, FIREWALL_TEST_CSV, "Firewall", FIREWALL_DONE_FLAG)
    return {"message": "Pipeline Firewall lancé",
            "status_url": "/firewall/status", "results_url": "/firewall/results"}

@router.get("/firewall/status", tags=["Pipeline Firewall"])
async def firewall_status(current_user: dict = Depends(get_current_user)):
    return dict(_get_status("firewall"))

@router.get("/firewall/results", tags=["Pipeline Firewall"])
async def firewall_results(current_user: dict = Depends(get_current_user)):
    return _build_results("firewall", FIREWALL_INFO_DIR, FIREWALL_ANOMALY_CSV, FIREWALL_TEST_CSV)

@router.get("/firewall/download", tags=["Pipeline Firewall"])
async def firewall_dl(current_user: dict = Depends(get_current_user)):
    if not os.path.exists(FIREWALL_OUTPUT_CSV): raise HTTPException(404, "Aucun fichier.")
    return FileResponse(FIREWALL_OUTPUT_CSV, media_type="text/csv", filename="Detected_Anomalies.csv")

@router.get("/firewall/download/anomalies", tags=["Pipeline Firewall"])
async def firewall_dl_anomalies(current_user: dict = Depends(get_current_user)):
    if not os.path.exists(FIREWALL_ANOMALY_CSV): raise HTTPException(404, "Aucun fichier.")
    return FileResponse(FIREWALL_ANOMALY_CSV, media_type="text/csv", filename="Detected_Anomalies_anomalies_only.csv")

@router.post("/firewall/reset", tags=["Pipeline Firewall"])
async def firewall_reset(current_user: dict = Depends(get_current_user)):
    _clear_status("firewall")
    return dict(_get_status("firewall"))


# ================================================================
# PIPELINE DATABASE
# ================================================================

@router.post("/database/upload-test-csv", tags=["Pipeline Database"])
async def db_upload(file: UploadFile = File(...),
                    current_user: dict = Depends(get_current_user)):
    return await _upload_csv(file, DB_TEST_CSV, "Database", "POST /database/run")

@router.get("/database/test-csv-info", tags=["Pipeline Database"])
async def db_csv_info(current_user: dict = Depends(get_current_user)):
    return _csv_info(DB_TEST_CSV, "Database")

@router.post("/database/run", status_code=status.HTTP_202_ACCEPTED, tags=["Pipeline Database"])
async def db_run(background_tasks: BackgroundTasks,
                 current_user: dict = Depends(get_current_user)):
    _pipeline_run_guard("database", DB_TEST_CSV, "Database")
    background_tasks.add_task(_run_pipeline_background,
        "database", DB_SCRIPT, DB_TEST_CSV, "Database", DB_DONE_FLAG)
    return {"message": "Pipeline Database lancé",
            "status_url": "/database/status", "results_url": "/database/results"}

@router.get("/database/status", tags=["Pipeline Database"])
async def db_status(current_user: dict = Depends(get_current_user)):
    return dict(_get_status("database"))

@router.get("/database/results", tags=["Pipeline Database"])
async def db_results(current_user: dict = Depends(get_current_user)):
    return _build_results("database", DB_INFO_DIR, DB_ANOMALY_CSV, DB_TEST_CSV)

@router.get("/database/download", tags=["Pipeline Database"])
async def db_dl(current_user: dict = Depends(get_current_user)):
    if not os.path.exists(DB_OUTPUT_CSV): raise HTTPException(404, "Aucun fichier.")
    return FileResponse(DB_OUTPUT_CSV, media_type="text/csv", filename="Detected_DB_Anomalies.csv")

@router.get("/database/download/anomalies", tags=["Pipeline Database"])
async def db_dl_anomalies(current_user: dict = Depends(get_current_user)):
    if not os.path.exists(DB_ANOMALY_CSV): raise HTTPException(404, "Aucun fichier.")
    return FileResponse(DB_ANOMALY_CSV, media_type="text/csv", filename="Detected_DB_Anomalies_anomalies_only.csv")

@router.post("/database/reset", tags=["Pipeline Database"])
async def db_reset(current_user: dict = Depends(get_current_user)):
    _clear_status("database")
    return dict(_get_status("database"))


# ================================================================
# PIPELINE OS INFRASTRUCTURE
# ================================================================

@router.post("/os/upload-test-csv", tags=["Pipeline OS Infrastructure"])
async def os_upload(file: UploadFile = File(...),
                    current_user: dict = Depends(get_current_user)):
    return await _upload_csv(file, OS_TEST_CSV, "OS Infrastructure", "POST /os/run")

@router.get("/os/test-csv-info", tags=["Pipeline OS Infrastructure"])
async def os_csv_info(current_user: dict = Depends(get_current_user)):
    return _csv_info(OS_TEST_CSV, "OS Infrastructure")

@router.post("/os/run", status_code=status.HTTP_202_ACCEPTED, tags=["Pipeline OS Infrastructure"])
async def os_run(background_tasks: BackgroundTasks,
                 current_user: dict = Depends(get_current_user)):
    _pipeline_run_guard("os", OS_TEST_CSV, "OS Infrastructure")
    background_tasks.add_task(_run_pipeline_background,
        "os", OS_SCRIPT, OS_TEST_CSV, "OS Infrastructure", OS_DONE_FLAG)
    return {"message": "Pipeline OS lancé",
            "status_url": "/os/status", "results_url": "/os/results"}

@router.get("/os/status", tags=["Pipeline OS Infrastructure"])
async def os_status(current_user: dict = Depends(get_current_user)):
    return dict(_get_status("os"))

@router.get("/os/results", tags=["Pipeline OS Infrastructure"])
async def os_results(current_user: dict = Depends(get_current_user)):
    return _build_results("os_infrastructure", OS_INFO_DIR, OS_ANOMALY_CSV, OS_TEST_CSV)

@router.get("/os/download", tags=["Pipeline OS Infrastructure"])
async def os_dl(current_user: dict = Depends(get_current_user)):
    if not os.path.exists(OS_OUTPUT_CSV): raise HTTPException(404, "Aucun fichier.")
    return FileResponse(OS_OUTPUT_CSV, media_type="text/csv", filename="Detected_OS_Anomalies.csv")

@router.get("/os/download/anomalies", tags=["Pipeline OS Infrastructure"])
async def os_dl_anomalies(current_user: dict = Depends(get_current_user)):
    if not os.path.exists(OS_ANOMALY_CSV): raise HTTPException(404, "Aucun fichier.")
    return FileResponse(OS_ANOMALY_CSV, media_type="text/csv", filename="Detected_OS_Anomalies_anomalies_only.csv")

@router.post("/os/reset", tags=["Pipeline OS Infrastructure"])
async def os_reset(current_user: dict = Depends(get_current_user)):
    _clear_status("os")
    return dict(_get_status("os"))


# ================================================================
# PIPELINE APPLICATIF
# ================================================================

@router.post("/app/upload-test-csv", tags=["Pipeline Applicatif"])
async def app_upload(file: UploadFile = File(...),
                     current_user: dict = Depends(get_current_user)):
    return await _upload_csv(file, APP_TEST_CSV, "Applicatif", "POST /app/run")

@router.get("/app/test-csv-info", tags=["Pipeline Applicatif"])
async def app_csv_info(current_user: dict = Depends(get_current_user)):
    return _csv_info(APP_TEST_CSV, "Applicatif")

@router.post("/app/run", status_code=status.HTTP_202_ACCEPTED, tags=["Pipeline Applicatif"])
async def app_run(background_tasks: BackgroundTasks,
                  current_user: dict = Depends(get_current_user)):
    _pipeline_run_guard("app", APP_TEST_CSV, "Applicatif")
    background_tasks.add_task(_run_pipeline_background,
        "app", APP_SCRIPT, APP_TEST_CSV, "Applicatif", APP_DONE_FLAG)
    return {"message": "Pipeline Applicatif lancé",
            "status_url": "/app/status", "results_url": "/app/results"}

@router.get("/app/status", tags=["Pipeline Applicatif"])
async def app_status(current_user: dict = Depends(get_current_user)):
    return dict(_get_status("app"))

@router.get("/app/results", tags=["Pipeline Applicatif"])
async def app_results(current_user: dict = Depends(get_current_user)):
    return _build_results("applicatif", APP_INFO_DIR, APP_ANOMALY_CSV, APP_TEST_CSV)

@router.get("/app/download", tags=["Pipeline Applicatif"])
async def app_dl(current_user: dict = Depends(get_current_user)):
    if not os.path.exists(APP_OUTPUT_CSV): raise HTTPException(404, "Aucun fichier.")
    return FileResponse(APP_OUTPUT_CSV, media_type="text/csv", filename="Detected_App_Anomalies.csv")

@router.get("/app/download/anomalies", tags=["Pipeline Applicatif"])
async def app_dl_anomalies(current_user: dict = Depends(get_current_user)):
    if not os.path.exists(APP_ANOMALY_CSV): raise HTTPException(404, "Aucun fichier.")
    return FileResponse(APP_ANOMALY_CSV, media_type="text/csv", filename="Detected_App_Anomalies_anomalies_only.csv")

@router.post("/app/reset", tags=["Pipeline Applicatif"])
async def app_reset(current_user: dict = Depends(get_current_user)):
    _clear_status("app")
    return dict(_get_status("app"))


# ================================================================
# PIPELINE API LOGS
# ================================================================

@router.post("/apilogs/upload-test-csv", tags=["Pipeline API Logs"])
async def apilogs_upload(file: UploadFile = File(...),
                         current_user: dict = Depends(get_current_user)):
    return await _upload_csv(file, APILOGS_TEST_CSV, "API Logs", "POST /apilogs/run")

@router.get("/apilogs/test-csv-info", tags=["Pipeline API Logs"])
async def apilogs_csv_info(current_user: dict = Depends(get_current_user)):
    return _csv_info(APILOGS_TEST_CSV, "API Logs")

@router.post("/apilogs/run", status_code=status.HTTP_202_ACCEPTED, tags=["Pipeline API Logs"])
async def apilogs_run(background_tasks: BackgroundTasks,
                      current_user: dict = Depends(get_current_user)):
    """
    Lance le pipeline API Logs.
    _run_pipeline_background est DEF (synchrone) — exécutée dans un thread
    par anyio/Starlette → le subprocess bloque le thread jusqu'à la fin
    → le statut est mis à jour correctement.
    """
    _pipeline_run_guard("apilogs", APILOGS_TEST_CSV, "API Logs")
    background_tasks.add_task(
        _run_pipeline_background,
        "apilogs", APILOGS_SCRIPT, APILOGS_TEST_CSV, "API Logs", APILOGS_DONE_FLAG,
    )
    return {
        "message":     "Pipeline API Logs lancé avec succès",
        "status_url":  "/apilogs/status",
        "results_url": "/apilogs/results",
        "started_at":  _get_status("apilogs").get("started_at"),
    }

@router.get("/apilogs/status", tags=["Pipeline API Logs"])
async def apilogs_status(current_user: dict = Depends(get_current_user)):
    """
    Statut courant : idle | pending | running | done | error
    Quand done : enrichi avec l'existence des fichiers de sortie.
    """
    st = dict(_get_status("apilogs"))

    if st.get("state") == "done":
        st["output_csv_exists"]  = os.path.exists(APILOGS_OUTPUT_CSV)
        st["anomaly_csv_exists"] = os.path.exists(APILOGS_ANOMALY_CSV)
        if os.path.exists(APILOGS_DONE_FLAG):
            try:
                with open(APILOGS_DONE_FLAG, "r", encoding="utf-8") as f:
                    st["completed_run_ts"] = f.read().strip()
            except Exception:
                pass

    return st

@router.get("/apilogs/results", tags=["Pipeline API Logs"])
async def apilogs_results(current_user: dict = Depends(get_current_user)):
    """
    Lit les résultats depuis le CSV.
    Ne vérifie PAS le statut en mémoire → fonctionne après redémarrage.
    """
    return _build_results("api_logs", APILOGS_INFO_DIR,
                          APILOGS_ANOMALY_CSV, APILOGS_TEST_CSV)

@router.get("/apilogs/download", tags=["Pipeline API Logs"])
async def apilogs_dl(current_user: dict = Depends(get_current_user)):
    if not os.path.exists(APILOGS_OUTPUT_CSV):
        raise HTTPException(status_code=404, detail="Aucun fichier.")
    return FileResponse(APILOGS_OUTPUT_CSV, media_type="text/csv",
                        filename="Detected_API_Anomalies.csv")

@router.get("/apilogs/download/anomalies", tags=["Pipeline API Logs"])
async def apilogs_dl_anomalies(current_user: dict = Depends(get_current_user)):
    if not os.path.exists(APILOGS_ANOMALY_CSV):
        raise HTTPException(status_code=404, detail="Aucun fichier.")
    return FileResponse(APILOGS_ANOMALY_CSV, media_type="text/csv",
                        filename="Detected_API_Anomalies_anomalies_only.csv")

@router.post("/apilogs/reset", tags=["Pipeline API Logs"])
async def apilogs_reset(current_user: dict = Depends(get_current_user)):
    """Remet à idle — utile si bloqué en running/pending."""
    _clear_status("apilogs", message="Pipeline réinitialisé manuellement")
    return dict(_get_status("apilogs"))


# ================================================================
# MONITORING GLOBAL
# ================================================================

@router.get("/pipelines/all-status", tags=["Pipeline Monitoring"])
async def all_pipelines_status(current_user: dict = Depends(get_current_user)):
    """Statut de tous les pipelines en un seul appel."""
    return {
        name: dict(st)
        for name, st in _PIPELINE_REGISTRY.items()
    } | {"timestamp": datetime.now(timezone.utc).isoformat()}