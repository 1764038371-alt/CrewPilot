"""initial core schema

Revision ID: 202606300001
Revises: 
Create Date: 2026-06-30 00:00:01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "202606300001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stores",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("opening_time", sa.Time(), nullable=False),
        sa.Column("closing_time", sa.Time(), nullable=False),
        sa.Column("time_slot_minutes", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("opening_time < closing_time", name="opening_before_closing"),
        sa.CheckConstraint("time_slot_minutes > 0", name="positive_time_slot_minutes"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stores")),
        sa.UniqueConstraint("code", name=op.f("uq_stores_code")),
    )
    op.create_table(
        "staff_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("employment_type", sa.String(length=50), nullable=False),
        sa.Column("max_weekly_minutes", sa.Integer(), nullable=True),
        sa.Column("min_shift_minutes", sa.Integer(), nullable=True),
        sa.Column("max_shift_minutes", sa.Integer(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("joined_on", sa.Date(), nullable=True),
        sa.Column("left_on", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], name=op.f("fk_staff_members_store_id_stores"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_staff_members")),
    )
    op.create_index(op.f("ix_staff_members_store_id"), "staff_members", ["store_id"], unique=False)
    op.create_table(
        "positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("color", sa.String(length=32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], name=op.f("fk_positions_store_id_stores"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_positions")),
        sa.UniqueConstraint("store_id", "code", name="uq_positions_store_code"),
    )
    op.create_index(op.f("ix_positions_store_id"), "positions", ["store_id"], unique=False)
    op.create_table(
        "task_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("requires_offsite", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], name=op.f("fk_task_types_store_id_stores"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_types")),
        sa.UniqueConstraint("store_id", "code", name="uq_task_types_store_code"),
    )
    op.create_index(op.f("ix_task_types_store_id"), "task_types", ["store_id"], unique=False)
    op.create_table(
        "skill_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("skill_category", sa.String(length=50), nullable=False),
        sa.Column("position_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_type_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"], name=op.f("fk_skill_definitions_position_id_positions"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], name=op.f("fk_skill_definitions_store_id_stores"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["task_type_id"], ["task_types.id"], name=op.f("fk_skill_definitions_task_type_id_task_types"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_skill_definitions")),
        sa.UniqueConstraint("store_id", "code", name="uq_skill_definitions_store_code"),
    )
    op.create_index(op.f("ix_skill_definitions_store_id"), "skill_definitions", ["store_id"], unique=False)
    op.create_table(
        "planning_periods",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("request_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("start_date <= end_date", name="planning_period_valid_date_range"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], name=op.f("fk_planning_periods_store_id_stores"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_planning_periods")),
    )
    op.create_index(op.f("ix_planning_periods_store_id"), "planning_periods", ["store_id"], unique=False)
    op.create_table(
        "staff_skills",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("staff_member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("skill_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("skill_level", sa.Integer(), nullable=False),
        sa.Column("is_preferred", sa.Boolean(), nullable=False),
        sa.Column("certified_at", sa.Date(), nullable=True),
        sa.Column("expires_at", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("skill_level >= 1", name="positive_skill_level"),
        sa.ForeignKeyConstraint(["skill_definition_id"], ["skill_definitions.id"], name=op.f("fk_staff_skills_skill_definition_id_skill_definitions"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["staff_member_id"], ["staff_members.id"], name=op.f("fk_staff_skills_staff_member_id_staff_members"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_staff_skills")),
        sa.UniqueConstraint("staff_member_id", "skill_definition_id", name="uq_staff_skills_staff_skill"),
    )
    op.create_table(
        "shift_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("planning_period_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("staff_member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("request_type", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("(start_time IS NULL AND end_time IS NULL) OR start_time < end_time", name="shift_request_valid_time_range"),
        sa.ForeignKeyConstraint(["planning_period_id"], ["planning_periods.id"], name=op.f("fk_shift_requests_planning_period_id_planning_periods"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["staff_member_id"], ["staff_members.id"], name=op.f("fk_shift_requests_staff_member_id_staff_members"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shift_requests")),
    )
    op.create_index(op.f("ix_shift_requests_planning_period_id"), "shift_requests", ["planning_period_id"], unique=False)
    op.create_index(op.f("ix_shift_requests_staff_member_id"), "shift_requests", ["staff_member_id"], unique=False)
    op.create_table(
        "shift_requirements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("planning_period_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requirement_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("requirement_type", sa.String(length=50), nullable=False),
        sa.Column("position_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_type_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("min_staff_count", sa.Integer(), nullable=False),
        sa.Column("target_staff_count", sa.Integer(), nullable=False),
        sa.Column("max_staff_count", sa.Integer(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("start_time < end_time", name="shift_requirement_valid_time_range"),
        sa.CheckConstraint(
            "(requirement_type = 'WORK' AND position_id IS NOT NULL AND task_type_id IS NULL) OR "
            "(requirement_type = 'TASK' AND task_type_id IS NOT NULL AND position_id IS NULL)",
            name="shift_requirement_target_matches_type",
        ),
        sa.CheckConstraint("min_staff_count >= 0 AND target_staff_count >= min_staff_count", name="shift_requirement_staff_count_order"),
        sa.ForeignKeyConstraint(["planning_period_id"], ["planning_periods.id"], name=op.f("fk_shift_requirements_planning_period_id_planning_periods"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"], name=op.f("fk_shift_requirements_position_id_positions"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], name=op.f("fk_shift_requirements_store_id_stores"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["task_type_id"], ["task_types.id"], name=op.f("fk_shift_requirements_task_type_id_task_types"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shift_requirements")),
    )
    op.create_index(op.f("ix_shift_requirements_planning_period_id"), "shift_requirements", ["planning_period_id"], unique=False)
    op.create_table(
        "shift_requirement_required_skills",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shift_requirement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("skill_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("min_skill_level", sa.Integer(), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("min_skill_level >= 1", name="positive_min_skill_level"),
        sa.ForeignKeyConstraint(["shift_requirement_id"], ["shift_requirements.id"], name=op.f("fk_shift_requirement_required_skills_shift_requirement_id_shift_requirements"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_definition_id"], ["skill_definitions.id"], name=op.f("fk_shift_requirement_required_skills_skill_definition_id_skill_definitions"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shift_requirement_required_skills")),
        sa.UniqueConstraint("shift_requirement_id", "skill_definition_id", name="uq_requirement_required_skill"),
    )
    op.create_table(
        "schedule_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("planning_period_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_schedule_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("is_locked", sa.Boolean(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("version_number > 0", name="positive_version_number"),
        sa.CheckConstraint("revision >= 0", name="non_negative_revision"),
        sa.ForeignKeyConstraint(["parent_schedule_version_id"], ["schedule_versions.id"], name=op.f("fk_schedule_versions_parent_schedule_version_id_schedule_versions"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["planning_period_id"], ["planning_periods.id"], name=op.f("fk_schedule_versions_planning_period_id_planning_periods"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], name=op.f("fk_schedule_versions_store_id_stores"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_schedule_versions")),
        sa.UniqueConstraint("planning_period_id", "version_number", name="uq_schedule_versions_period_version"),
    )
    op.create_index(op.f("ix_schedule_versions_planning_period_id"), "schedule_versions", ["planning_period_id"], unique=False)
    op.create_table(
        "work_shifts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schedule_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("staff_member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("total_work_minutes", sa.Integer(), nullable=False),
        sa.Column("total_break_minutes", sa.Integer(), nullable=False),
        sa.Column("assignment_source", sa.String(length=50), nullable=False),
        sa.Column("is_locked", sa.Boolean(), nullable=False),
        sa.Column("lock_scope", sa.String(length=50), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lock_reason", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("start_time < end_time", name="work_shift_valid_time_range"),
        sa.CheckConstraint("total_work_minutes >= 0 AND total_break_minutes >= 0", name="work_shift_non_negative_minutes"),
        sa.ForeignKeyConstraint(["schedule_version_id"], ["schedule_versions.id"], name=op.f("fk_work_shifts_schedule_version_id_schedule_versions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["staff_member_id"], ["staff_members.id"], name=op.f("fk_work_shifts_staff_member_id_staff_members"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], name=op.f("fk_work_shifts_store_id_stores"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_work_shifts")),
    )
    op.create_index("ix_work_shifts_version_date", "work_shifts", ["schedule_version_id", "work_date"], unique=False)
    op.create_index("ix_work_shifts_version_staff", "work_shifts", ["schedule_version_id", "staff_member_id"], unique=False)
    op.create_table(
        "shift_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_shift_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schedule_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("segment_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("segment_type", sa.String(length=50), nullable=False),
        sa.Column("position_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_type_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("assignment_source", sa.String(length=50), nullable=False),
        sa.Column("is_locked", sa.Boolean(), nullable=False),
        sa.Column("lock_scope", sa.String(length=50), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lock_reason", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("start_time < end_time", name="shift_segment_valid_time_range"),
        sa.CheckConstraint(
            "(segment_type = 'WORK' AND position_id IS NOT NULL AND task_type_id IS NULL) OR "
            "(segment_type = 'BREAK' AND position_id IS NULL AND task_type_id IS NULL) OR "
            "(segment_type = 'TASK' AND task_type_id IS NOT NULL AND position_id IS NULL)",
            name="shift_segment_target_matches_type",
        ),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"], name=op.f("fk_shift_segments_position_id_positions"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["schedule_version_id"], ["schedule_versions.id"], name=op.f("fk_shift_segments_schedule_version_id_schedule_versions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], name=op.f("fk_shift_segments_store_id_stores"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["task_type_id"], ["task_types.id"], name=op.f("fk_shift_segments_task_type_id_task_types"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["work_shift_id"], ["work_shifts.id"], name=op.f("fk_shift_segments_work_shift_id_work_shifts"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shift_segments")),
    )
    op.create_index("ix_shift_segments_version_date", "shift_segments", ["schedule_version_id", "segment_date"], unique=False)
    op.create_index(op.f("ix_shift_segments_work_shift_id"), "shift_segments", ["work_shift_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_shift_segments_work_shift_id"), table_name="shift_segments")
    op.drop_index("ix_shift_segments_version_date", table_name="shift_segments")
    op.drop_table("shift_segments")
    op.drop_index("ix_work_shifts_version_staff", table_name="work_shifts")
    op.drop_index("ix_work_shifts_version_date", table_name="work_shifts")
    op.drop_table("work_shifts")
    op.drop_index(op.f("ix_schedule_versions_planning_period_id"), table_name="schedule_versions")
    op.drop_table("schedule_versions")
    op.drop_table("shift_requirement_required_skills")
    op.drop_index(op.f("ix_shift_requirements_planning_period_id"), table_name="shift_requirements")
    op.drop_table("shift_requirements")
    op.drop_index(op.f("ix_shift_requests_staff_member_id"), table_name="shift_requests")
    op.drop_index(op.f("ix_shift_requests_planning_period_id"), table_name="shift_requests")
    op.drop_table("shift_requests")
    op.drop_table("staff_skills")
    op.drop_index(op.f("ix_planning_periods_store_id"), table_name="planning_periods")
    op.drop_table("planning_periods")
    op.drop_index(op.f("ix_skill_definitions_store_id"), table_name="skill_definitions")
    op.drop_table("skill_definitions")
    op.drop_index(op.f("ix_task_types_store_id"), table_name="task_types")
    op.drop_table("task_types")
    op.drop_index(op.f("ix_positions_store_id"), table_name="positions")
    op.drop_table("positions")
    op.drop_index(op.f("ix_staff_members_store_id"), table_name="staff_members")
    op.drop_table("staff_members")
    op.drop_table("stores")

