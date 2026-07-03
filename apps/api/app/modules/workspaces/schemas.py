from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.shared.schemas import (
    PlanningPeriodRead,
    PositionRead,
    ScheduleVersionRead,
    ScheduleWarningRead,
    ShiftRequestRead,
    ShiftRequirementRead,
    ShiftSegmentRead,
    SkillDefinitionRead,
    StaffMemberRead,
    StoreRead,
    TaskTypeRead,
    WorkShiftRead,
)


class WorkspaceStaffSkillRead(BaseModel):
    staff_member_id: UUID
    skill_definition_id: UUID


class WorkspaceRead(BaseModel):
    planning_period: PlanningPeriodRead
    store: StoreRead
    current_schedule_version: Optional[ScheduleVersionRead]
    staff_members: list[StaffMemberRead]
    positions: list[PositionRead]
    task_types: list[TaskTypeRead]
    skill_definitions: list[SkillDefinitionRead]
    staff_skills: list[WorkspaceStaffSkillRead]
    shift_requests: list[ShiftRequestRead]
    shift_requirements: list[ShiftRequirementRead]
    work_shifts: list[WorkShiftRead]
    shift_segments: list[ShiftSegmentRead]
    warnings: list[ScheduleWarningRead] = []
    locks: list[dict] = []
