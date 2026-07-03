from datetime import date, time
from enum import Enum
from typing import Annotated, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class OptimizationScopeType(str, Enum):
    FULL = "full"
    DATE = "date"
    TIME_RANGE = "time_range"
    STAFF = "staff"
    WARNING = "warning"


class FullScope(BaseModel):
    type: Literal[OptimizationScopeType.FULL] = OptimizationScopeType.FULL


class DateScope(BaseModel):
    type: Literal[OptimizationScopeType.DATE]
    date: date


class TimeRangeScope(BaseModel):
    type: Literal[OptimizationScopeType.TIME_RANGE]
    date: date
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def validate_time_range(self) -> "TimeRangeScope":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time")
        return self


class StaffScope(BaseModel):
    type: Literal[OptimizationScopeType.STAFF]
    staff_member_id: UUID
    date: Optional[date] = None


class WarningScope(BaseModel):
    type: Literal[OptimizationScopeType.WARNING]
    warning_id: UUID


OptimizationScopePayload = Annotated[
    Union[FullScope, DateScope, TimeRangeScope, StaffScope, WarningScope],
    Field(discriminator="type"),
]


class OptimizationRequest(BaseModel):
    scope: OptimizationScopePayload = Field(default_factory=FullScope)
    time_limit_seconds: float = Field(default=5.0, gt=0, le=60)
