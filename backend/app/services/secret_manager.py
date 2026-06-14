import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class SecretManager:
    """
    Abstraction pour la gestion des secrets (Standard Bank - Vault Ready).
    Permet de basculer de .env vers HashiCorp Vault sans changer le code métier.

    PRIORITÉ DE RÉSOLUTION DES SECRETS (Finding SEC-01 — Audit Bancaire) :
    1. HashiCorp Vault (si VAULT_ENABLED=true)
    2. Variables d'environnement (Docker Secrets, K8s Secrets, CI/CD)
    3. Fichier .env local (DEV uniquement — jamais en PROD)
    """
    def __init__(self):
        self.use_vault = os.getenv("VAULT_ENABLED", "false").lower() == "true"
        self.vault_url = os.getenv("VAULT_ADDR")
        self.vault_token = os.getenv("VAULT_TOKEN")

    def get_secret(self, key: str, default: str = None) -> str:
        if self.use_vault:
            try:
                import hvac
                client = hvac.Client(url=self.vault_url, token=self.vault_token)
                secret = client.secrets.kv.v2.read_secret_version(path="banking-app")
                value = secret["data"]["data"].get(key)
                if value:
                    logger.info(f"🔒 Vault: Secret '{key}' récupéré avec succès.")
                    return value
                logger.warning(f"⚠️ Vault: Secret '{key}' introuvable dans Vault.")
            except ImportError:
                logger.warning("⚠️ hvac non installé — Vault désactivé, fallback sur variables d'environnement.")
            except Exception as e:
                logger.error(f"❌ Erreur Vault pour '{key}': {e}. Fallback sur variables d'environnement.")

        # Fallback: Variables d'environnement (DEV/STAGE)
        return os.getenv(key, default)

    def get_rsa_key(self, key_type: str = "private") -> str:
        """
        Récupère les clés RSA dans l'ordre de priorité suivant :
        1. Variable d'environnement RSA_PRIVATE_KEY / RSA_PUBLIC_KEY (PROD — Docker Secrets)
        2. Fichier .pem local (DEV uniquement — exclu du build Docker via .dockerignore)

        Finding DATA-01 (Audit Bancaire) : Les clés RSA ne doivent JAMAIS être copiées
        dans l'image Docker. Elles doivent être injectées au runtime via Docker Secrets
        ou variables d'environnement.
        """
        env_var_name = "RSA_PRIVATE_KEY" if key_type == "private" else "RSA_PUBLIC_KEY"

        # Priorité 1 : Variable d'environnement (PROD / Docker Swarm Secrets / K8s Secret)
        key_from_env = os.getenv(env_var_name)
        if key_from_env:
            # Restaurer les sauts de ligne si la clé a été passée encodée
            key_content = key_from_env.replace("\\n", "\n")
            logger.info(f"🔒 Clé RSA {key_type} chargée depuis variable d'environnement.")
            return key_content

        # Priorité 2 : Fichier .pem local (DEV uniquement)
        filename = "private_key.pem" if key_type == "private" else "public_key.pem"
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), filename)

        if not os.path.exists(path):
            logger.warning(
                f"⚠️ Clé RSA {key_type} introuvable : ni la variable d'environnement "
                f"'{env_var_name}' ni le fichier '{path}' ne sont disponibles."
            )
            return None

        env = os.getenv("ENV", "dev").lower()
        if env == "prod":
            # En production, on refuse de lire depuis le filesystem — la clé doit être injectée
            logger.error(
                f"🚨 SECURITY VIOLATION: Tentative de lecture de la clé RSA {key_type} "
                f"depuis le filesystem en ENV=prod. Utilisez RSA_{key_type.upper()}_KEY en variable d'environnement."
            )
            return None

        logger.warning(
            f"⚠️ DEV MODE: Clé RSA {key_type} lue depuis le filesystem ({filename}). "
            "En production, injectez via la variable d'environnement RSA_PRIVATE_KEY / RSA_PUBLIC_KEY."
        )
        with open(path, "r") as f:
            return f.read()


secret_manager = SecretManager()
