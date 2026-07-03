"""schedule history actor

Revision ID: 202606300004
Revises: 202606300003
Create Date: 2026-06-30 12:20:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "202606300004"
down_revision: Union[str, None] = "202606300003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "schedule_change_logs",
        sa.Column("executed_by", sa.String(length=100), nullable=False, server_default="manager"),
    )
    op.alter_column("schedule_change_logs", "executed_by", server_default=None)


def downgrade() -> None:
    op.drop_column("schedule_change_logs", "executed_by")
