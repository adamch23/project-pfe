import os
import random
from email.message import EmailMessage
import aiosmtplib
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

async def send_verification_code(to_email: str, code: str):
    msg = EmailMessage()
    msg["From"] = SMTP_USER
    msg["To"] = to_email
    msg["Subject"] = "Code de vérification pour réinitialisation de mot de passe"
    msg.set_content(f"Votre code de vérification est : {code}\nIl expire dans 15 minutes.")

    await aiosmtplib.send(
        msg,
        hostname=SMTP_HOST,
        port=SMTP_PORT,
        start_tls=True,
        username=SMTP_USER,
        password=SMTP_PASSWORD,
    )

def generate_code(length: int = 6):
    return "".join([str(random.randint(0, 9)) for _ in range(length)])