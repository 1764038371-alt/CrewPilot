"""audit log metadata

Revision ID: 202606300009
Revises: 202606300008
Create Date: 2026-06-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "202606300009"
down_revision = "202606300008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("schedule_change_logs", sa.Column("source_type", sa.String(length=50), nullable=True))
    op.add_column("schedule_change_logs", sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("schedule_change_logs", sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("schedule_change_logs", sa.Column("batch_label", sa.String(length=255), nullable=True))
    op.add_column("schedule_change_logs", sa.Column("explanation", sa.JSON(), nullable=True))
    op.create_index(
        op.f("ix_schedule_change_logs_source_id"),
        "schedule_change_logs",
        ["source_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_schedule_change_logs_batch_id"),
        "schedule_change_logs",
        ["batch_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_schedule_change_logs_batch_id"), table_name="schedule_change_logs")
    op.drop_index(op.f("ix_schedule_change_logs_source_id"), table_name="schedule_change_logs")
    op.drop_column("schedule_change_logs", "explanation")
    op.drop_column("schedule_change_logs", "batch_label")
    op.drop_column("schedule_change_logs", "batch_id")
    op.drop_column("schedule_change_logs", "source_id")
    op.drop_column("schedule_change_logs", "source_type")
