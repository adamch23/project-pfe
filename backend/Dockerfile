# ── Build Stage ──
FROM python:3.10-slim

WORKDIR /app

# Installation des dépendances système (OpenCV, etc.)
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Installation de Torch version CPU (plus léger et stable pour Docker)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Installation des autres dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code source
# IMPORTANT: .dockerignore exclut explicitement *.pem, .env, private_key.pem, public_key.pem
# Finding DATA-01 / SEC-01 (Audit Bancaire) : Les secrets ne doivent jamais être copiés
# dans l'image Docker. Injectez RSA_PRIVATE_KEY et RSA_PUBLIC_KEY via Docker Secrets
# ou variables d'environnement au moment du runtime.
COPY app/ ./app/

# Port d'exposition
EXPOSE 8000

# Variables d'environnement par défaut
ENV PYTHONPATH=/app/app
ENV PYTHONUNBUFFERED=1

# Création d'un utilisateur non-root pour la sécurité (Principe du moindre privilège)
# CIS Docker Benchmark 4.1
RUN useradd -m appuser
RUN chown -R appuser:appuser /app
USER appuser

# Lancement sécurisé
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
