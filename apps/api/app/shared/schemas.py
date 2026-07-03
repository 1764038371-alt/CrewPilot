from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class StoreRead(BaseModel):
    id: UUID
    name: str
    code: str
    timezone: str
    opening_time: time
    closing_time: time
    business_hours: Optional[dict] = None
    operational_settings: Optional[dict] = None
    time_slot_minutes: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class StaffMemberRead(BaseModel):
    id: UUID
    store_id: UUID
    employee_number: Optional[str] = None
    display_name: str
    employment_type: str
    hourly_wage_yen: Optional[int] = None
    max_weekly_minutes: Optional[int]
    min_shift_minutes: Optional[int]
    max_shift_minutes: Optional[int]
    priority: int
    is_active: bool
    joined_on: Optional[date]
    left_on: Optional[date]

    model_config = ConfigDict(from_attributes=True)


class PositionRead(BaseModel):
    id: UUID
    store_id: UUID
    name: str
    code: str
    priority: int
    color: Optional[str]
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class TaskTypeRead(BaseModel):
    id: UUID
    store_id: UUID
    code: str
    name: str
    description: Optional[str]
    default_duration_minutes: Optional[int]
    requires_offsite: bool
    priority: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class SkillDefinitionRead(BaseModel):
    id: UUID
    store_id: UUID
    code: str
    name: str
    skill_category: str
    position_id: Optional[UUID]
    task_type_id: Optional[UUID]
    description: Optional[str]
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class PlanningPeriodRead(BaseModel):
    id: UUID
    store_id: UUID
    name: str
    start_date: date
    end_date: date
    status: str
    request_deadline: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ShiftRequestRead(BaseModel):
    id: UUID
    planning_period_id: UUID
    staff_member_id: UUID
    request_date: date
    start_time: Optional[time]
    end_time: Optional[time]
    request_type: str
    priority: int
    note: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class ShiftRequirementRead(BaseModel):
    id: UUID
    planning_period_id: UUID
    store_id: UUID
    requirement_date: date
    start_time: time
    end_time: time
    requirement_type: str
    position_id: Optional[UUID]
    task_type_id: Optional[UUID]
    min_staff_count: int
    target_staff_count: int
    max_staff_count: Optional[int]
    priority: int

    model_config = ConfigDict(from_attributes=True)


class ScheduleVersionRead(BaseModel):
    id: UUID
    planning_period_id: UUID
    store_id: UUID
    parent_schedule_version_id: Optional[UUID]
    published_by_user_id: Optional[UUID] = None
    version_number: int
    revision: int
    name: str
    status: str
    is_locked: bool
    published_at: Optional[datetime]
    published_by: Optional[str] = None
    change_summary: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class WorkShiftRead(BaseModel):
    id: UUID
    schedule_version_id: UUID
    staff_member_id: UUID
    store_id: UUID
    work_date: date
    start_time: time
    end_time: time
    total_work_minutes: int
    total_break_minutes: int
    assignment_source: str
    is_locked: bool
    locked_by_user_id: Optional[UUID] = None
    lock_scope: Optional[str]
    locked_at: Optional[datetime]
    lock_reason: Optional[str]
    note: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class ShiftSegmentRead(BaseModel):
    id: UUID
    work_shift_id: UUID
    schedule_version_id: UUID
    store_id: UUID
    segment_date: date
    start_time: time
    end_time: time
    segment_type: str
    position_id: Optional[UUID]
    task_type_id: Optional[UUID]
    label: Optional[str]
    assignment_source: str
    is_locked: bool
    locked_by_user_id: Optional[UUID] = None
    lock_scope: Optional[str]
    locked_at: Optional[datetime]
    lock_reason: Optional[str]
    confidence_score: Optional[Decimal]
    note: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class ScheduleWarningRead(BaseModel):
    id: UUID
    schedule_version_id: UUID
    work_shift_id: Optional[UUID]
    shift_segment_id: Optional[UUID]
    warning_type: str
    severity: str
    message: str
    details: Optional[dict]

    model_config = ConfigDict(from_attributes=True)


class ScheduleChangeLogRead(BaseModel):
    id: UUID
    schedule_version_id: UUID
    work_shift_id: Optional[UUID]
    shift_segment_id: Optional[UUID]
    command_type: str
    command_payload: Optional[dict]
    inverse_payload: Optional[dict]
    executed_by_user_id: Optional[UUID] = None
    before_value: Optional[Any]
    after_value: Optional[Any]
    reason: Optional[str]
    executed_by: str
    source_type: Optional[str] = None
    source_id: Optional[UUID] = None
    batch_id: Optional[UUID] = None
    batch_label: Optional[str] = None
    explanation: Optional[dict] = None
    is_undone: bool
    undone_at: Optional[datetime]
    parent_change_log_id: Optional[UUID]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OptimizationRunRead(BaseModel):
    id: UUID
    schedule_version_id: UUID
    solver_name: str
    status: str
    scope: dict
    solve_time_ms: int
    objective_value: Optional[int]
    warning_before: dict
    warning_after: dict
    changed_segments: int
    changed_work_shifts: int
    fairness_score: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
