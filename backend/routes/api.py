import logging
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from core.config import MAX_IMPORT_BYTES
from core.jwt import criar_token_acesso
from core.senha_hash import criar_hash_senha, verificar_senha
from database import get_db
from dependencies.autenticacao import get_usuario_atual, require_admin, require_editor
from models import (
    Alert, AnalyticsResult, AuditLog, DataRecord, DataSource, Dataset, IngestionJob,
    Insight, KPI, Report, User,
)
from schemas.datapulse import (
    AlertInput, AnalyticsQuery, DatasetInput, DatasetMetadata, KPIInput, Login, PasswordChange,
    Register, ReportInput, RoleUpdate, SourceInput,
)
from services.analytics import evaluate_alert, execute_query, get_dataset, trends
from services.ingestion import check_api_url, run_import
from services.events import audit, notify
from services.reports import report_csv

router = APIRouter(prefix="/api/v1")
logger = logging.getLogger("datapulse")
login_attempts = defaultdict(deque)
attempt_lock = threading.Lock()


def serialize(entity) -> dict:
    hidden = {"password_hash", "bootstrap_key", "file_content", "token_version"}
    result = {}
    for column in inspect(type(entity)).columns:
        if column.key not in hidden:
            value = getattr(entity, column.key)
            if isinstance(value, datetime) and value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            result[column.key] = value
    return result


def ok(data, meta: dict | None = None) -> dict:
    return {"data": data, "meta": meta or {}}


def paginate(db: Session, statement, page: int, page_size: int, transform=serialize) -> dict:
    total = db.scalar(select(func.count()).select_from(statement.subquery()))
    items = db.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()
    return ok([transform(item) for item in items], {
        "page": page, "page_size": page_size, "total": total,
    })


def save(db: Session, entity, user: User, action: str = "create") -> dict:
    db.add(entity)
    db.flush()
    audit(db, user.id, action, entity.__tablename__, entity.id)
    db.commit()
    db.refresh(entity)
    return ok(serialize(entity))


def auth_throttle(request: Request):
    key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with attempt_lock:
        for stale in list(login_attempts):
            if not login_attempts[stale] or now - login_attempts[stale][-1] > 60:
                del login_attempts[stale]
        attempts = login_attempts[key]
        while attempts and now - attempts[0] > 60:
            attempts.popleft()
        if len(attempts) >= 15:
            raise HTTPException(429, "Muitas tentativas; aguarde um minuto")
        attempts.append(now)


@router.post("/auth/register", tags=["Authentication"], status_code=201)
def register(body: Register, request: Request, db: Session = Depends(get_db)):
    auth_throttle(request)
    first = db.scalar(select(User.id).limit(1)) is None
    if not first:
        raise HTTPException(403, "Cadastro inicial encerrado. Solicite acesso ao administrador.")
    user = User(
        name=body.name, email=body.email, password_hash=criar_hash_senha(body.password),
        role="admin" if first else "viewer", bootstrap_key="initial" if first else None,
    )
    db.add(user)
    db.flush()
    audit(db, user.id, "register", "users", user.id)
    db.commit()
    return ok({"user": serialize(user), "access_token": criar_token_acesso(user.id, user.token_version), "token_type": "bearer"})


@router.get("/auth/setup", tags=["Authentication"])
def setup_status(db: Session = Depends(get_db)):
    return ok({"registration_open": db.scalar(select(User.id).limit(1)) is None})


@router.post("/auth/login", tags=["Authentication"])
def login(body: Login, request: Request, db: Session = Depends(get_db)):
    auth_throttle(request)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verificar_senha(body.password, user.password_hash) or not user.active:
        logger.warning("Authentication rejected")
        raise HTTPException(401, "Credenciais invalidas")
    audit(db, user.id, "login", "users", user.id)
    db.commit()
    return ok({"user": serialize(user), "access_token": criar_token_acesso(user.id, user.token_version), "token_type": "bearer"})


@router.get("/auth/me", tags=["Authentication"])
def me(user: User = Depends(get_usuario_atual)):
    return ok(serialize(user))


@router.post("/auth/password", tags=["Authentication"])
def change_password(body: PasswordChange, db: Session = Depends(get_db),
                    user: User = Depends(get_usuario_atual)):
    if not verificar_senha(body.current_password, user.password_hash):
        raise HTTPException(400, "Senha atual incorreta")
    if body.current_password == body.new_password:
        raise HTTPException(400, "A nova senha deve ser diferente da atual")
    user.password_hash = criar_hash_senha(body.new_password)
    user.token_version += 1
    audit(db, user.id, "change_password", "users", user.id)
    db.commit()
    db.refresh(user)
    return ok({"access_token": criar_token_acesso(user.id, user.token_version), "token_type": "bearer"})


@router.post("/auth/logout", tags=["Authentication"])
def logout(db: Session = Depends(get_db), user: User = Depends(get_usuario_atual)):
    user.token_version += 1
    audit(db, user.id, "logout", "users", user.id)
    db.commit()
    return ok({"logged_out": True})


@router.get("/users", tags=["Team"])
def users(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
          db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return paginate(db, select(User).order_by(User.id), page, page_size)


@router.post("/users", tags=["Team"], status_code=201)
def create_user(body: Register, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return save(db, User(
        name=body.name, email=body.email, password_hash=criar_hash_senha(body.password),
        role="viewer", active=True,
    ), user)


@router.patch("/users/{user_id}", tags=["Team"])
def update_user(user_id: int, body: RoleUpdate, db: Session = Depends(get_db),
                user: User = Depends(require_admin)):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(404, "Usuario nao encontrado")
    if target.id == user.id and (body.role != "admin" or not body.active):
        raise HTTPException(422, "Nao e permitido remover seu proprio acesso de administrador")
    if target.role != body.role or target.active != body.active:
        target.token_version += 1
    target.role, target.active = body.role, body.active
    return save(db, target, user, "update_permissions")


@router.post("/sources", tags=["Data Sources"], status_code=201)
def create_source(body: SourceInput, db: Session = Depends(get_db), user: User = Depends(require_editor)):
    if body.kind == "api":
        check_api_url(body.url)
    return save(db, DataSource(**body.model_dump(), created_by=user.id), user)


@router.get("/sources", tags=["Data Sources"])
def sources(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
            db: Session = Depends(get_db), user: User = Depends(get_usuario_atual)):
    return paginate(db, select(DataSource).order_by(DataSource.id.desc()), page, page_size)


@router.patch("/sources/{source_id}", tags=["Data Sources"])
def update_source(source_id: int, body: SourceInput, db: Session = Depends(get_db),
                  user: User = Depends(require_editor)):
    source = db.get(DataSource, source_id)
    if source is None:
        raise HTTPException(404, "Fonte nao encontrada")
    if body.kind == "api":
        check_api_url(body.url)
    for key, value in body.model_dump().items():
        setattr(source, key, value)
    return save(db, source, user, "update")


@router.post("/datasets", tags=["Datasets"], status_code=201)
def create_dataset(body: DatasetInput, db: Session = Depends(get_db), user: User = Depends(require_editor)):
    if body.source_id and db.get(DataSource, body.source_id) is None:
        raise HTTPException(404, "Fonte nao encontrada")
    return save(db, Dataset(
        name=body.name, description=body.description, source_id=body.source_id,
        schema=[c.model_dump() for c in body.columns], created_by=user.id,
    ), user)


@router.get("/datasets", tags=["Datasets"])
def datasets(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
             db: Session = Depends(get_db), user: User = Depends(get_usuario_atual)):
    def item(dataset):
        return {**serialize(dataset), "record_count": db.scalar(
            select(func.count()).select_from(DataRecord).where(DataRecord.dataset_id == dataset.id),
        )}
    return paginate(db, select(Dataset).order_by(Dataset.id.desc()), page, page_size, item)


@router.get("/datasets/{dataset_id}", tags=["Datasets"])
def dataset_detail(dataset_id: int, db: Session = Depends(get_db), user: User = Depends(get_usuario_atual)):
    return ok(serialize(get_dataset(db, dataset_id)))


@router.patch("/datasets/{dataset_id}", tags=["Datasets"])
def update_dataset(dataset_id: int, body: DatasetMetadata, db: Session = Depends(get_db),
                   user: User = Depends(require_editor)):
    dataset = get_dataset(db, dataset_id)
    if body.source_id and db.get(DataSource, body.source_id) is None:
        raise HTTPException(404, "Fonte nao encontrada")
    for key, value in body.model_dump().items():
        setattr(dataset, key, value)
    return save(db, dataset, user, "update")


@router.get("/datasets/{dataset_id}/records", tags=["Datasets"])
def records(dataset_id: int, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
            db: Session = Depends(get_db), user: User = Depends(get_usuario_atual)):
    get_dataset(db, dataset_id)
    return paginate(db, select(DataRecord).where(
        DataRecord.dataset_id == dataset_id,
    ).order_by(DataRecord.id), page, page_size)


@router.post("/ingestion/import", tags=["Data Ingestion"], status_code=201)
def import_data(response: Response, dataset_id: int = Form(..., gt=0), file: UploadFile | None = File(None),
                background: bool = Form(False),
                db: Session = Depends(get_db), user: User = Depends(require_editor)):
    dataset = get_dataset(db, dataset_id)
    source = db.get(DataSource, dataset.source_id) if dataset.source_id else None
    if file:
        content = file.file.read(MAX_IMPORT_BYTES + 1)
        if len(content) > MAX_IMPORT_BYTES:
            raise HTTPException(413, "Arquivo excede 5 MB")
        filename = file.filename or ""
    else:
        content = None
        filename = "api.json"
    if background:
        from services.operations import enqueue_import
        job = enqueue_import(db, dataset, user.id, filename, content)
        result = save(db, job, user, "queue_import")
        response.status_code = 202
        return result
    job = run_import(db, dataset, user.id, filename, content, source)
    result = save(db, job, user, "import")
    if job.status == "failed":
        logger.warning("Import failed job=%s dataset=%s", job.id, dataset.id)
        raise HTTPException(422, {"message": "Importacao falhou", "job": result["data"]})
    return result


@router.get("/ingestion/jobs", tags=["Data Ingestion"])
def jobs(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
         db: Session = Depends(get_db), user: User = Depends(get_usuario_atual)):
    return paginate(db, select(IngestionJob).order_by(IngestionJob.id.desc()), page, page_size)


@router.get("/ingestion/jobs/{job_id}", tags=["Data Ingestion"])
def job_detail(job_id: int, db: Session = Depends(get_db), user: User = Depends(get_usuario_atual)):
    job = db.get(IngestionJob, job_id)
    if job is None:
        raise HTTPException(404, "Importacao nao encontrada")
    return ok(serialize(job))


@router.post("/analytics/query", tags=["Analytics"])
def query(body: AnalyticsQuery, db: Session = Depends(get_db), user: User = Depends(get_usuario_atual)):
    result = execute_query(db, body)
    db.add(AnalyticsResult(
        dataset_id=body.dataset_id, query=body.model_dump(), result=result, created_by=user.id,
    ))
    audit(db, user.id, "query", "datasets", body.dataset_id)
    db.commit()
    return ok(result)


@router.get("/analytics/summary", tags=["Analytics"])
def summary(db: Session = Depends(get_db), user: User = Depends(get_usuario_atual)):
    def count(model):
        return db.scalar(select(func.count()).select_from(model))
    kpis = [{
        **serialize(kpi),
        "value": execute_query(db, AnalyticsQuery.model_validate(kpi.query))["value"],
    } for kpi in db.scalars(select(KPI).order_by(KPI.id.desc()).limit(6))]
    return ok({
        "records": count(DataRecord), "sources": count(DataSource), "datasets": count(Dataset),
        "imports": count(IngestionJob), "kpi_count": count(KPI), "kpis": kpis,
        "active_alerts": db.scalar(select(func.count()).select_from(Alert).where(
            Alert.enabled.is_(True), Alert.triggered.is_(True),
        )),
        "recent_jobs": [serialize(j) for j in db.scalars(
            select(IngestionJob).order_by(IngestionJob.id.desc()).limit(5),
        )],
        "insights": [serialize(i) for i in db.scalars(
            select(Insight).order_by(Insight.updated_at.desc()).limit(5),
        )],
        "recent_alerts": [serialize(a) for a in db.scalars(
            select(Alert).order_by(Alert.evaluated_at.desc()).limit(5),
        )],
    })


@router.get("/analytics/trends", tags=["Analytics"])
def trend_query(dataset_id: int = Query(..., gt=0), date_field: str = Query(..., min_length=1),
                field: str | None = None, aggregation: str = "count", period: str = "month",
                db: Session = Depends(get_db), user: User = Depends(get_usuario_atual)):
    from pydantic import ValidationError
    try:
        body = AnalyticsQuery.model_validate({
            "dataset_id": dataset_id, "field": field, "date_field": date_field,
            "aggregation": aggregation, "period": period,
        })
    except ValidationError:
        raise HTTPException(422, "Parametros de tendencia invalidos")
    return ok(trends(db, body))


@router.post("/kpis", tags=["KPIs"], status_code=201)
def create_kpi(body: KPIInput, db: Session = Depends(get_db), user: User = Depends(require_editor)):
    if body.query.group_by or body.query.date_field:
        raise HTTPException(422, "KPI requer consulta escalar sem agrupamentos")
    execute_query(db, body.query)
    return save(db, KPI(
        name=body.name, dataset_id=body.query.dataset_id, query=body.query.model_dump(),
        target=body.target, created_by=user.id,
    ), user)


@router.get("/kpis", tags=["KPIs"])
def kpis(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
         db: Session = Depends(get_db), user: User = Depends(get_usuario_atual)):
    def item(kpi):
        return {**serialize(kpi), "value": execute_query(db, AnalyticsQuery.model_validate(kpi.query))["value"]}
    return paginate(db, select(KPI).order_by(KPI.id.desc()), page, page_size, item)


@router.patch("/kpis/{kpi_id}", tags=["KPIs"])
def update_kpi(kpi_id: int, body: KPIInput, db: Session = Depends(get_db),
               user: User = Depends(require_editor)):
    kpi = db.get(KPI, kpi_id)
    if kpi is None:
        raise HTTPException(404, "KPI nao encontrado")
    if body.query.group_by or body.query.date_field:
        raise HTTPException(422, "KPI requer consulta escalar sem agrupamentos")
    execute_query(db, body.query)
    kpi.name, kpi.target = body.name, body.target
    kpi.dataset_id, kpi.query = body.query.dataset_id, body.query.model_dump()
    db.flush()
    for alert in db.scalars(select(Alert).where(Alert.kpi_id == kpi.id)):
        evaluate_alert(db, alert)
    return save(db, kpi, user, "update")


@router.get("/insights", tags=["Insights"])
def insights(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
             db: Session = Depends(get_db), user: User = Depends(get_usuario_atual)):
    return paginate(db, select(Insight).order_by(Insight.updated_at.desc()), page, page_size)


@router.post("/reports", tags=["Reports"], status_code=201)
def create_report(body: ReportInput, db: Session = Depends(get_db), user: User = Depends(require_editor)):
    notify(db, "report", f"Relatorio pronto: {body.name}", "Snapshot gerado com dados reais.",
           "/reports", user_id=user.id)
    return save(db, Report(
        name=body.name, dataset_id=body.query.dataset_id, query=body.query.model_dump(),
        result=execute_query(db, body.query), created_by=user.id,
    ), user)


@router.get("/reports", tags=["Reports"])
def reports(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
            db: Session = Depends(get_db), user: User = Depends(get_usuario_atual)):
    return paginate(db, select(Report).order_by(Report.id.desc()), page, page_size)


@router.get("/reports/{report_id}/export", tags=["Reports"])
def export_report(report_id: int, db: Session = Depends(get_db), user: User = Depends(get_usuario_atual)):
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(404, "Relatorio nao encontrado")
    audit(db, user.id, "export", "reports", report.id)
    db.commit()
    return Response(report_csv(report), media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="datapulse-report-{report.id}.csv"',
    })


@router.post("/alerts", tags=["Alerts"], status_code=201)
def create_alert(body: AlertInput, db: Session = Depends(get_db), user: User = Depends(require_editor)):
    if db.get(KPI, body.kpi_id) is None:
        raise HTTPException(404, "KPI nao encontrado")
    alert = Alert(**body.model_dump(), created_by=user.id)
    evaluate_alert(db, alert)
    return save(db, alert, user)


@router.get("/alerts", tags=["Alerts"])
def alerts(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
           db: Session = Depends(get_db), user: User = Depends(get_usuario_atual)):
    return paginate(db, select(Alert).order_by(Alert.id.desc()), page, page_size)


@router.patch("/alerts/{alert_id}", tags=["Alerts"])
def update_alert(alert_id: int, body: AlertInput, db: Session = Depends(get_db),
                 user: User = Depends(require_editor)):
    alert = db.get(Alert, alert_id)
    if alert is None or db.get(KPI, body.kpi_id) is None:
        raise HTTPException(404, "Alerta ou KPI nao encontrado")
    for key, value in body.model_dump().items():
        setattr(alert, key, value)
    evaluate_alert(db, alert)
    return save(db, alert, user, "update")


@router.get("/audit", tags=["Team"])
def audit_logs(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
               db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return paginate(db, select(AuditLog).order_by(AuditLog.id.desc()), page, page_size)
