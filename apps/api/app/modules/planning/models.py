from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PlanningPeriod(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "planning_periods"
    __table_args__ = (
        CheckConstraint("start_date <= end_date", name="planning_period_valid_date_range"),
    )

    store_id: Mapped[UUID] = mapped_column(ForeignKey("stores.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(nullable=False)
    end_date: Mapped[date] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    request_deadline: Mapped[Optional[datetime]] = mapped_column()

    shift_requests: Mapped[list["ShiftRequest"]] = relationship(back_populates="planning_period")
    shift_requirements: Mapped[list["ShiftRequirement"]] = relationship(
        back_populates="planning_period"
    )


class ShiftRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shift_requests"
    __table_args__ = (
        CheckConstraint(
            "(start_time IS NULL AND end_time IS NULL) OR start_time < end_time",
            name="shift_request_valid_time_range",
        ),
    )

    planning_period_id: Mapped[UUID] = mapped_column(
        ForeignKey("planning_periods.id", ondelete="CASCADE"), index=True
    )
    staff_member_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff_members.id", ondelete="CASCADE"), index=True
    )
    request_date: Mapped[date] = mapped_column(nullable=False)
    start_time: Mapped[Optional[time]] = mapped_column()
    end_time: Mapped[Optional[time]] = mapped_column()
    request_type: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    note: Mapped[Optional[str]] = mapped_column(Text)

    planning_period: Mapped[PlanningPeriod] = relationship(back_populates="shift_requests")


class ShiftRequirement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shift_requirements"
    __table_args__ = (
        CheckConstraint("start_time < end_time", name="shift_requirement_valid_time_range"),
        CheckConstraint(
            "(requirement_type = 'WORK' AND task_type_id IS NULL) OR "
            "(requirement_type = 'TASK' AND task_type_id IS NOT NULL AND position_id IS NULL)",
            name="shift_requirement_target_matches_type",
        ),
        CheckConstraint(
            "min_staff_count >= 0 AND target_staff_count >= min_staff_count",
            name="shift_requirement_staff_count_order",
        ),
    )

    planning_period_id: Mapped[UUID] = mapped_column(
        ForeignKey("planning_periods.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[UUID] = mapped_column(ForeignKey("stores.id", ondelete="RESTRICT"))
    requirement_date: Mapped[date] = mapped_column(nullable=False)
    start_time: Mapped[time] = mapped_column(nullable=False)
    end_time: Mapped[time] = mapped_column(nullable=False)
    requirement_type: Mapped[str] = mapped_column(String(50), nullable=False)
    position_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("positions.id", ondelete="RESTRICT")
    )
    task_type_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("task_types.id", ondelete="RESTRICT")
    )
    min_staff_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    target_staff_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_staff_count: Mapped[Optional[int]] = mapped_column(Integer)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    planning_period: Mapped[PlanningPeriod] = relationship(back_populates="shift_requirements")
    required_skills: Mapped[list["ShiftRequirementRequiredSkill"]] = relationship(
        back_populates="shift_requirement"
    )


class ShiftRequirementRequiredSkill(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "shift_requirement_required_skills"
    __table_args__ = (
        UniqueConstraint(
            "shift_requirement_id",
            "skill_definition_id",
            name="uq_requirement_required_skill",
        ),
        CheckConstraint("min_skill_level >= 1", name="positive_min_skill_level"),
    )

    shift_requirement_id: Mapped[UUID] = mapped_column(
        ForeignKey("shift_requirements.id", ondelete="CASCADE")
    )
    skill_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("skill_definitions.id", ondelete="RESTRICT")
    )
    min_skill_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    shift_requirement: Mapped[ShiftRequirement] = relationship(back_populates="required_skills")
