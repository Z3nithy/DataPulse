"""Isolated API and worker for Playwright. Never loads the application database."""
import os
import secrets
import tempfile
import threading
from contextlib import asynccontextmanager
from pathlib import Path

directory = tempfile.TemporaryDirectory(prefix="datapulse-e2e-")
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(directory.name) / "e2e.db")
os.environ["SECRET_KEY"] = secrets.token_urlsafe(48)
os.environ["SMTP_ENABLED"] = "false"
os.environ["CORS_ORIGINS"] = "http://127.0.0.1:18771"
os.environ["API_ALLOWED_HOSTS"] = ""
os.environ["WORKER_LOCK_PATH"] = str(Path(directory.name) / ".worker.lock")

import uvicorn
from alembic import command
from alembic.config import Config
from database import engine
from database.db import SessionLocal
from main import app, lifespan
from services.operations import dispatch_schedules, heartbeat, process_email, process_task


@asynccontextmanager
async def test_lifespan(application):
    stop = threading.Event()

    def worker():
        while not stop.is_set():
            with SessionLocal() as db:
                heartbeat(db)
                dispatch_schedules(db)
                process_task(db)
                process_email(db)
            stop.wait(0.25)

    async with lifespan(application):
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        try:
            yield
        finally:
            stop.set()
            thread.join(timeout=30)
            engine.dispose()
            directory.cleanup()


if __name__ == "__main__":
    command.upgrade(Config("alembic.ini"), "head")
    app.router.lifespan_context = test_lifespan
    uvicorn.run(app, host="127.0.0.1", port=18770)
