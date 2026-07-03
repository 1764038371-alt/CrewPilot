"""normalize opening and closing skill names

Revision ID: 202607010005
Revises: 202607010004
Create Date: 2026-07-01
"""

from alembic import op


revision = "202607010005"
down_revision = "202607010004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE skill_definitions
        SET name = CASE code
            WHEN 'B_OPEN' THEN 'オープンB'
            WHEN 'C_OPEN' THEN 'オープンC'
            WHEN 'B_CLOSE' THEN 'クローズB'
            WHEN 'C_CLOSE' THEN 'クローズC'
            WHEN 'F_CLOSE' THEN 'クローズF'
            ELSE name
        END,
            updated_at = now()
        WHERE code IN ('B_OPEN', 'C_OPEN', 'B_CLOSE', 'C_CLOSE', 'F_CLOSE')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE skill_definitions
        SET name = CASE code
            WHEN 'B_OPEN' THEN 'オープンB'
            WHEN 'C_OPEN' THEN 'オープンC'
            WHEN 'B_CLOSE' THEN 'クローズB'
            WHEN 'C_CLOSE' THEN 'クローズC'
            WHEN 'F_CLOSE' THEN 'クローズF'
            ELSE name
        END,
            updated_at = now()
        WHERE code IN ('B_OPEN', 'C_OPEN', 'B_CLOSE', 'C_CLOSE', 'F_CLOSE')
        """
    )
