"""operational flow settings

Revision ID: 202607010001
Revises: 202606300009
Create Date: 2026-07-01
"""

from alembic import op
import sqlalchemy as sa


revision = "202607010001"
down_revision = "202606300009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stores", sa.Column("business_hours", sa.JSON(), nullable=True))
    op.add_column("stores", sa.Column("operational_settings", sa.JSON(), nullable=True))
    op.add_column("staff_members", sa.Column("employee_number", sa.String(length=64), nullable=True))
    op.add_column("staff_members", sa.Column("hourly_wage_yen", sa.Integer(), nullable=True))
    op.create_unique_constraint(
        "uq_staff_members_store_employee_number",
        "staff_members",
        ["store_id", "employee_number"],
    )
    op.execute(
        """
        UPDATE staff_members
        SET employee_number = CASE
            WHEN display_name = '田中' THEN '101'
            WHEN display_name = '佐藤' THEN '102'
            WHEN display_name = '鈴木' THEN '103'
            ELSE LEFT(id::text, 8)
        END
        WHERE employee_number IS NULL
        """
    )
    op.execute("UPDATE staff_members SET hourly_wage_yen = 1200 WHERE hourly_wage_yen IS NULL")
    op.execute(
        """
        UPDATE stores
        SET business_hours = json_build_object(
            'weekday', json_build_object('open', to_char(opening_time, 'HH24:MI'), 'close', to_char(closing_time, 'HH24:MI')),
            'holiday', json_build_object('open', '10:00', 'close', '18:00'),
            'daily', json_build_object(
                'monday', json_build_object('open', to_char(opening_time, 'HH24:MI'), 'close', to_char(closing_time, 'HH24:MI')),
                'tuesday', json_build_object('open', to_char(opening_time, 'HH24:MI'), 'close', to_char(closing_time, 'HH24:MI')),
                'wednesday', json_build_object('open', to_char(opening_time, 'HH24:MI'), 'close', to_char(closing_time, 'HH24:MI')),
                'thursday', json_build_object('open', to_char(opening_time, 'HH24:MI'), 'close', to_char(closing_time, 'HH24:MI')),
                'friday', json_build_object('open', to_char(opening_time, 'HH24:MI'), 'close', to_char(closing_time, 'HH24:MI')),
                'saturday', json_build_object('open', '10:00', 'close', '18:00'),
                'sunday', json_build_object('open', '10:00', 'close', '18:00')
            )
        )
        WHERE business_hours IS NULL
        """
    )
    op.execute(
        """
        UPDATE stores
        SET operational_settings = json_build_object(
            'required_staff_templates', json_build_array(
                json_build_object('start_time', '09:00', 'end_time', '12:00', 'target_staff_count', 2),
                json_build_object('start_time', '12:00', 'end_time', '15:00', 'target_staff_count', 3),
                json_build_object('start_time', '15:00', 'end_time', '18:00', 'target_staff_count', 2)
            ),
            'deposit_rule', json_build_object(
                'primary_start', '10:00',
                'primary_end', '10:30',
                'fallback', 'previous_day_close_30_minutes'
            )
        )
        WHERE operational_settings IS NULL
        """
    )


def downgrade() -> None:
    op.drop_constraint("uq_staff_members_store_employee_number", "staff_members", type_="unique")
    op.drop_column("staff_members", "hourly_wage_yen")
    op.drop_column("staff_members", "employee_number")
    op.drop_column("stores", "operational_settings")
    op.drop_column("stores", "business_hours")
