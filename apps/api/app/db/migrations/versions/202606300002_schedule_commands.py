"""schedule commands

Revision ID: 202606300002
Revises: 202606300001
Create Date: 2026-06-30 01:40:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "202606300002"
down_revision: Union[str, None] = "202606300001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "schedule_change_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schedule_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_shift_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("shift_segment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("command_type", sa.String(length=100), nullable=False),
        sa.Column("before_value", sa.JSON(), nullable=True),
        sa.Column("after_value", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["schedule_version_id"], ["schedule_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shift_segment_id"], ["shift_segments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["work_shift_id"], ["work_shifts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_schedule_change_logs")),
    )
    op.create_index(
        op.f("ix_schedule_change_logs_schedule_version_id"),
        "schedule_change_logs",
        ["schedule_version_id"],
        unique=False,
    )
    op.create_table(
        "schedule_warnings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schedule_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_shift_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("shift_segment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("warning_type", sa.String(length=100), nullable=False),
        sa.Column("severity", sa.String(length=50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["schedule_version_id"], ["schedule_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shift_segment_id"], ["shift_segments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_shift_id"], ["work_shifts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_schedule_warnings")),
    )
    op.create_index(
        op.f("ix_schedule_warnings_schedule_version_id"),
        "schedule_warnings",
        ["schedule_version_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_schedule_warnings_schedule_version_id"), table_name="schedule_warnings")
    op.drop_table("schedule_warnings")
    op.drop_index(op.f("ix_schedule_change_logs_schedule_version_id"), table_name="schedule_change_logs")
    op.drop_table("schedule_change_logs")

