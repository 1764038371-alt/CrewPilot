"""position based opening and closing skills

Revision ID: 202607010002
Revises: 202607010001
Create Date: 2026-07-01
"""

from alembic import op


revision = "202607010002"
down_revision = "202607010001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute(
        """
        WITH position_rows AS (
            SELECT store_id, id AS position_id, code
            FROM positions
            WHERE code IN ('B', 'C', 'F', 'S')
        )
        INSERT INTO skill_definitions (
            id,
            store_id,
            code,
            name,
            skill_category,
            position_id,
            task_type_id,
            description,
            is_active,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            store_id,
            code,
            CASE code
                WHEN 'B' THEN 'バリ'
                WHEN 'C' THEN 'キャッシャー'
                WHEN 'F' THEN 'フロア'
                WHEN 'S' THEN 'サブ'
            END,
            'position',
            position_id,
            NULL,
            NULL,
            TRUE,
            now(),
            now()
        FROM position_rows
        ON CONFLICT (store_id, code) DO UPDATE
        SET skill_category = 'position',
            position_id = EXCLUDED.position_id,
            task_type_id = NULL,
            updated_at = now()
        """
    )
    op.execute(
        """
        WITH position_rows AS (
            SELECT store_id, id AS position_id, code
            FROM positions
            WHERE code IN ('B', 'C')
        )
        INSERT INTO skill_definitions (
            id,
            store_id,
            code,
            name,
            skill_category,
            position_id,
            task_type_id,
            description,
            is_active,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            store_id,
            code || '_OPEN',
            CASE code
                WHEN 'B' THEN 'オープンB'
                WHEN 'C' THEN 'オープンC'
            END,
            'opening',
            position_id,
            NULL,
            NULL,
            TRUE,
            now(),
            now()
        FROM position_rows
        ON CONFLICT (store_id, code) DO UPDATE
        SET skill_category = 'opening',
            position_id = EXCLUDED.position_id,
            task_type_id = NULL,
            updated_at = now()
        """
    )
    op.execute(
        """
        WITH position_rows AS (
            SELECT store_id, id AS position_id, code
            FROM positions
            WHERE code IN ('B', 'C', 'F')
        )
        INSERT INTO skill_definitions (
            id,
            store_id,
            code,
            name,
            skill_category,
            position_id,
            task_type_id,
            description,
            is_active,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            store_id,
            code || '_CLOSE',
            CASE code
                WHEN 'B' THEN 'クローズB'
                WHEN 'C' THEN 'クローズC'
                WHEN 'F' THEN 'クローズF'
            END,
            'closing',
            position_id,
            NULL,
            NULL,
            TRUE,
            now(),
            now()
        FROM position_rows
        ON CONFLICT (store_id, code) DO UPDATE
        SET skill_category = 'closing',
            position_id = EXCLUDED.position_id,
            task_type_id = NULL,
            updated_at = now()
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM skill_definitions
        WHERE code IN ('B_OPEN', 'B_CLOSE', 'C_CLOSE', 'F_CLOSE', 'F', 'S', 'B')
        """
    )
