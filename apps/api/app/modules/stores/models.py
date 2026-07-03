from __future__ import annotations

from datetime import date, time
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.modules.staff.models import StaffMember


class Store(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stores"
    __table_args__ = (
        CheckConstraint("opening_time < closing_time", name="opening_before_closing"),
        CheckConstraint("time_slot_minutes > 0", name="positive_time_slot_minutes"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Tokyo")
    opening_time: Mapped[time] = mapped_column(nullable=False)
    closing_time: Mapped[time] = mapped_column(nullable=False)
    business_hours: Mapped[Optional[dict]] = mapped_column(JSON)
    operational_settings: Mapped[Optional[dict]] = mapped_column(JSON)
    time_slot_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    positions: Mapped[list["Position"]] = relationship(back_populates="store")
    task_types: Mapped[list["TaskType"]] = relationship(back_populates="store")
    skill_definitions: Mapped[list["SkillDefinition"]] = relationship(back_populates="store")


class Position(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "positions"
    __table_args__ = (UniqueConstraint("store_id", "code", name="uq_positions_store_code"),)

    store_id: Mapped[UUID] = mapped_column(ForeignKey("stores.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    color: Mapped[Optional[str]] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    store: Mapped[Store] = relationship(back_populates="positions")
    skill_definitions: Mapped[list["SkillDefinition"]] = relationship(back_populates="position")


class TaskType(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "task_types"
    __table_args__ = (UniqueConstraint("store_id", "code", name="uq_task_types_store_code"),)

    store_id: Mapped[UUID] = mapped_column(ForeignKey("stores.id", ondelete="RESTRICT"), index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    default_duration_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    requires_offsite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    store: Mapped[Store] = relationship(back_populates="task_types")
    skill_definitions: Mapped[list["SkillDefinition"]] = relationship(back_populates="task_type")


class SkillDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "skill_definitions"
    __table_args__ = (UniqueConstraint("store_id", "code", name="uq_skill_definitions_store_code"),)

    store_id: Mapped[UUID] = mapped_column(ForeignKey("stores.id", ondelete="RESTRICT"), index=True)
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    skill_category: Mapped[str] = mapped_column(String(50), nullable=False)
    position_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("positions.id", ondelete="SET NULL")
    )
    task_type_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("task_types.id", ondelete="SET NULL")
    )
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    store: Mapped[Store] = relationship(back_populates="skill_definitions")
    position: Mapped[Optional[Position]] = relationship(back_populates="skill_definitions")
    task_type: Mapped[Optional[TaskType]] = relationship(back_populates="skill_definitions")
    staff_skills: Mapped[list["StaffSkill"]] = relationship(back_populates="skill_definition")


class StaffSkill(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "staff_skills"
    __table_args__ = (
        UniqueConstraint(
            "staff_member_id",
            "skill_definition_id",
            name="uq_staff_skills_staff_skill",
        ),
        CheckConstraint("skill_level >= 1", name="positive_skill_level"),
    )

    staff_member_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff_members.id", ondelete="CASCADE")
    )
    skill_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("skill_definitions.id", ondelete="RESTRICT")
    )
    skill_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_preferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    certified_at: Mapped[Optional[date]] = mapped_column()
    expires_at: Mapped[Optional[date]] = mapped_column()

    staff_member: Mapped["StaffMember"] = relationship(back_populates="staff_skills")
    skill_definition: Mapped[SkillDefinition] = relationship(back_populates="staff_skills")
