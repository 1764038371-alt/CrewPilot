"""users auth

Revision ID: 202606300008
Revises: 202606300007
Create Date: 2026-06-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "202606300008"
down_revision = "202606300007"
branch_labels = None
depends_on = None


PASSWORD_HASH = (
    "pbkdf2_sha256$crewpilot-demo-salt$"
    "38986406ed5f5d82878a3f3d92c20d631580b14b47ccd1d031cbd90be257a0f4"
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)
    op.create_table(
        "user_sessions",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_user_sessions_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_sessions")),
        sa.UniqueConstraint("session_token_hash", name=op.f("uq_user_sessions_session_token_hash")),
    )
    op.create_index(op.f("ix_user_sessions_user_id"), "user_sessions", ["user_id"], unique=False)
    op.add_column("schedule_change_logs", sa.Column("executed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_schedule_change_logs_executed_by_user_id_users", "schedule_change_logs", "users", ["executed_by_user_id"], ["id"], ondelete="SET NULL")
    op.add_column("schedule_versions", sa.Column("published_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_schedule_versions_published_by_user_id_users", "schedule_versions", "users", ["published_by_user_id"], ["id"], ondelete="SET NULL")
    op.add_column("work_shifts", sa.Column("locked_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_work_shifts_locked_by_user_id_users", "work_shifts", "users", ["locked_by_user_id"], ["id"], ondelete="SET NULL")
    op.add_column("shift_segments", sa.Column("locked_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_shift_segments_locked_by_user_id_users", "shift_segments", "users", ["locked_by_user_id"], ["id"], ondelete="SET NULL")

    users_table = sa.table(
        "users",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("email", sa.String),
        sa.column("display_name", sa.String),
        sa.column("role", sa.String),
        sa.column("password_hash", sa.String),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        users_table,
        [
            {
                "id": "01000000-0000-0000-0000-000000000001",
                "email": "admin@example.com",
                "display_name": "Admin User",
                "role": "admin",
                "password_hash": PASSWORD_HASH,
                "is_active": True,
            },
            {
                "id": "01000000-0000-0000-0000-000000000002",
                "email": "manager@example.com",
                "display_name": "Manager User",
                "role": "manager",
                "password_hash": PASSWORD_HASH,
                "is_active": True,
            },
            {
                "id": "01000000-0000-0000-0000-000000000003",
                "email": "viewer@example.com",
                "display_name": "Viewer User",
                "role": "viewer",
                "password_hash": PASSWORD_HASH,
                "is_active": True,
            },
        ],
    )


def downgrade() -> None:
    op.drop_constraint("fk_shift_segments_locked_by_user_id_users", "shift_segments", type_="foreignkey")
    op.drop_column("shift_segments", "locked_by_user_id")
    op.drop_constraint("fk_work_shifts_locked_by_user_id_users", "work_shifts", type_="foreignkey")
    op.drop_column("work_shifts", "locked_by_user_id")
    op.drop_constraint("fk_schedule_versions_published_by_user_id_users", "schedule_versions", type_="foreignkey")
    op.drop_column("schedule_versions", "published_by_user_id")
    op.drop_constraint("fk_schedule_change_logs_executed_by_user_id_users", "schedule_change_logs", type_="foreignkey")
    op.drop_column("schedule_change_logs", "executed_by_user_id")
    op.drop_index(op.f("ix_user_sessions_user_id"), table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
