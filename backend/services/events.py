import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import SMTP_ENABLED
from models import AuditLog, EmailDelivery, Notification, User

logger = logging.getLogger("datapulse")


def audit(db: Session, user_id: int | None, action: str, entity: str, entity_id: int | None):
    db.add(AuditLog(user_id=user_id, action=action, entity=entity, entity_id=entity_id))
    logger.info("audit action=%s entity=%s id=%s user=%s", action, entity, entity_id, user_id)


def notify(db: Session, kind: str, title: str, message: str, href: str,
           user_id: int | None = None, email: bool = False, report_id: int | None = None):
    statement = select(User).where(User.active.is_(True))
    if user_id is not None:
        statement = statement.where(User.id == user_id)
    for user in db.scalars(statement):
        db.add(Notification(user_id=user.id, kind=kind, title=title[:200], message=message, href=href))
        if email and SMTP_ENABLED and user.email:
            db.add(EmailDelivery(user_id=user.id, subject=title[:200], body=message, report_id=report_id))
