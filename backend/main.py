import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException
import uvicorn

from core.config import CORS_ORIGINS
from database import engine
from routes.api import router
from routes.operations import router as operations_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("datapulse")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if "alembic_version" not in inspect(engine).get_table_names():
        raise RuntimeError("Banco nao migrado. Execute: python -m alembic upgrade head")
    config = Config(str(Path(__file__).parent / "alembic.ini"))
    with engine.connect() as connection:
        if MigrationContext.configure(connection).get_current_revision() != ScriptDirectory.from_config(config).get_current_head():
            raise RuntimeError("Migrations pendentes. Execute: python -m alembic upgrade head")
    yield


app = FastAPI(title="DataPulse API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router)
app.include_router(operations_router)


def error_response(request: Request, status: int, code: str, message: str, details=None):
    return JSONResponse(status_code=status, content=jsonable_encoder({
        "error": {"code": code, "message": message, "details": details},
        "request_id": getattr(request.state, "request_id", None),
    }))


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    message = exc.detail if isinstance(exc.detail, str) else exc.detail.get("message", "Falha na requisicao")
    return error_response(request, exc.status_code, f"HTTP_{exc.status_code}", message,
                          exc.detail if not isinstance(exc.detail, str) else None)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    details = [{"location": list(e["loc"]), "message": e["msg"]} for e in exc.errors()]
    return error_response(request, 422, "VALIDATION_ERROR", "Dados invalidos", details)


@app.exception_handler(IntegrityError)
async def integrity_error(request: Request, exc: IntegrityError):
    logger.warning("Integrity conflict request=%s", getattr(request.state, "request_id", None))
    return error_response(request, 409, "CONFLICT", "Registro duplicado ou conflito de integridade; atualize e tente novamente")


@app.middleware("http")
async def request_logging(request: Request, call_next):
    request.state.request_id = uuid.uuid4().hex
    start = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        # Last-resort boundary: log the traceback, never expose database data or credentials.
        logger.exception("Unhandled request error id=%s path=%s", request.state.request_id, request.url.path)
        response = error_response(request, 500, "INTERNAL_ERROR", "Erro interno; consulte o identificador nos logs")
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    logger.info("%s %s status=%s duration_ms=%.1f request=%s",
                request.method, request.url.path, response.status_code,
                (time.monotonic() - start) * 1000, request.state.request_id)
    return response


@app.get("/health", tags=["Health"])
def health():
    return {"data": {"status": "ok", "service": "DataPulse"}, "meta": {}}


@app.get("/ready", tags=["Health"])
def ready():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Readiness database check failed")
        raise HTTPException(503, "Banco indisponivel")
    return {"data": {"status": "ready"}, "meta": {}}

if __name__ == "__main__":
    uvicorn.run("main:app", port=8000, reload=True)