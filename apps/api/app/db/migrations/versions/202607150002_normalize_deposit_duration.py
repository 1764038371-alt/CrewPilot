"""normalize the deposit task duration to 30 minutes

Revision ID: 202607150002
Revises: 202607150001
Create Date: 2026-07-15
"""

from alembic import op


revision = "202607150002"
down_revision = "202607150001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE task_types
        SET default_duration_minutes = 30,
            description = '前日に受け取った現金を店舗口座へ入金する店舗外業務',
            updated_at = now()
        WHERE code = 'M'
          AND name = '入金'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE task_types
        SET default_duration_minutes = 45,
            description = '店舗外で行う入金業務',
            updated_at = now()
        WHERE code = 'M'
          AND name = '入金'
        """
    )
