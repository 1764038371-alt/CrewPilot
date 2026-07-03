"""weekday and holiday requirement templates

Revision ID: 202607010003
Revises: 202607010002
Create Date: 2026-07-01
"""

from alembic import op


revision = "202607010003"
down_revision = "202607010002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE stores
        SET operational_settings =
            (operational_settings::jsonb
            || jsonb_build_object(
                'weekday_required_staff_templates',
                COALESCE(
                    operational_settings::jsonb -> 'weekday_required_staff_templates',
                    operational_settings::jsonb -> 'required_staff_templates',
                    '[]'::jsonb
                ),
                'holiday_required_staff_templates',
                COALESCE(
                    operational_settings::jsonb -> 'holiday_required_staff_templates',
                    operational_settings::jsonb -> 'required_staff_templates',
                    '[]'::jsonb
                )
            ))::json
        WHERE operational_settings IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE stores
        SET operational_settings =
            (operational_settings::jsonb
                - 'weekday_required_staff_templates'
                - 'holiday_required_staff_templates')::json
        WHERE operational_settings IS NOT NULL
        """
    )
