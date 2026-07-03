"""optimization proposals

Revision ID: 202606300003
Revises: 202606300002
Create Date: 2026-06-30 11:20:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "202606300003"
down_revision: Union[str, None] = "202606300002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "optimization_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schedule_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("generated_by", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["schedule_version_id"], ["schedule_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_optimization_proposals")),
    )
    op.create_index(
        op.f("ix_optimization_proposals_schedule_version_id"),
        "optimization_proposals",
        ["schedule_version_id"],
        unique=False,
    )
    op.create_table(
        "proposal_changes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("change_type", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=100), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("command_type", sa.String(length=100), nullable=False),
        sa.Column("command_payload", sa.JSON(), nullable=False),
        sa.Column("before_value", sa.JSON(), nullable=True),
        sa.Column("after_value", sa.JSON(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["proposal_id"], ["optimization_proposals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_proposal_changes")),
    )
    op.create_index(
        op.f("ix_proposal_changes_proposal_id"),
        "proposal_changes",
        ["proposal_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_proposal_changes_proposal_id"), table_name="proposal_changes")
    op.drop_table("proposal_changes")
    op.drop_index(
        op.f("ix_optimization_proposals_schedule_version_id"),
        table_name="optimization_proposals",
    )
    op.drop_table("optimization_proposals")
