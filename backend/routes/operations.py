from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from core.config import SMTP_ENABLED
from database import get_db
from dependencies.autenticacao import get_usuario_atual, require_admin
from models import BackgroundTask, EmailDelivery, Favorite, Notification, Schedule, User
from models.entities import utcnow
from routes.api import ok, paginate, save
from schemas.datapulse import FavoriteInput, ScheduleInput, ScheduleState
from services.analytics import execute_query, get_dataset
from services.events import audit
from services.operations import api_source, worker_ready

router = APIRouter(prefix="/api/v1", tags=["Workspace Operations"])


@router.get("/notifications")
def notifications(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                  db: Session = Depends(get_db), user: User = Depends(get_usuario_atual)):
    result = paginate(db, select(Notification).where(Notification.user_id == user.id).order_by(
        Notification.id.desc()), page, page_size)
    result["meta"]["unread"] = db.scalar(select(func.count()).select_from(Notification).where(
        Notification.user_id == user.id, Notification.read_at.is_(None)))
    return result


@router.post("/notifications/read-all")
def read_all(db: Session = Depends(get_db), user: User = Depends(get_usuario_atual)):
    db.execute(update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None)).values(read_at=utcnow()))
    audit(db, user.id, "read_all", "notifications", None)
    db.commit()
    return ok({"read": True})


@router.patch("/notifications/{notification_id}/read")
def read_one(notification_id: int, db: Session = Depends(get_db), user: User = Depends(get_usuario_atual)):
    item = db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id))
    if item is None:
        raise HTTPException(404, "Notificacao nao encontrada")
    item.read_at = item.read_at or utcnow()
    return save(db, item, user, "read")


@router.get("/favorites")
def favorites(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
              db: Session = Depends(get_db), user: User = Depends(get_usuario_atual)):
    return paginate(db, select(Favorite).where(Favorite.user_id == user.id).order_by(Favorite.id.desc()), page, page_size)


@router.post("/favorites", status_code=201)
def create_favorite(body: FavoriteInput, db: Session = Depends(get_db), user: User = Depends(get_usuario_atual)):
    execute_query(db, body.query)
    return save(db, Favorite(user_id=user.id, name=body.name, dataset_id=body.query.dataset_id,
                             query=body.query.model_dump()), user)


@router.delete("/favorites/{favorite_id}")
def delete_favorite(favorite_id: int, db: Session = Depends(get_db), user: User = Depends(get_usuario_atual)):
    item = db.scalar(select(Favorite).where(Favorite.id == favorite_id, Favorite.user_id == user.id))
    if item is None:
        raise HTTPException(404, "Favorito nao encontrado")
    db.delete(item)
    audit(db, user.id, "delete", "favorites", favorite_id)
    db.commit()
    return ok({"deleted": True})


@router.get("/operations/status")
def status(db: Session = Depends(get_db), user: User = Depends(get_usuario_atual)):
    return ok({"worker_online": worker_ready(db), "smtp_enabled": SMTP_ENABLED})


@router.get("/operations/tasks")
def tasks(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
          db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return paginate(db, select(BackgroundTask).order_by(BackgroundTask.id.desc()), page, page_size)


@router.get("/operations/emails")
def emails(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
           db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return paginate(db, select(EmailDelivery).order_by(EmailDelivery.id.desc()), page, page_size)


@router.get("/operations/metrics")
def metrics(db: Session = Depends(get_db), user: User = Depends(require_admin)):
    def counts(model):
        return {state: count for state, count in db.execute(
            select(model.status, func.count()).group_by(model.status))}
    return ok({"worker_online": worker_ready(db), "tasks": counts(BackgroundTask),
               "emails": counts(EmailDelivery)})


@router.get("/schedules")
def schedules(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
              db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return paginate(db, select(Schedule).order_by(Schedule.id.desc()), page, page_size)


@router.post("/schedules", status_code=201)
def create_schedule(body: ScheduleInput, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    dataset = get_dataset(db, body.dataset_id)
    if body.kind == "import":
        api_source(db, dataset)
    else:
        execute_query(db, body.query)
    if body.email_report and not SMTP_ENABLED:
        raise HTTPException(422, "Habilite SMTP no servidor antes de agendar envio de relatorios")
    return save(db, Schedule(**body.model_dump(exclude={"query"}),
                             query=body.query.model_dump() if body.query else None,
                             created_by=user.id, next_run_at=utcnow() + timedelta(minutes=body.interval_minutes)), user)


@router.patch("/schedules/{schedule_id}")
def toggle_schedule(schedule_id: int, body: ScheduleState, db: Session = Depends(get_db),
                    user: User = Depends(require_admin)):
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        raise HTTPException(404, "Agendamento nao encontrado")
    schedule.enabled = body.enabled
    schedule.next_run_at = utcnow() + timedelta(minutes=schedule.interval_minutes)
    return save(db, schedule, user, "enable" if body.enabled else "disable")
