"""optimization runs and proposal explanations

Revision ID: 202606300005
Revises: 202606300004
Create Date: 2026-06-30 15:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "202606300005"
down_revision: Union[str, None] = "202606300004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "optimization_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schedule_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("solver_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("solve_time_ms", sa.Integer(), nullable=False),
        sa.Column("objective_value", sa.Integer(), nullable=True),
        sa.Column("warning_before", sa.JSON(), nullable=False),
        sa.Column("warning_after", sa.JSON(), nullable=False),
        sa.Column("changed_segments", sa.Integer(), nullable=False),
        sa.Column("changed_work_shifts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["schedule_version_id"],
            ["schedule_versions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_optimization_runs")),
    )
    op.create_index(
        op.f("ix_optimization_runs_schedule_version_id"),
        "optimization_runs",
        ["schedule_version_id"],
        unique=False,
    )
    op.add_column(
        "optimization_proposals",
        sa.Column("optimization_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        op.f("ix_optimization_proposals_optimization_run_id"),
        "optimization_proposals",
        ["optimization_run_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_optimization_proposals_optimization_run_id_optimization_runs"),
        "optimization_proposals",
        "optimization_runs",
        ["optimization_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("proposal_changes", sa.Column("explanation", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("proposal_changes", "explanation")
    op.drop_constraint(
        op.f("fk_optimization_proposals_optimization_run_id_optimization_runs"),
        "optimization_proposals",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_optimization_proposals_optimization_run_id"),
        table_name="optimization_proposals",
    )
    op.drop_column("optimization_proposals", "optimization_run_id")
    op.drop_index(op.f("ix_optimization_runs_schedule_version_id"), table_name="optimization_runs")
    op.drop_table("optimization_runs")
