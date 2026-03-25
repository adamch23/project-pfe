from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from controllers import user_controller
from auth import create_default_admin

app = FastAPI()

# --- CORS ---
origins = [
    "http://localhost:5173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Création admin par défaut ---
@app.on_event("startup")
async def startup():
    await create_default_admin()

# --- Routes ---
app.include_router(user_controller.router, prefix="/api", tags=["users"])