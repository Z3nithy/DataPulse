import os
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