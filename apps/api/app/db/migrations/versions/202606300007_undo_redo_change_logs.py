"""undo redo change logs

Revision ID: 202606300007
Revises: 202606300006
Create Date: 2026-06-30 17:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "202606300007"
down_revision: Union[str, None] = "202606300006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("schedule_change_logs", sa.Column("command_payload", sa.JSON(), nullable=True))
    op.add_column("schedule_change_logs", sa.Column("inverse_payload", sa.JSON(), nullable=True))
    op.add_column(
        "schedule_change_logs",
        sa.Column("is_undone", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("schedule_change_logs", sa.Column("undone_at", sa.DateTime(), nullable=True))
    op.add_column(
        "schedule_change_logs",
        sa.Column("parent_change_log_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_schedule_change_logs_parent_change_log_id_schedule_change_logs"),
        "schedule_change_logs",
        "schedule_change_logs",
        ["parent_change_log_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column("schedule_change_logs", "is_undone", server_default=None)


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_schedule_change_logs_parent_change_log_id_schedule_change_logs"),
        "schedule_change_logs",
        type_="foreignkey",
    )
    op.drop_column("schedule_change_logs", "parent_change_log_id")
    op.drop_column("schedule_change_logs", "undone_at")
    op.drop_column("schedule_change_logs", "is_undone")
    op.drop_column("schedule_change_logs", "inverse_payload")
    op.drop_column("schedule_change_logs", "command_payload")
