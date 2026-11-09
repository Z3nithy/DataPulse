import os
import re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DATABASE_URL = os.environ["DATABASE_URL"]
SECRET_KEY = os.environ["SECRET_KEY"]
ALGORITHM = os.getenv("ALGORITHM", "HS256")
if ALGORITHM != "HS256":
    raise RuntimeError("DataPulse requer ALGORITHM=HS256.")
if len(SECRET_KEY) < 32:
    raise RuntimeError("SECRET_KEY deve conter pelo menos 32 caracteres.")

CORS_ORIGINS = [v.strip() for v in os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",") if v.strip()]
API_ALLOWED_HOSTS = {v.strip().lower() for v in os.getenv(
    "API_ALLOWED_HOSTS", ""
).split(",") if v.strip()}
MAX_IMPORT_BYTES = 5 * 1024 * 1024
MAX_ROWS = 10000

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
DEMO_USERNAME = os.getenv("DEMO_USERNAME", "demo").strip().lower()
DEMO_EMAIL = os.getenv("DEMO_EMAIL", "").strip().lower() or None
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "")
if DEMO_MODE and (
    not re.fullmatch(r"[a-z0-9._-]{3,32}", DEMO_USERNAME)
    or not 10 <= len(DEMO_PASSWORD) <= 128
):
    raise RuntimeError(
        "DEMO_MODE requer DEMO_USERNAME valido e DEMO_PASSWORD entre 10 e 128 caracteres."
    )

SMTP_ENABLED = os.getenv("SMTP_ENABLED", "false").lower() == "true"
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")
SMTP_SECURITY = os.getenv("SMTP_SECURITY", "starttls")
if SMTP_SECURITY not in {"starttls", "ssl"}:
    raise RuntimeError("SMTP_SECURITY requer starttls ou ssl.")
if SMTP_ENABLED and (not SMTP_HOST or not SMTP_FROM or "\n" in SMTP_FROM or "\r" in SMTP_FROM):
    raise RuntimeError("SMTP habilitado requer SMTP_HOST e SMTP_FROM validos.")
WORKER_LOCK_PATH = Path(os.getenv("WORKER_LOCK_PATH", str(Path(__file__).resolve().parents[1] / ".worker.lock")))