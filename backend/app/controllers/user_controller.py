from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse
from bson import ObjectId
from typing import List
import subprocess, sys, os

from models.user_model import RoleEnum
from schemas.user_schema import UserCreate, UserOut, LoginSchema, Token
from services.user_service import UserService
from auth import decode_access_token

router   = APIRouter()
service  = UserService()
security = HTTPBearer(auto_error=False)

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IA_DIR  = os.path.join(APP_DIR, "IA_anomaly_detection")

# ── Pipeline constants (unchanged) ───────────────────────────────
FIREWALL_SCRIPT      = os.path.join(IA_DIR, "FirewallReseauLogs.py")
FIREWALL_INFO_DIR    = os.path.join(IA_DIR, "Firewall_info")
FIREWALL_OUTPUT_CSV  = os.path.join(FIREWALL_INFO_DIR, "Detected_Anomalies.csv")
FIREWALL_ANOMALY_CSV = os.path.join(FIREWALL_INFO_DIR, "Detected_Anomalies_anomalies_only.csv")
FIREWALL_TEST_CSV    = os.path.join(IA_DIR, "Firewall_Logstest.csv")
firewall_pipeline_status: dict = {"state": "idle", "message": "Aucune exécution lancée"}

DB_SCRIPT      = os.path.join(IA_DIR, "BaseDeDonnees.py")
DB_INFO_DIR    = os.path.join(IA_DIR, "DB_info")
DB_OUTPUT_CSV  = os.path.join(DB_INFO_DIR, "Detected_DB_Anomalies.csv")
DB_ANOMALY_CSV = os.path.join(DB_INFO_DIR, "Detected_DB_Anomalies_anomalies_only.csv")
DB_TEST_CSV    = os.path.join(IA_DIR, "BasedeDonneestest.csv")
db_pipeline_status: dict = {"state": "idle", "message": "Aucune exécution lancée"}

OS_SCRIPT      = os.path.join(IA_DIR, "OS_Infrastructure.py")
OS_INFO_DIR    = os.path.join(IA_DIR, "OS_info")
OS_OUTPUT_CSV  = os.path.join(OS_INFO_DIR, "Detected_OS_Anomalies.csv")
OS_ANOMALY_CSV = os.path.join(OS_INFO_DIR, "Detected_OS_Anomalies_anomalies_only.csv")
OS_TEST_CSV    = os.path.join(IA_DIR, "OS&Infrastructure_test.csv")
os_pipeline_status: dict = {"state": "idle", "message": "Aucune exécution lancée"}

APP_SCRIPT      = os.path.join(IA_DIR, "LogsApplicatifs.py")
APP_INFO_DIR    = os.path.join(IA_DIR, "App_info")
APP_OUTPUT_CSV  = os.path.join(APP_INFO_DIR, "Detected_App_Anomalies.csv")
APP_ANOMALY_CSV = os.path.join(APP_INFO_DIR, "Detected_App_Anomalies_anomalies_only.csv")
APP_TEST_CSV    = os.path.join(IA_DIR, "Logs_Applicatifs_test.csv")
app_pipeline_status: dict = {"state": "idle", "message": "Aucune exécution lancée"}

APILOGS_SCRIPT      = os.path.join(IA_DIR, "API_Logs.py")
APILOGS_INFO_DIR    = os.path.join(IA_DIR, "API_info")
APILOGS_OUTPUT_CSV  = os.path.join(APILOGS_INFO_DIR, "Detected_API_Anomalies.csv")
APILOGS_ANOMALY_CSV = os.path.join(APILOGS_INFO_DIR, "Detected_API_Anomalies_anomalies_only.csv")
APILOGS_TEST_CSV    = os.path.join(IA_DIR, "Testlogs.csv")
apilogs_pipeline_status: dict = {"state": "idle", "message": "Aucune exécution lancée"}


# ================================================================
# HELPERS
# ================================================================
def _run_pipeline_generic(script, test_csv, status_dict, label):
    if not os.path.exists(script):
        return {"state": "error", "message": f"Script introuvable : {script}"}
    if not os.path.exists(test_csv):
        return {"state": "error", "message": f"Fichier de test manquant : {os.path.basename(test_csv)}"}
    try:
        r = subprocess.run(
            [sys.executable, script], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=3600, cwd=IA_DIR
        )
        if r.returncode == 0:
            summary = "\n".join(r.stdout.strip().splitlines()[-20:])
            return {"state": "done", "message": f"Pipeline {label} terminé avec succès", "summary": summary}
        else:
            full_output = ""
            if r.stdout.strip():
                full_output += f"=== STDOUT ===\n{chr(10).join(r.stdout.strip().splitlines()[-50:])}\n\n"
            if r.stderr.strip():
                full_output += f"=== STDERR ===\n{r.stderr.strip()}"
            return {"state": "error", "message": f"Pipeline {label} échoué (code={r.returncode})", "stderr": full_output or "(aucune sortie)"}
    except subprocess.TimeoutExpired:
        return {"state": "error", "message": f"Pipeline {label} : timeout > 1 heure"}
    except Exception as e:
        return {"state": "error", "message": f"Pipeline {label} : erreur Python : {e}"}


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
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


def _build_results(pipeline_name, output_dir, anomaly_csv, test_csv):
    import pandas as pd
    if not os.path.exists(anomaly_csv):
        raise HTTPException(status_code=404, detail=f"Résultats introuvables. Relancez le pipeline.")
    df    = pd.read_csv(anomaly_csv)
    total = (sum(1 for _ in open(test_csv, encoding="utf-8")) - 1 if os.path.exists(test_csv) else len(df))
    return {
        "pipeline": pipeline_name, "output_dir": output_dir,
        "stats": {
            "total_processed": total, "total_anomalies": len(df),
            "anomaly_rate": round(len(df) / total * 100, 2) if total > 0 else 0,
            "critical_alerts": int((df["Risk"] >= 8).sum()),
        },
        "distributions": {
            "by_type": df["Anomaly_type"].value_counts().to_dict(),
            "by_vote": {
                "Unanime (3/3)": int((df["ensemble_votes"] == 3).sum()),
                "Majoritaire (2/3)": int((df["ensemble_votes"] == 2).sum()),
                "Faible (1/3)": int((df["ensemble_votes"] == 1).sum()),
            }
        },
        "top20": df.sort_values(["Risk", "composite_score"], ascending=False).head(20).to_dict(orient="records")
    }


async def _upload_csv(file, dest_path, filename_label, next_route):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Seuls les .csv sont acceptés.")
    contents = await file.read()
    if len(contents) > 500 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (max 500 Mo).")
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, "wb") as f:
        f.write(contents)
    return {"message": f"Fichier {filename_label} uploadé", "filename": os.path.basename(dest_path),
            "saved_to": dest_path, "size_kb": round(len(contents) / 1024, 1),
            "original_name": file.filename, "next_step": next_route}


def _csv_info(csv_path, label):
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
    return {"exists": True, "filename": os.path.basename(csv_path),
            "size_kb": round(stat.st_size / 1024, 1), "rows": rows, "columns": cols, "modified_at": stat.st_mtime}


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
    if not email: raise HTTPException(status_code=400, detail="Email requis")
    return await service.forgot_password(email)

@router.post("/reset-password")
async def reset_password(data: dict):
    email, code, new_password = data.get("email"), data.get("code"), data.get("new_password")
    if not all([email, code, new_password]):
        raise HTTPException(status_code=400, detail="Email, code et nouveau mot de passe requis")
    return await service.reset_password(email, code, new_password)


# ================================================================
# USER PROFILE (SELF) — admin + employer
# ================================================================

@router.get("/users/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    """Retourne le profil complet avec la photo de reconnaissance faciale."""
    return await service.get_my_profile(current_user["id"])

@router.put("/users/me")
async def update_my_profile(data: dict, current_user: dict = Depends(get_current_user)):
    """Met à jour email, first_name, last_name."""
    return await service.update_my_profile(current_user["id"], data)

@router.put("/users/me/password")
async def change_my_password(data: dict, current_user: dict = Depends(get_current_user)):
    """Change le mot de passe en vérifiant l'ancien."""
    old_password = data.get("old_password")
    new_password = data.get("new_password")
    if not old_password or not new_password:
        raise HTTPException(status_code=400, detail="Ancien et nouveau mot de passe requis")
    return await service.change_my_password(current_user["id"], old_password, new_password)

@router.post("/users/me/face-photo")
async def upload_face_photo(data: dict, current_user: dict = Depends(get_current_user)):
    """
    Upload la photo de référence pour la reconnaissance faciale.
    Body: { "image": "data:image/jpeg;base64,..." }
    """
    image_b64 = data.get("image")
    if not image_b64:
        raise HTTPException(status_code=400, detail="Image requise (base64)")
    return await service.upload_face_photo(current_user["id"], image_b64)

@router.delete("/users/me/face-photo")
async def delete_face_photo(current_user: dict = Depends(get_current_user)):
    """Supprime la photo de reconnaissance faciale."""
    return await service.delete_face_photo(current_user["id"])


# ================================================================
# USER MANAGEMENT (ADMIN)
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
async def update_user(user_id: str, data: dict, admin=Depends(require_admin)):
    return await service.update_user(user_id, data)

@router.put("/users/{user_id}/password")
async def update_password(user_id: str, data: dict, current_user: dict = Depends(get_current_user)):
    if not ObjectId.is_valid(user_id): raise HTTPException(status_code=400, detail="ID invalide")
    new_password = data.get("password")
    if not new_password: raise HTTPException(status_code=400, detail="Mot de passe requis")
    if current_user["role"] != RoleEnum.admin.value and current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Action non autorisée")
    return await service.update_password(user_id, new_password)

@router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin=Depends(require_admin)):
    return await service.delete_user(user_id)


# ================================================================
# PIPELINES (unchanged)
# ================================================================

@router.post("/firewall/upload-test-csv", tags=["Pipeline Firewall"])
async def firewall_upload(file: UploadFile = File(...), admin=Depends(require_admin)):
    return await _upload_csv(file, FIREWALL_TEST_CSV, "Firewall", "POST /firewall/run")

@router.get("/firewall/test-csv-info", tags=["Pipeline Firewall"])
async def firewall_csv_info(current_user: dict = Depends(get_current_user)):
    return _csv_info(FIREWALL_TEST_CSV, "Firewall")

def _run_firewall_pipeline():
    global firewall_pipeline_status
    firewall_pipeline_status = {"state": "running", "message": "Pipeline Firewall en cours..."}
    firewall_pipeline_status = _run_pipeline_generic(FIREWALL_SCRIPT, FIREWALL_TEST_CSV, firewall_pipeline_status, "Firewall")

@router.post("/firewall/run", status_code=status.HTTP_202_ACCEPTED, tags=["Pipeline Firewall"])
async def firewall_run(background_tasks: BackgroundTasks, admin=Depends(require_admin)):
    global firewall_pipeline_status
    if not os.path.exists(FIREWALL_TEST_CSV): raise HTTPException(400, "Firewall_Logstest.csv manquant.")
    if firewall_pipeline_status.get("state") == "running": raise HTTPException(409, "Déjà en cours.")
    firewall_pipeline_status = {"state": "pending", "message": "Démarrage..."}
    background_tasks.add_task(_run_firewall_pipeline)
    return {"message": "Pipeline Firewall lancé", "output_dir": FIREWALL_INFO_DIR, "status_url": "/firewall/status", "results_url": "/firewall/results"}

@router.get("/firewall/status", tags=["Pipeline Firewall"])
async def firewall_status(current_user: dict = Depends(get_current_user)): return firewall_pipeline_status

@router.get("/firewall/results", tags=["Pipeline Firewall"])
async def firewall_results(current_user: dict = Depends(get_current_user)):
    if firewall_pipeline_status.get("state") != "done": raise HTTPException(400, f"Pipeline non terminé.")
    return _build_results("firewall", FIREWALL_INFO_DIR, FIREWALL_ANOMALY_CSV, FIREWALL_TEST_CSV)

@router.get("/firewall/download", tags=["Pipeline Firewall"])
async def firewall_dl(admin=Depends(require_admin)):
    if not os.path.exists(FIREWALL_OUTPUT_CSV): raise HTTPException(404, "Aucun fichier.")
    return FileResponse(FIREWALL_OUTPUT_CSV, media_type="text/csv", filename="Detected_Anomalies.csv")

@router.get("/firewall/download/anomalies", tags=["Pipeline Firewall"])
async def firewall_dl_anomalies(admin=Depends(require_admin)):
    if not os.path.exists(FIREWALL_ANOMALY_CSV): raise HTTPException(404, "Aucun fichier.")
    return FileResponse(FIREWALL_ANOMALY_CSV, media_type="text/csv", filename="Detected_Anomalies_anomalies_only.csv")

@router.post("/database/upload-test-csv", tags=["Pipeline Database"])
async def db_upload(file: UploadFile = File(...), admin=Depends(require_admin)):
    return await _upload_csv(file, DB_TEST_CSV, "Database", "POST /database/run")

@router.get("/database/test-csv-info", tags=["Pipeline Database"])
async def db_csv_info(current_user: dict = Depends(get_current_user)): return _csv_info(DB_TEST_CSV, "Database")

def _run_db_pipeline():
    global db_pipeline_status
    db_pipeline_status = {"state": "running", "message": "Pipeline Database en cours..."}
    db_pipeline_status = _run_pipeline_generic(DB_SCRIPT, DB_TEST_CSV, db_pipeline_status, "Database")

@router.post("/database/run", status_code=status.HTTP_202_ACCEPTED, tags=["Pipeline Database"])
async def db_run(background_tasks: BackgroundTasks, admin=Depends(require_admin)):
    global db_pipeline_status
    if not os.path.exists(DB_TEST_CSV): raise HTTPException(400, "BasedeDonneestest.csv manquant.")
    if db_pipeline_status.get("state") == "running": raise HTTPException(409, "Déjà en cours.")
    db_pipeline_status = {"state": "pending", "message": "Démarrage..."}
    background_tasks.add_task(_run_db_pipeline)
    return {"message": "Pipeline Database lancé", "output_dir": DB_INFO_DIR, "status_url": "/database/status", "results_url": "/database/results"}

@router.get("/database/status", tags=["Pipeline Database"])
async def db_status(current_user: dict = Depends(get_current_user)): return db_pipeline_status

@router.get("/database/results", tags=["Pipeline Database"])
async def db_results(current_user: dict = Depends(get_current_user)):
    if db_pipeline_status.get("state") != "done": raise HTTPException(400, "Pipeline non terminé.")
    return _build_results("database", DB_INFO_DIR, DB_ANOMALY_CSV, DB_TEST_CSV)

@router.get("/database/download", tags=["Pipeline Database"])
async def db_dl(admin=Depends(require_admin)):
    if not os.path.exists(DB_OUTPUT_CSV): raise HTTPException(404, "Aucun fichier.")
    return FileResponse(DB_OUTPUT_CSV, media_type="text/csv", filename="Detected_DB_Anomalies.csv")

@router.get("/database/download/anomalies", tags=["Pipeline Database"])
async def db_dl_anomalies(admin=Depends(require_admin)):
    if not os.path.exists(DB_ANOMALY_CSV): raise HTTPException(404, "Aucun fichier.")
    return FileResponse(DB_ANOMALY_CSV, media_type="text/csv", filename="Detected_DB_Anomalies_anomalies_only.csv")

@router.post("/os/upload-test-csv", tags=["Pipeline OS Infrastructure"])
async def os_upload(file: UploadFile = File(...), admin=Depends(require_admin)):
    return await _upload_csv(file, OS_TEST_CSV, "OS Infrastructure", "POST /os/run")

@router.get("/os/test-csv-info", tags=["Pipeline OS Infrastructure"])
async def os_csv_info(current_user: dict = Depends(get_current_user)): return _csv_info(OS_TEST_CSV, "OS Infrastructure")

def _run_os_pipeline():
    global os_pipeline_status
    os_pipeline_status = {"state": "running", "message": "Pipeline OS en cours..."}
    os_pipeline_status = _run_pipeline_generic(OS_SCRIPT, OS_TEST_CSV, os_pipeline_status, "OS Infrastructure")

@router.post("/os/run", status_code=status.HTTP_202_ACCEPTED, tags=["Pipeline OS Infrastructure"])
async def os_run(background_tasks: BackgroundTasks, admin=Depends(require_admin)):
    global os_pipeline_status
    if not os.path.exists(OS_TEST_CSV): raise HTTPException(400, "OS&Infrastructure_test.csv manquant.")
    if os_pipeline_status.get("state") == "running": raise HTTPException(409, "Déjà en cours.")
    os_pipeline_status = {"state": "pending", "message": "Démarrage..."}
    background_tasks.add_task(_run_os_pipeline)
    return {"message": "Pipeline OS lancé", "output_dir": OS_INFO_DIR, "status_url": "/os/status", "results_url": "/os/results"}

@router.get("/os/status", tags=["Pipeline OS Infrastructure"])
async def os_status(current_user: dict = Depends(get_current_user)): return os_pipeline_status

@router.get("/os/results", tags=["Pipeline OS Infrastructure"])
async def os_results(current_user: dict = Depends(get_current_user)):
    if os_pipeline_status.get("state") != "done": raise HTTPException(400, "Pipeline non terminé.")
    return _build_results("os_infrastructure", OS_INFO_DIR, OS_ANOMALY_CSV, OS_TEST_CSV)

@router.get("/os/download", tags=["Pipeline OS Infrastructure"])
async def os_dl(admin=Depends(require_admin)):
    if not os.path.exists(OS_OUTPUT_CSV): raise HTTPException(404, "Aucun fichier.")
    return FileResponse(OS_OUTPUT_CSV, media_type="text/csv", filename="Detected_OS_Anomalies.csv")

@router.get("/os/download/anomalies", tags=["Pipeline OS Infrastructure"])
async def os_dl_anomalies(admin=Depends(require_admin)):
    if not os.path.exists(OS_ANOMALY_CSV): raise HTTPException(404, "Aucun fichier.")
    return FileResponse(OS_ANOMALY_CSV, media_type="text/csv", filename="Detected_OS_Anomalies_anomalies_only.csv")

@router.post("/app/upload-test-csv", tags=["Pipeline Applicatif"])
async def app_upload(file: UploadFile = File(...), admin=Depends(require_admin)):
    return await _upload_csv(file, APP_TEST_CSV, "Applicatif", "POST /app/run")

@router.get("/app/test-csv-info", tags=["Pipeline Applicatif"])
async def app_csv_info(current_user: dict = Depends(get_current_user)): return _csv_info(APP_TEST_CSV, "Applicatif")

def _run_app_pipeline():
    global app_pipeline_status
    app_pipeline_status = {"state": "running", "message": "Pipeline Applicatif en cours..."}
    app_pipeline_status = _run_pipeline_generic(APP_SCRIPT, APP_TEST_CSV, app_pipeline_status, "Applicatif")

@router.post("/app/run", status_code=status.HTTP_202_ACCEPTED, tags=["Pipeline Applicatif"])
async def app_run(background_tasks: BackgroundTasks, admin=Depends(require_admin)):
    global app_pipeline_status
    if not os.path.exists(APP_TEST_CSV): raise HTTPException(400, "Logs_Applicatifs_test.csv manquant.")
    if app_pipeline_status.get("state") == "running": raise HTTPException(409, "Déjà en cours.")
    app_pipeline_status = {"state": "pending", "message": "Démarrage..."}
    background_tasks.add_task(_run_app_pipeline)
    return {"message": "Pipeline Applicatif lancé", "output_dir": APP_INFO_DIR, "status_url": "/app/status", "results_url": "/app/results"}

@router.get("/app/status", tags=["Pipeline Applicatif"])
async def app_status(current_user: dict = Depends(get_current_user)): return app_pipeline_status

@router.get("/app/results", tags=["Pipeline Applicatif"])
async def app_results(current_user: dict = Depends(get_current_user)):
    if app_pipeline_status.get("state") != "done": raise HTTPException(400, "Pipeline non terminé.")
    return _build_results("applicatif", APP_INFO_DIR, APP_ANOMALY_CSV, APP_TEST_CSV)

@router.get("/app/download", tags=["Pipeline Applicatif"])
async def app_dl(admin=Depends(require_admin)):
    if not os.path.exists(APP_OUTPUT_CSV): raise HTTPException(404, "Aucun fichier.")
    return FileResponse(APP_OUTPUT_CSV, media_type="text/csv", filename="Detected_App_Anomalies.csv")

@router.get("/app/download/anomalies", tags=["Pipeline Applicatif"])
async def app_dl_anomalies(admin=Depends(require_admin)):
    if not os.path.exists(APP_ANOMALY_CSV): raise HTTPException(404, "Aucun fichier.")
    return FileResponse(APP_ANOMALY_CSV, media_type="text/csv", filename="Detected_App_Anomalies_anomalies_only.csv")

@router.post("/apilogs/upload-test-csv", tags=["Pipeline API Logs"])
async def apilogs_upload(file: UploadFile = File(...), admin=Depends(require_admin)):
    return await _upload_csv(file, APILOGS_TEST_CSV, "API Logs", "POST /apilogs/run")

@router.get("/apilogs/test-csv-info", tags=["Pipeline API Logs"])
async def apilogs_csv_info(current_user: dict = Depends(get_current_user)): return _csv_info(APILOGS_TEST_CSV, "API Logs")

def _run_apilogs_pipeline():
    global apilogs_pipeline_status
    apilogs_pipeline_status = {"state": "running", "message": "Pipeline API Logs en cours..."}
    apilogs_pipeline_status = _run_pipeline_generic(APILOGS_SCRIPT, APILOGS_TEST_CSV, apilogs_pipeline_status, "API Logs")

@router.post("/apilogs/run", status_code=status.HTTP_202_ACCEPTED, tags=["Pipeline API Logs"])
async def apilogs_run(background_tasks: BackgroundTasks, admin=Depends(require_admin)):
    global apilogs_pipeline_status
    if not os.path.exists(APILOGS_TEST_CSV): raise HTTPException(status_code=400, detail="Testlogs.csv manquant.")
    if apilogs_pipeline_status.get("state") == "running": raise HTTPException(status_code=409, detail="Déjà en cours.")
    apilogs_pipeline_status = {"state": "pending", "message": "Démarrage pipeline API Logs..."}
    background_tasks.add_task(_run_apilogs_pipeline)
    return {"message": "Pipeline API Logs lancé", "output_dir": APILOGS_INFO_DIR, "status_url": "/apilogs/status", "results_url": "/apilogs/results"}

@router.get("/apilogs/status", tags=["Pipeline API Logs"])
async def apilogs_status(current_user: dict = Depends(get_current_user)): return apilogs_pipeline_status

@router.get("/apilogs/results", tags=["Pipeline API Logs"])
async def apilogs_results(current_user: dict = Depends(get_current_user)):
    if apilogs_pipeline_status.get("state") != "done": raise HTTPException(status_code=400, detail=f"Pipeline non terminé.")
    return _build_results("api_logs", APILOGS_INFO_DIR, APILOGS_ANOMALY_CSV, APILOGS_TEST_CSV)

@router.get("/apilogs/download", tags=["Pipeline API Logs"])
async def apilogs_dl(admin=Depends(require_admin)):
    if not os.path.exists(APILOGS_OUTPUT_CSV): raise HTTPException(status_code=404, detail="Aucun fichier.")
    return FileResponse(APILOGS_OUTPUT_CSV, media_type="text/csv", filename="Detected_API_Anomalies.csv")

@router.get("/apilogs/download/anomalies", tags=["Pipeline API Logs"])
async def apilogs_dl_anomalies(admin=Depends(require_admin)):
    if not os.path.exists(APILOGS_ANOMALY_CSV): raise HTTPException(status_code=404, detail="Aucun fichier.")
    return FileResponse(APILOGS_ANOMALY_CSV, media_type="text/csv", filename="Detected_API_Anomalies_anomalies_only.csv")