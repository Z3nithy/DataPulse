"""Single durable worker; run separately from the API."""
import logging
import os
import time
from contextlib import contextmanager

from core.config import WORKER_LOCK_PATH
from database import engine
from database.db import SessionLocal
from services.operations import dispatch_schedules, heartbeat, process_email, process_task, recover_interrupted

logger = logging.getLogger("datapulse.worker")


@contextmanager
def worker_lock(path=WORKER_LOCK_PATH):
    with open(path, "a+b") as handle:
        handle.seek(0)
        handle.write(b"0")
        handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError("Outro worker ativo. Use o mesmo WORKER_LOCK_PATH para este banco.") from exc
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def main():
    from main import lifespan, app
    import asyncio

    async def verify_schema():
        async with lifespan(app):
            pass

    asyncio.run(verify_schema())
    with worker_lock():
        with SessionLocal() as db:
            recover_interrupted(db)
        logger.info("Worker started")
        try:
            while True:
                with SessionLocal() as db:
                    heartbeat(db)
                    dispatch_schedules(db)
                    process_task(db)
                    process_email(db)
                time.sleep(3)
        finally:
            engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    main()
