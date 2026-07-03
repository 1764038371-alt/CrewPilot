from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ScheduleVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "schedule_versions"
    __table_args__ = (
        UniqueConstraint(
            "planning_period_id",
            "version_number",
            name="uq_schedule_versions_period_version",
        ),
        CheckConstraint("version_number > 0", name="positive_version_number"),
        CheckConstraint("revision >= 0", name="non_negative_revision"),
    )

    planning_period_id: Mapped[UUID] = mapped_column(
        ForeignKey("planning_periods.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[UUID] = mapped_column(ForeignKey("stores.id", ondelete="RESTRICT"))
    parent_schedule_version_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("schedule_versions.id", ondelete="SET NULL")
    )
    published_by_user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_at: Mapped[Optional[datetime]] = mapped_column()
    change_summary: Mapped[Optional[str]] = mapped_column(Text)

    work_shifts: Mapped[list["WorkShift"]] = relationship(back_populates="schedule_version")


class WorkShift(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "work_shifts"
    __table_args__ = (
        CheckConstraint("start_time < end_time", name="work_shift_valid_time_range"),
        CheckConstraint(
            "total_work_minutes >= 0 AND total_break_minutes >= 0",
            name="work_shift_non_negative_minutes",
        ),
    )

    schedule_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("schedule_versions.id", ondelete="CASCADE"), index=True
    )
    staff_member_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff_members.id", ondelete="RESTRICT")
    )
    store_id: Mapped[UUID] = mapped_column(ForeignKey("stores.id", ondelete="RESTRICT"))
    work_date: Mapped[date] = mapped_column(nullable=False)
    start_time: Mapped[time] = mapped_column(nullable=False)
    end_time: Mapped[time] = mapped_column(nullable=False)
    total_work_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_break_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assignment_source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    locked_by_user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    lock_scope: Mapped[Optional[str]] = mapped_column(String(50))
    locked_at: Mapped[Optional[datetime]] = mapped_column()
    lock_reason: Mapped[Optional[str]] = mapped_column(Text)
    note: Mapped[Optional[str]] = mapped_column(Text)

    schedule_version: Mapped[ScheduleVersion] = relationship(back_populates="work_shifts")
    shift_segments: Mapped[list["ShiftSegment"]] = relationship(back_populates="work_shift")


class ShiftSegment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shift_segments"
    __table_args__ = (
        CheckConstraint("start_time < end_time", name="shift_segment_valid_time_range"),
        CheckConstraint(
            "(segment_type = 'WORK' AND position_id IS NOT NULL AND task_type_id IS NULL) OR "
            "(segment_type = 'BREAK' AND position_id IS NULL AND task_type_id IS NULL) OR "
            "(segment_type = 'TASK' AND task_type_id IS NOT NULL AND position_id IS NULL)",
            name="shift_segment_target_matches_type",
        ),
    )

    work_shift_id: Mapped[UUID] = mapped_column(
        ForeignKey("work_shifts.id", ondelete="CASCADE"), index=True
    )
    schedule_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("schedule_versions.id", ondelete="CASCADE")
    )
    store_id: Mapped[UUID] = mapped_column(ForeignKey("stores.id", ondelete="RESTRICT"))
    segment_date: Mapped[date] = mapped_column(nullable=False)
    start_time: Mapped[time] = mapped_column(nullable=False)
    end_time: Mapped[time] = mapped_column(nullable=False)
    segment_type: Mapped[str] = mapped_column(String(50), nullable=False)
    position_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("positions.id", ondelete="RESTRICT")
    )
    task_type_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("task_types.id", ondelete="RESTRICT")
    )
    label: Mapped[Optional[str]] = mapped_column(String(255))
    assignment_source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    locked_by_user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    lock_scope: Mapped[Optional[str]] = mapped_column(String(50))
    locked_at: Mapped[Optional[datetime]] = mapped_column()
    lock_reason: Mapped[Optional[str]] = mapped_column(Text)
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    note: Mapped[Optional[str]] = mapped_column(Text)

    work_shift: Mapped[WorkShift] = relationship(back_populates="shift_segments")


class ScheduleChangeLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "schedule_change_logs"

    schedule_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("schedule_versions.id", ondelete="CASCADE"), index=True
    )
    work_shift_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("work_shifts.id", ondelete="SET NULL")
    )
    shift_segment_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("shift_segments.id", ondelete="SET NULL")
    )
    command_type: Mapped[str] = mapped_column(String(100), nullable=False)
    command_payload: Mapped[Optional[dict]] = mapped_column(JSON)
    inverse_payload: Mapped[Optional[dict]] = mapped_column(JSON)
    executed_by_user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    before_value: Mapped[Optional[dict]] = mapped_column(JSON)
    after_value: Mapped[Optional[dict]] = mapped_column(JSON)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    executed_by: Mapped[str] = mapped_column(String(100), nullable=False, default="manager")
    source_type: Mapped[Optional[str]] = mapped_column(String(50))
    source_id: Mapped[Optional[UUID]] = mapped_column(index=True)
    batch_id: Mapped[Optional[UUID]] = mapped_column(index=True)
    batch_label: Mapped[Optional[str]] = mapped_column(String(255))
    explanation: Mapped[Optional[dict]] = mapped_column(JSON)
    is_undone: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    undone_at: Mapped[Optional[datetime]] = mapped_column()
    parent_change_log_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("schedule_change_logs.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)


class ScheduleWarning(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "schedule_warnings"

    schedule_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("schedule_versions.id", ondelete="CASCADE"), index=True
    )
    work_shift_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("work_shifts.id", ondelete="CASCADE")
    )
    shift_segment_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("shift_segments.id", ondelete="CASCADE")
    )
    warning_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False, default="warning")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSON)


class OptimizationProposal(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "optimization_proposals"

    schedule_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("schedule_versions.id", ondelete="CASCADE"), index=True
    )
    optimization_run_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("optimization_runs.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    summary_metrics: Mapped[Optional[dict]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    generated_by: Mapped[str] = mapped_column(String(50), nullable=False, default="dummy")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    applied_at: Mapped[Optional[datetime]] = mapped_column()
    rejected_at: Mapped[Optional[datetime]] = mapped_column()

    changes: Mapped[list["ProposalChange"]] = relationship(
        back_populates="proposal",
        cascade="all, delete-orphan",
    )


class ProposalChange(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "proposal_changes"

    proposal_id: Mapped[UUID] = mapped_column(
        ForeignKey("optimization_proposals.id", ondelete="CASCADE"), index=True
    )
    change_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[Optional[UUID]] = mapped_column()
    command_type: Mapped[str] = mapped_column(String(100), nullable=False)
    command_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    before_value: Mapped[Optional[dict]] = mapped_column(JSON)
    after_value: Mapped[Optional[dict]] = mapped_column(JSON)
    explanation: Mapped[Optional[dict]] = mapped_column(JSON)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    proposal: Mapped[OptimizationProposal] = relationship(back_populates="changes")


class OptimizationRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "optimization_runs"

    schedule_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("schedule_versions.id", ondelete="CASCADE"), index=True
    )
    solver_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="completed")
    scope: Mapped[dict] = mapped_column(JSON, nullable=False)
    solve_time_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    objective_value: Mapped[Optional[int]] = mapped_column(Integer)
    warning_before: Mapped[dict] = mapped_column(JSON, nullable=False)
    warning_after: Mapped[dict] = mapped_column(JSON, nullable=False)
    changed_segments: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    changed_work_shifts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fairness_score: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
