"""Initial DataPulse schema; existing unrelated tables are preserved."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.Column("bootstrap_key", sa.String(20), unique=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    definitions = {
        "data_sources": [
            sa.Column("name", sa.String(100), nullable=False, unique=True),
            sa.Column("kind", sa.String(20), nullable=False),
            sa.Column("url", sa.Text), sa.Column("credential_env", sa.String(100)),
        ],
        "datasets": [
            sa.Column("name", sa.String(100), nullable=False, unique=True),
            sa.Column("description", sa.Text, nullable=False),
            sa.Column("source_id", sa.Integer, sa.ForeignKey("data_sources.id"), index=True),
            sa.Column("schema", sa.JSON, nullable=False),
        ],
        "ingestion_jobs": [
            sa.Column("dataset_id", sa.Integer, sa.ForeignKey("datasets.id"), nullable=False, index=True),
            sa.Column("status", sa.String(30), nullable=False, index=True),
            sa.Column("filename", sa.String(255), nullable=False),
            *[sa.Column(n, sa.Integer, nullable=False) for n in
              ("total_rows", "imported_rows", "duplicate_rows", "rejected_rows")],
            sa.Column("errors", sa.JSON, nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True)),
        ],
        "data_records": [
            sa.Column("dataset_id", sa.Integer, sa.ForeignKey("datasets.id"), nullable=False, index=True),
            sa.Column("job_id", sa.Integer, sa.ForeignKey("ingestion_jobs.id"), nullable=False, index=True),
            sa.Column("fingerprint", sa.String(64), nullable=False),
            sa.Column("data", sa.JSON, nullable=False),
        ],
        "kpis": [
            sa.Column("name", sa.String(100), nullable=False, unique=True),
            sa.Column("dataset_id", sa.Integer, sa.ForeignKey("datasets.id"), nullable=False, index=True),
            sa.Column("query", sa.JSON, nullable=False), sa.Column("target", sa.Float),
        ],
        "analytics_results": [
            sa.Column("dataset_id", sa.Integer, sa.ForeignKey("datasets.id"), nullable=False, index=True),
            sa.Column("query", sa.JSON, nullable=False), sa.Column("result", sa.JSON, nullable=False),
        ],
        "insights": [
            sa.Column("dataset_id", sa.Integer, sa.ForeignKey("datasets.id"), nullable=False, index=True),
            sa.Column("rule_key", sa.String(200), nullable=False),
            sa.Column("kind", sa.String(30), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("details", sa.JSON, nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ],
        "alerts": [
            sa.Column("name", sa.String(100), nullable=False, unique=True),
            sa.Column("kpi_id", sa.Integer, sa.ForeignKey("kpis.id"), nullable=False, index=True),
            sa.Column("operator", sa.String(10), nullable=False),
            sa.Column("threshold", sa.Float, nullable=False),
            sa.Column("enabled", sa.Boolean, nullable=False),
            sa.Column("triggered", sa.Boolean, nullable=False),
            sa.Column("last_value", sa.Float),
            sa.Column("evaluated_at", sa.DateTime(timezone=True)),
        ],
        "reports": [
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("dataset_id", sa.Integer, sa.ForeignKey("datasets.id"), nullable=False, index=True),
            sa.Column("query", sa.JSON, nullable=False), sa.Column("result", sa.JSON, nullable=False),
        ],
        "audit_logs": [
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), index=True),
            sa.Column("action", sa.String(100), nullable=False, index=True),
            sa.Column("entity", sa.String(100), nullable=False),
            sa.Column("entity_id", sa.Integer),
        ],
    }
    without_creator = {"data_records", "insights", "audit_logs"}
    for table, columns in definitions.items():
        if table not in without_creator:
            columns.append(sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False))
        op.create_table(
            table, sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), *columns,
        )
    op.create_index("uq_dataset_fingerprint", "data_records", ["dataset_id", "fingerprint"], unique=True)
    op.create_index("uq_insight_rule", "insights", ["dataset_id", "rule_key"], unique=True)


def downgrade():
    for name in (
        "audit_logs", "reports", "alerts", "insights", "analytics_results", "kpis",
        "data_records", "ingestion_jobs", "datasets", "data_sources", "users",
    ):
        op.drop_table(name)
