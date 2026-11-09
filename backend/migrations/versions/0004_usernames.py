"""Add usernames and make contact emails optional."""
import re

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _username_for(email: str | None, user_id: int, used: set[str]) -> str:
    local_part = (email or "").split("@", 1)[0].lower()
    base = re.sub(r"[^a-z0-9._-]", "-", local_part).strip("._-")
    if len(base) < 3:
        base = f"user{user_id}"
    base = base[:32]
    username = base
    suffix = 2
    while username in used:
        ending = f"-{suffix}"
        username = f"{base[:32 - len(ending)]}{ending}"
        suffix += 1
    return username


def upgrade():
    connection = op.get_bind()
    op.add_column("users", sa.Column("username", sa.String(32), nullable=True))
    users = connection.execute(sa.text("SELECT id, email FROM users ORDER BY id")).all()
    used = set()
    for user_id, email in users:
        username = _username_for(email, user_id, used)
        used.add(username)
        connection.execute(
            sa.text("UPDATE users SET username = :username WHERE id = :user_id"),
            {"username": username, "user_id": user_id},
        )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    with op.batch_alter_table("users") as batch:
        batch.alter_column("username", existing_type=sa.String(32), nullable=False)
        batch.alter_column("email", existing_type=sa.String(254), nullable=True)


def downgrade():
    connection = op.get_bind()
    connection.execute(sa.text(
        "UPDATE users SET email = username || '@local.invalid' WHERE email IS NULL"
    ))
    op.drop_index("ix_users_username", table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.alter_column("email", existing_type=sa.String(254), nullable=False)
        batch.drop_column("username")
