"""phase2 generation metrics

Revision ID: 202606300006
Revises: 202606300005
Create Date: 2026-06-30 16:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "202606300006"
down_revision: Union[str, None] = "202606300005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("optimization_proposals", sa.Column("summary_metrics", sa.JSON(), nullable=True))
    op.add_column("optimization_runs", sa.Column("fairness_score", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("optimization_runs", "fairness_score")
    op.drop_column("optimization_proposals", "summary_metrics")
