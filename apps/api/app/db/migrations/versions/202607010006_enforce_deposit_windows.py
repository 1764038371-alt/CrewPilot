"""enforce deposit task windows

Revision ID: 202607010006
Revises: 202607010005
Create Date: 2026-07-01
"""

from alembic import op


revision = "202607010006"
down_revision = "202607010005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE shift_requirements
        SET start_time = TIME '10:00',
            end_time = TIME '10:30',
            max_staff_count = 1,
            target_staff_count = 1,
            updated_at = now()
        WHERE requirement_type = 'TASK'
          AND task_type_id IN (SELECT id FROM task_types WHERE code = 'M')
        """
    )
    op.execute(
        """
        DELETE FROM shift_segments AS segment
        USING task_types AS task_type
        WHERE segment.task_type_id = task_type.id
          AND task_type.code = 'M'
          AND NOT (
            (segment.start_time = TIME '10:00' AND segment.end_time = TIME '10:30')
            OR EXISTS (
                SELECT 1
                FROM work_shifts AS shift
                JOIN stores AS store ON store.id = shift.store_id
                WHERE shift.id = segment.work_shift_id
                  AND segment.segment_date = shift.work_date
                  AND segment.start_time = store.closing_time - INTERVAL '30 minutes'
                  AND segment.end_time = store.closing_time
            )
          )
        """
    )


def downgrade() -> None:
    pass
