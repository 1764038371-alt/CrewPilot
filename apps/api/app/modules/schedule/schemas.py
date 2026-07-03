from datetime import time
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, model_validator

from app.shared.schemas import ScheduleVersionRead


class PublishValidationIssue(BaseModel):
    code: str
    message: str
    severity: str = "error"


class PublishValidationResult(BaseModel):
    schedule_version_id: UUID
    can_publish: bool
    issues: list[PublishValidationIssue]


class ScheduleVersionActionResult(BaseModel):
    schedule_version: ScheduleVersionRead
    validation: Optional[PublishValidationResult] = None


class PublishRequest(BaseModel):
    expected_revision: Optional[int] = None


class WorkShiftUpdate(BaseModel):
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    is_locked: Optional[bool] = None
    lock_scope: Optional[str] = None
    lock_reason: Optional[str] = None
    note: Optional[str] = None

    @model_validator(mode="after")
    def validate_time_range(self) -> "WorkShiftUpdate":
        if self.start_time is not None and self.end_time is not None:
            if self.start_time >= self.end_time:
                raise ValueError("start_time must be earlier than end_time")
        return self


class ShiftSegmentUpdate(BaseModel):
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    segment_type: Optional[str] = None
    position_id: Optional[UUID] = None
    task_type_id: Optional[UUID] = None
    label: Optional[str] = None
    is_locked: Optional[bool] = None
    lock_scope: Optional[str] = None
    lock_reason: Optional[str] = None
    note: Optional[str] = None

    @model_validator(mode="after")
    def validate_time_range(self) -> "ShiftSegmentUpdate":
        if self.start_time is not None and self.end_time is not None:
            if self.start_time >= self.end_time:
                raise ValueError("start_time must be earlier than end_time")
        return self
