"""Persistent events, personal favorites, queue and schedules."""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    definitions = {
        "notifications": [
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("kind", sa.String(30), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("message", sa.Text, nullable=False),
            sa.Column("href", sa.String(100), nullable=False),
            sa.Column("read_at", sa.DateTime(timezone=True), index=True),
        ],
        "favorites": [
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("dataset_id", sa.Integer, sa.ForeignKey("datasets.id"), nullable=False),
            sa.Column("query", sa.JSON, nullable=False),
        ],
        "schedules": [
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("kind", sa.String(20), nullable=False),
            sa.Column("dataset_id", sa.Integer, sa.ForeignKey("datasets.id"), nullable=False),
            sa.Column("query", sa.JSON),
            sa.Column("interval_minutes", sa.Integer, nullable=False),
            sa.Column("enabled", sa.Boolean, nullable=False),
            sa.Column("email_report", sa.Boolean, nullable=False),
            sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False, index=True),
            sa.Column("last_run_at", sa.DateTime(timezone=True)),
            sa.Column("last_status", sa.String(30)),
            sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        ],
        "background_tasks": [
            sa.Column("kind", sa.String(20), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, index=True),
            sa.Column("dataset_id", sa.Integer, sa.ForeignKey("datasets.id"), nullable=False),
            sa.Column("schedule_id", sa.Integer, sa.ForeignKey("schedules.id"), index=True),
            sa.Column("job_id", sa.Integer, sa.ForeignKey("ingestion_jobs.id")),
            sa.Column("report_id", sa.Integer, sa.ForeignKey("reports.id")),
            sa.Column("payload", sa.JSON, nullable=False),
            sa.Column("file_content", sa.LargeBinary),
            sa.Column("error", sa.Text),
            sa.Column("finished_at", sa.DateTime(timezone=True)),
            sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        ],
        "email_deliveries": [
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
            sa.Column("subject", sa.String(200), nullable=False),
            sa.Column("body", sa.Text, nullable=False),
            sa.Column("report_id", sa.Integer, sa.ForeignKey("reports.id")),
            sa.Column("status", sa.String(30), nullable=False, index=True),
            sa.Column("attempts", sa.Integer, nullable=False),
            sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("error", sa.Text),
            sa.Column("sent_at", sa.DateTime(timezone=True)),
        ],
    }
    for name, columns in definitions.items():
        op.create_table(name, sa.Column("id", sa.Integer, primary_key=True),
                        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), *columns)
    op.create_index("uq_favorite_user_name", "favorites", ["user_id", "name"], unique=True)
    op.create_table("worker_heartbeat", sa.Column("id", sa.Integer, primary_key=True),
                    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    for name in ("worker_heartbeat", "email_deliveries", "background_tasks", "schedules", "favorites", "notifications"):
        op.drop_table(name)
