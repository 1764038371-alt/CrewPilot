from datetime import date, time
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.shared.schemas import (
    PlanningPeriodRead,
    PositionRead,
    ShiftRequestRead,
    SkillDefinitionRead,
    StaffMemberRead,
    StoreRead,
    TaskTypeRead,
)


class StaffSkillRead(BaseModel):
    staff_member_id: UUID
    skill_definition_id: UUID


class SetupRead(BaseModel):
    store: StoreRead
    planning_period: PlanningPeriodRead
    staff_members: list[StaffMemberRead]
    positions: list[PositionRead]
    task_types: list[TaskTypeRead]
    skill_definitions: list[SkillDefinitionRead]
    staff_skills: list[StaffSkillRead]


class StoreSetupWrite(BaseModel):
    name: str
    opening_time: time
    closing_time: time
    business_hours: dict
    operational_settings: dict


class StaffSetupWrite(BaseModel):
    id: Optional[UUID] = None
    employee_number: str = Field(min_length=1)
    display_name: str
    employment_type: str
    hourly_wage_yen: Optional[int] = None
    position_ids: list[UUID] = []
    skill_definition_ids: list[UUID] = []
    can_open: bool = False
    can_close: bool = False
    can_deposit: bool = False
    is_active: bool = True


class SetupWrite(BaseModel):
    store: StoreSetupWrite
    staff_members: list[StaffSetupWrite]


class DailyShiftRequestWrite(BaseModel):
    staff_member_id: UUID
    request_type: str
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    note: Optional[str] = None


class DailyDraftRead(BaseModel):
    planning_period: PlanningPeriodRead
    store: StoreRead
    staff_members: list[StaffMemberRead]
    shift_requests: list[ShiftRequestRead]


class DailyDraftWrite(BaseModel):
    target_date: date
    requests: list[DailyShiftRequestWrite]
    required_staff_templates: list[dict] = []
