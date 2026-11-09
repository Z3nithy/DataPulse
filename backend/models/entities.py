from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Timestamp:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Timestamp, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20), default="viewer")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    bootstrap_key: Mapped[str | None] = mapped_column(String(20), unique=True)


class DataSource(Timestamp, Base):
    __tablename__ = "data_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    kind: Mapped[str] = mapped_column(String(20))
    url: Mapped[str | None] = mapped_column(Text)
    credential_env: Mapped[str | None] = mapped_column(String(100))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class Dataset(Timestamp, Base):
    __tablename__ = "datasets"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.id"), index=True)
    schema: Mapped[list[dict]] = mapped_column(JSON, default=list)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    records: Mapped[list["DataRecord"]] = relationship(back_populates="dataset")


class IngestionJob(Timestamp, Base):
    __tablename__ = "ingestion_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="processing", index=True)
    filename: Mapped[str] = mapped_column(String(255))
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    imported_rows: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_rows: Mapped[int] = mapped_column(Integer, default=0)
    rejected_rows: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list[dict]] = mapped_column(JSON, default=list)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class DataRecord(Timestamp, Base):
    __tablename__ = "data_records"
    __table_args__ = (Index("uq_dataset_fingerprint", "dataset_id", "fingerprint", unique=True),)
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"), index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("ingestion_jobs.id"), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    data: Mapped[dict] = mapped_column(JSON)
    dataset: Mapped[Dataset] = relationship(back_populates="records")


class KPI(Timestamp, Base):
    __tablename__ = "kpis"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"), index=True)
    query: Mapped[dict] = mapped_column(JSON)
    target: Mapped[float | None] = mapped_column(Float)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class AnalyticsResult(Timestamp, Base):
    __tablename__ = "analytics_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"), index=True)
    query: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class Insight(Timestamp, Base):
    __tablename__ = "insights"
    __table_args__ = (Index("uq_insight_rule", "dataset_id", "rule_key", unique=True),)
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"), index=True)
    rule_key: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    details: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Alert(Timestamp, Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    kpi_id: Mapped[int] = mapped_column(ForeignKey("kpis.id"), index=True)
    operator: Mapped[str] = mapped_column(String(10))
    threshold: Mapped[float] = mapped_column(Float)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    last_value: Mapped[float | None] = mapped_column(Float)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class Report(Timestamp, Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"), index=True)
    query: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class AuditLog(Timestamp, Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[int | None] = mapped_column(Integer)


class Notification(Timestamp, Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    href: Mapped[str] = mapped_column(String(100))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class Favorite(Timestamp, Base):
    __tablename__ = "favorites"
    __table_args__ = (Index("uq_favorite_user_name", "user_id", "name", unique=True),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"))
    query: Mapped[dict] = mapped_column(JSON)


class Schedule(Timestamp, Base):
    __tablename__ = "schedules"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(20))
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"))
    query: Mapped[dict | None] = mapped_column(JSON)
    interval_minutes: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    email_report: Mapped[bool] = mapped_column(Boolean, default=False)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(30))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class BackgroundTask(Timestamp, Base):
    __tablename__ = "background_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"))
    schedule_id: Mapped[int | None] = mapped_column(ForeignKey("schedules.id"), index=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("ingestion_jobs.id"))
    report_id: Mapped[int | None] = mapped_column(ForeignKey("reports.id"))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    file_content: Mapped[bytes | None] = mapped_column(LargeBinary)
    error: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class EmailDelivery(Timestamp, Base):
    __tablename__ = "email_deliveries"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    report_id: Mapped[int | None] = mapped_column(ForeignKey("reports.id"))
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeat"
    id: Mapped[int] = mapped_column(primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
