import logging
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core import config
from models import (
    BackgroundTask, DataSource, Dataset, EmailDelivery, IngestionJob,
    Report, Schedule, User, WorkerHeartbeat,
)
from models.entities import utcnow
from schemas.datapulse import AnalyticsQuery
from services.analytics import execute_query, get_dataset
from services.events import audit, notify
from services.ingestion import check_api_url, run_import
from services.reports import report_csv

logger = logging.getLogger("datapulse.worker")


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def worker_ready(db: Session) -> bool:
    heartbeat = db.get(WorkerHeartbeat, 1)
    return bool(heartbeat and utcnow() - as_utc(heartbeat.updated_at) < timedelta(seconds=120))


def heartbeat(db: Session):
    row = db.get(WorkerHeartbeat, 1)
    if row is None:
        db.add(WorkerHeartbeat(id=1, updated_at=utcnow()))
    else:
        row.updated_at = utcnow()
    db.commit()


def require_capacity(db: Session):
    count = db.scalar(select(func.count()).select_from(BackgroundTask).where(
        BackgroundTask.status.in_(["queued", "running"]),
    ))
    if count >= 100:
        raise HTTPException(429, "Fila cheia (100 tarefas); aguarde o processamento")


def api_source(db: Session, dataset: Dataset) -> DataSource:
    source = db.get(DataSource, dataset.source_id) if dataset.source_id else None
    if source is None or source.kind != "api":
        raise HTTPException(422, "Agendamento/importacao sem arquivo requer fonte API HTTPS")
    check_api_url(source.url or "")
    return source


def enqueue_import(db: Session, dataset: Dataset, user_id: int, filename: str,
                   content: bytes | None, schedule_id: int | None = None) -> IngestionJob:
    require_capacity(db)
    if content is None:
        api_source(db, dataset)
    job = IngestionJob(dataset_id=dataset.id, created_by=user_id, filename=filename[:255], status="queued")
    db.add(job)
    db.flush()
    db.add(BackgroundTask(kind="import", dataset_id=dataset.id, created_by=user_id,
                          schedule_id=schedule_id, job_id=job.id, file_content=content))
    return job


def enqueue_report(db: Session, schedule: Schedule):
    require_capacity(db)
    db.add(BackgroundTask(
        kind="report", dataset_id=schedule.dataset_id, schedule_id=schedule.id,
        created_by=schedule.created_by,
        payload={"name": schedule.name, "query": schedule.query, "email_report": schedule.email_report},
    ))


def dispatch_schedules(db: Session):
    now = utcnow()
    for schedule in db.scalars(select(Schedule).where(
        Schedule.enabled.is_(True), Schedule.next_run_at <= now,
    ).order_by(Schedule.next_run_at).limit(25)):
        if db.scalar(select(BackgroundTask.id).where(
            BackgroundTask.schedule_id == schedule.id,
            BackgroundTask.status.in_(["queued", "running"]),
        ).limit(1)) is not None:
            continue
        try:
            if schedule.kind == "import":
                enqueue_import(db, get_dataset(db, schedule.dataset_id), schedule.created_by,
                               "api.json", None, schedule.id)
            else:
                enqueue_report(db, schedule)
            schedule.last_status = "queued"
        except HTTPException as exc:
            logger.warning("Schedule rejected id=%s status=%s", schedule.id, exc.status_code)
            schedule.last_status = "failed"
            notify(db, "schedule", f"Falha no agendamento: {schedule.name}",
                   str(exc.detail), "/settings", user_id=schedule.created_by)
        schedule.next_run_at = now + timedelta(minutes=schedule.interval_minutes)
        audit(db, schedule.created_by, "dispatch", "schedules", schedule.id)
    db.commit()


def mark_failed(db: Session, task_id: int, message: str):
    task = db.get(BackgroundTask, task_id)
    task.status, task.error, task.finished_at, task.file_content = "failed", message, utcnow(), None
    if task.job_id:
        job = db.get(IngestionJob, task.job_id)
        job.status, job.errors, job.finished_at = "failed", [{"message": message}], utcnow()
    if task.schedule_id:
        schedule = db.get(Schedule, task.schedule_id)
        schedule.last_status, schedule.last_run_at = "failed", utcnow()
    notify(db, "task", "Processamento interrompido", message, "/settings", user_id=task.created_by)
    audit(db, task.created_by, "failed", "background_tasks", task.id)
    db.commit()


def recover_interrupted(db: Session):
    for task_id in db.scalars(select(BackgroundTask.id).where(BackgroundTask.status == "running")).all():
        mark_failed(db, task_id, "Worker interrompido. Verifique o resultado antes de reenviar a tarefa.")
    for delivery in db.scalars(select(EmailDelivery).where(EmailDelivery.status == "sending")):
        delivery.status = "failed"
        delivery.error = "Envio interrompido; entrega incerta. Nao reenviado para evitar duplicidade."
        logger.error("Uncertain email delivery id=%s", delivery.id)
        notify(db, "email", "Entrega de email incerta", delivery.error, "/settings", user_id=delivery.user_id)
    db.commit()


def process_task(db: Session) -> bool:
    task = db.scalar(select(BackgroundTask).where(
        BackgroundTask.status == "queued",
    ).order_by(BackgroundTask.id).limit(1))
    if task is None:
        return False
    task_id = task.id
    task.status = "running"
    if task.job_id:
        db.get(IngestionJob, task.job_id).status = "processing"
    db.commit()
    try:
        user = db.get(User, task.created_by)
        if user is None or not user.active or user.role not in {"editor", "admin"}:
            raise HTTPException(403, "Autor sem permissao de edicao; tarefa cancelada")
        dataset = get_dataset(db, task.dataset_id)
        if task.kind == "import":
            job = db.get(IngestionJob, task.job_id)
            source = api_source(db, dataset) if task.file_content is None else None
            run_import(db, dataset, user.id, job.filename, task.file_content, source, job=job)
            task.status = job.status
            if job.status == "failed":
                task.error = job.errors[0]["message"]
        elif task.kind == "report":
            query = AnalyticsQuery.model_validate(task.payload["query"])
            report = Report(name=task.payload["name"], dataset_id=dataset.id,
                            query=query.model_dump(), result=execute_query(db, query), created_by=user.id)
            db.add(report)
            db.flush()
            task.report_id, task.status = report.id, "completed"
            message = "Snapshot gerado com dados reais."
            if task.payload.get("email_report") and not config.SMTP_ENABLED:
                task.status = "completed_with_errors"
                task.error = "Email nao enviado: SMTP foi desabilitado no servidor."
                message += " " + task.error
            notify(db, "report", f"Relatorio pronto: {report.name}", message,
                   "/reports", user_id=user.id, email=task.payload.get("email_report", False),
                   report_id=report.id)
        else:
            raise ValueError("Tipo de tarefa invalido")
        task.finished_at, task.file_content = utcnow(), None
        if task.schedule_id:
            schedule = db.get(Schedule, task.schedule_id)
            schedule.last_status, schedule.last_run_at = task.status, utcnow()
        audit(db, user.id, task.status, "background_tasks", task.id)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Task failed id=%s", task_id)
        message = str(exc.detail) if isinstance(exc, HTTPException) else "Falha no processamento. Consulte os logs do worker."
        mark_failed(db, task_id, message)
    return True


def send_email(delivery: EmailDelivery, user: User, report: Report | None):
    message = EmailMessage()
    message["From"] = config.SMTP_FROM
    message["To"] = user.email
    message["Subject"] = delivery.subject.replace("\r", " ").replace("\n", " ")
    message["Message-ID"] = f"<datapulse-{delivery.id}@{config.SMTP_FROM.rsplit('@', 1)[-1]}>"
    message.set_content(delivery.body)
    if report:
        message.add_attachment(report_csv(report).encode("utf-8"), maintype="text", subtype="csv",
                               filename=f"datapulse-report-{report.id}.csv")
    smtp_class = smtplib.SMTP_SSL if config.SMTP_SECURITY == "ssl" else smtplib.SMTP
    kwargs = {"context": ssl.create_default_context()} if config.SMTP_SECURITY == "ssl" else {}
    with smtp_class(config.SMTP_HOST, config.SMTP_PORT, timeout=20, **kwargs) as smtp:
        if config.SMTP_SECURITY == "starttls":
            smtp.starttls(context=ssl.create_default_context())
        if config.SMTP_USERNAME:
            smtp.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
        smtp.send_message(message)


def process_email(db: Session) -> bool:
    if not config.SMTP_ENABLED:
        return False
    delivery = db.scalar(select(EmailDelivery).where(
        EmailDelivery.status == "queued", EmailDelivery.next_attempt_at <= utcnow(),
    ).order_by(EmailDelivery.id).limit(1))
    if delivery is None:
        return False
    user = db.get(User, delivery.user_id)
    if user is None or not user.active:
        delivery.status, delivery.error = "cancelled", "Destinatario desativado"
        db.commit()
        return True
    delivery.status, delivery.attempts = "sending", delivery.attempts + 1
    db.commit()
    try:
        send_email(delivery, user, db.get(Report, delivery.report_id) if delivery.report_id else None)
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        logger.error("SMTP failed delivery=%s attempt=%s type=%s", delivery.id, delivery.attempts, type(exc).__name__)
        delivery.error = "Falha SMTP; verifique conectividade, TLS e credenciais no servidor."
        delivery.status = "failed" if delivery.attempts >= 3 else "queued"
        delivery.next_attempt_at = utcnow() + timedelta(minutes=5 * delivery.attempts)
        if delivery.status == "failed":
            notify(db, "email", "Falha na entrega de email", delivery.error, "/settings", user_id=user.id)
    else:
        delivery.status, delivery.sent_at, delivery.error = "sent", utcnow(), None
    db.commit()
    return True
