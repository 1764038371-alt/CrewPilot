"""allow generic work requirements

Revision ID: 202607010007
Revises: 202607010006
Create Date: 2026-07-01
"""

from alembic import op


revision = "202607010007"
down_revision = "202607010006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE shift_requirements
        DROP CONSTRAINT ck_shift_requirements_shift_requirement_target_matches_type
        """
    )
    op.execute(
        """
        ALTER TABLE shift_requirements
        ADD CONSTRAINT ck_shift_requirements_shift_requirement_target_matches_type
        CHECK (
            (requirement_type = 'WORK' AND task_type_id IS NULL)
            OR
            (requirement_type = 'TASK' AND task_type_id IS NOT NULL AND position_id IS NULL)
        )
        """
    )
    op.execute(
        """
        UPDATE shift_requirements
        SET position_id = NULL,
            updated_at = now()
        WHERE requirement_type = 'WORK'
          AND task_type_id IS NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE shift_requirements AS requirement
        SET position_id = fallback_position.id,
            updated_at = now()
        FROM LATERAL (
            SELECT position.id
            FROM positions AS position
            WHERE position.store_id = requirement.store_id
            ORDER BY position.display_order, position.code
            LIMIT 1
        ) AS fallback_position
        WHERE requirement.requirement_type = 'WORK'
          AND requirement.position_id IS NULL
          AND requirement.task_type_id IS NULL
        """
    )
    op.execute(
        """
        ALTER TABLE shift_requirements
        DROP CONSTRAINT ck_shift_requirements_shift_requirement_target_matches_type
        """
    )
    op.execute(
        """
        ALTER TABLE shift_requirements
        ADD CONSTRAINT ck_shift_requirements_shift_requirement_target_matches_type
        CHECK (
            (requirement_type = 'WORK' AND position_id IS NOT NULL AND task_type_id IS NULL)
            OR
            (requirement_type = 'TASK' AND task_type_id IS NOT NULL AND position_id IS NULL)
        )
        """
    )
