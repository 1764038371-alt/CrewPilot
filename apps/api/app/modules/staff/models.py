from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.modules.stores.models import StaffSkill


class StaffMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "staff_members"

    store_id: Mapped[UUID] = mapped_column(ForeignKey("stores.id", ondelete="RESTRICT"), index=True)
    employee_number: Mapped[Optional[str]] = mapped_column(String(64))
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    employment_type: Mapped[str] = mapped_column(String(50), nullable=False, default="part_time")
    hourly_wage_yen: Mapped[Optional[int]] = mapped_column(Integer)
    max_weekly_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    min_shift_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    max_shift_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    joined_on: Mapped[Optional[date]] = mapped_column()
    left_on: Mapped[Optional[date]] = mapped_column()

    staff_skills: Mapped[list["StaffSkill"]] = relationship(back_populates="staff_member")
