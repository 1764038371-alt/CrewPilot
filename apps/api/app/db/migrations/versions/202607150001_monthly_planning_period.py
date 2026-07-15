"""extend the sample planning period to a full month

Revision ID: 202607150001
Revises: 202607010007
Create Date: 2026-07-15
"""

from alembic import op


revision = "202607150001"
down_revision = "202607010007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE planning_periods
        SET name = '2026年7月シフト',
            end_date = DATE '2026-07-31',
            updated_at = now()
        WHERE id = '20000000-0000-0000-0000-000000000001'
          AND start_date = DATE '2026-07-01'
          AND end_date = DATE '2026-07-15'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE planning_periods
        SET name = '2026年7月前半シフト',
            end_date = DATE '2026-07-15',
            updated_at = now()
        WHERE id = '20000000-0000-0000-0000-000000000001'
          AND start_date = DATE '2026-07-01'
          AND end_date = DATE '2026-07-31'
        """
    )
