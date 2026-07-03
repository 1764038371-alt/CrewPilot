"""normalize position display names

Revision ID: 202607010004
Revises: 202607010003
Create Date: 2026-07-01
"""

from alembic import op


revision = "202607010004"
down_revision = "202607010003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE positions
        SET name = CASE code
            WHEN 'B' THEN 'バリ'
            WHEN 'C' THEN 'キャッシャー'
            WHEN 'F' THEN 'フロア'
            WHEN 'S' THEN 'サブ'
            ELSE name
        END,
            updated_at = now()
        WHERE code IN ('B', 'C', 'F', 'S')
        """
    )
    op.execute(
        """
        UPDATE skill_definitions
        SET name = CASE code
            WHEN 'B' THEN 'バリ'
            WHEN 'C' THEN 'キャッシャー'
            WHEN 'F' THEN 'フロア'
            WHEN 'S' THEN 'サブ'
            WHEN 'M' THEN '入金'
            ELSE name
        END,
            updated_at = now()
        WHERE code IN ('B', 'C', 'F', 'S', 'M')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE positions
        SET name = CASE code
            WHEN 'B' THEN 'バリ'
            WHEN 'S' THEN 'サブ'
            ELSE name
        END,
            updated_at = now()
        WHERE code IN ('B', 'S')
        """
    )
