from __future__ import annotations

from datetime import date, time
from enum import Enum
from typing import Annotated, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ScheduleCommandType(str, Enum):
    CREATE_WORK_SHIFT = "CreateWorkShift"
    RESTORE_WORK_SHIFT = "RestoreWorkShift"
    UPDATE_WORK_SHIFT = "UpdateWorkShift"
    DELETE_WORK_SHIFT = "DeleteWorkShift"
    RESTORE_SHIFT_SEGMENT = "RestoreShiftSegment"
    DELETE_SHIFT_SEGMENT = "DeleteShiftSegment"
    ASSIGN_STAFF = "AssignStaff"
    SWAP_STAFF = "SwapStaff"
    CREATE_BREAK = "CreateBreak"
    MOVE_BREAK = "MoveBreak"
    RESIZE_BREAK = "ResizeBreak"
    CREATE_WORK_SEGMENT = "CreateWorkSegment"
    CREATE_TASK_SEGMENT = "CreateTaskSegment"
    MOVE_TASK_SEGMENT = "MoveTaskSegment"
    SPLIT_SEGMENT = "SplitSegment"
    MERGE_SEGMENT = "MergeSegment"
    RESIZE_SEGMENT = "ResizeSegment"
    RESIZE_WORK_SHIFT = "ResizeWorkShift"
    UPDATE_SEGMENT_POSITION = "UpdateSegmentPosition"
    UPDATE_SEGMENT_TASK = "UpdateSegmentTask"
    UPDATE_SEGMENT_BREAK = "UpdateSegmentBreak"
    INSERT_BREAK = "InsertBreak"
    LOCK_SEGMENT = "LockSegment"
    UNLOCK_SEGMENT = "UnlockSegment"


class SplitSegmentPayload(BaseModel):
    segment_id: UUID
    split_time: time


class CreateWorkShiftSegmentPayload(BaseModel):
    start_time: time
    end_time: time
    segment_type: Literal["WORK", "BREAK", "TASK"] = "WORK"
    position_id: Optional[UUID] = None
    task_type_id: Optional[UUID] = None
    label: Optional[str] = None

    @model_validator(mode="after")
    def validate_segment(self) -> "CreateWorkShiftSegmentPayload":
        if self.start_time >= self.end_time:
            raise ValueError("segment start_time must be earlier than end_time")
        if self.segment_type == "WORK" and self.position_id is None:
            raise ValueError("WORK segment requires position_id")
        if self.segment_type == "TASK" and self.task_type_id is None:
            raise ValueError("TASK segment requires task_type_id")
        if self.segment_type == "BREAK" and (
            self.position_id is not None or self.task_type_id is not None
        ):
            raise ValueError("BREAK segment cannot have position_id or task_type_id")
        return self


class CreateWorkShiftPayload(BaseModel):
    staff_member_id: UUID
    work_date: date
    start_time: time
    end_time: time
    position_id: Optional[UUID] = None
    task_type_id: Optional[UUID] = None
    segments: list[CreateWorkShiftSegmentPayload] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_time_range(self) -> "CreateWorkShiftPayload":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time")
        if not self.segments and (self.position_id is None) == (self.task_type_id is None):
            raise ValueError("Specify exactly one of position_id or task_type_id")
        for segment in self.segments:
            if not (self.start_time <= segment.start_time < segment.end_time <= self.end_time):
                raise ValueError("segments must be inside work shift")
        return self


class UpdateWorkShiftPayload(BaseModel):
    work_shift_id: UUID
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    staff_member_id: Optional[UUID] = None

    @model_validator(mode="after")
    def validate_time_range(self) -> "UpdateWorkShiftPayload":
        if self.start_time is not None and self.end_time is not None:
            if self.start_time >= self.end_time:
                raise ValueError("start_time must be earlier than end_time")
        return self


class DeleteWorkShiftPayload(BaseModel):
    work_shift_id: UUID


class RestoreWorkShiftPayload(BaseModel):
    snapshot: dict


class DeleteShiftSegmentPayload(BaseModel):
    segment_id: UUID


class RestoreShiftSegmentPayload(BaseModel):
    snapshot: dict


class AssignStaffPayload(BaseModel):
    work_shift_id: UUID
    staff_member_id: UUID


class SwapStaffPayload(BaseModel):
    first_work_shift_id: UUID
    second_work_shift_id: UUID


class CreateBreakPayload(BaseModel):
    work_shift_id: UUID
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def validate_time_range(self) -> "CreateBreakPayload":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time")
        return self


class MoveBreakPayload(BaseModel):
    segment_id: UUID
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def validate_time_range(self) -> "MoveBreakPayload":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time")
        return self


class ResizeBreakPayload(MoveBreakPayload):
    pass


class CreateWorkSegmentPayload(BaseModel):
    work_shift_id: UUID
    start_time: time
    end_time: time
    position_id: UUID

    @model_validator(mode="after")
    def validate_time_range(self) -> "CreateWorkSegmentPayload":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time")
        return self


class CreateTaskSegmentPayload(BaseModel):
    work_shift_id: UUID
    start_time: time
    end_time: time
    task_type_id: UUID

    @model_validator(mode="after")
    def validate_time_range(self) -> "CreateTaskSegmentPayload":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time")
        return self


class MoveTaskSegmentPayload(BaseModel):
    segment_id: UUID
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def validate_time_range(self) -> "MoveTaskSegmentPayload":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time")
        return self


class MergeSegmentPayload(BaseModel):
    first_segment_id: UUID
    second_segment_id: UUID


class ResizeWorkShiftPayload(BaseModel):
    work_shift_id: UUID
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def validate_time_range(self) -> "ResizeWorkShiftPayload":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time")
        return self


class ResizeSegmentPayload(BaseModel):
    segment_id: UUID
    start_time: Optional[time] = None
    end_time: Optional[time] = None

    @model_validator(mode="after")
    def validate_time_range(self) -> "ResizeSegmentPayload":
        if self.start_time is None and self.end_time is None:
            raise ValueError("Specify start_time or end_time")
        if self.start_time is not None and self.end_time is not None:
            if self.start_time >= self.end_time:
                raise ValueError("start_time must be earlier than end_time")
        return self


class UpdateSegmentPositionPayload(BaseModel):
    segment_id: UUID
    position_id: UUID


class UpdateSegmentTaskPayload(BaseModel):
    segment_id: UUID
    task_type_id: UUID


class UpdateSegmentBreakPayload(BaseModel):
    segment_id: UUID


class InsertBreakPayload(BaseModel):
    work_shift_id: UUID
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def validate_time_range(self) -> "InsertBreakPayload":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time")
        return self


class LockSegmentPayload(BaseModel):
    segment_id: UUID
    lock_scope: str = "full"
    lock_reason: Optional[str] = None


class UnlockSegmentPayload(BaseModel):
    segment_id: UUID


class SplitSegmentCommand(BaseModel):
    type: Literal[ScheduleCommandType.SPLIT_SEGMENT]
    payload: SplitSegmentPayload


class CreateWorkShiftCommand(BaseModel):
    type: Literal[ScheduleCommandType.CREATE_WORK_SHIFT]
    payload: CreateWorkShiftPayload


class UpdateWorkShiftCommand(BaseModel):
    type: Literal[ScheduleCommandType.UPDATE_WORK_SHIFT]
    payload: UpdateWorkShiftPayload


class DeleteWorkShiftCommand(BaseModel):
    type: Literal[ScheduleCommandType.DELETE_WORK_SHIFT]
    payload: DeleteWorkShiftPayload


class RestoreWorkShiftCommand(BaseModel):
    type: Literal[ScheduleCommandType.RESTORE_WORK_SHIFT]
    payload: RestoreWorkShiftPayload


class DeleteShiftSegmentCommand(BaseModel):
    type: Literal[ScheduleCommandType.DELETE_SHIFT_SEGMENT]
    payload: DeleteShiftSegmentPayload


class RestoreShiftSegmentCommand(BaseModel):
    type: Literal[ScheduleCommandType.RESTORE_SHIFT_SEGMENT]
    payload: RestoreShiftSegmentPayload


class AssignStaffCommand(BaseModel):
    type: Literal[ScheduleCommandType.ASSIGN_STAFF]
    payload: AssignStaffPayload


class SwapStaffCommand(BaseModel):
    type: Literal[ScheduleCommandType.SWAP_STAFF]
    payload: SwapStaffPayload


class CreateBreakCommand(BaseModel):
    type: Literal[ScheduleCommandType.CREATE_BREAK]
    payload: CreateBreakPayload


class MoveBreakCommand(BaseModel):
    type: Literal[ScheduleCommandType.MOVE_BREAK]
    payload: MoveBreakPayload


class ResizeBreakCommand(BaseModel):
    type: Literal[ScheduleCommandType.RESIZE_BREAK]
    payload: ResizeBreakPayload


class CreateWorkSegmentCommand(BaseModel):
    type: Literal[ScheduleCommandType.CREATE_WORK_SEGMENT]
    payload: CreateWorkSegmentPayload


class CreateTaskSegmentCommand(BaseModel):
    type: Literal[ScheduleCommandType.CREATE_TASK_SEGMENT]
    payload: CreateTaskSegmentPayload


class MoveTaskSegmentCommand(BaseModel):
    type: Literal[ScheduleCommandType.MOVE_TASK_SEGMENT]
    payload: MoveTaskSegmentPayload


class MergeSegmentCommand(BaseModel):
    type: Literal[ScheduleCommandType.MERGE_SEGMENT]
    payload: MergeSegmentPayload


class ResizeWorkShiftCommand(BaseModel):
    type: Literal[ScheduleCommandType.RESIZE_WORK_SHIFT]
    payload: ResizeWorkShiftPayload


class ResizeSegmentCommand(BaseModel):
    type: Literal[ScheduleCommandType.RESIZE_SEGMENT]
    payload: ResizeSegmentPayload


class UpdateSegmentPositionCommand(BaseModel):
    type: Literal[ScheduleCommandType.UPDATE_SEGMENT_POSITION]
    payload: UpdateSegmentPositionPayload


class UpdateSegmentTaskCommand(BaseModel):
    type: Literal[ScheduleCommandType.UPDATE_SEGMENT_TASK]
    payload: UpdateSegmentTaskPayload


class UpdateSegmentBreakCommand(BaseModel):
    type: Literal[ScheduleCommandType.UPDATE_SEGMENT_BREAK]
    payload: UpdateSegmentBreakPayload


class InsertBreakCommand(BaseModel):
    type: Literal[ScheduleCommandType.INSERT_BREAK]
    payload: InsertBreakPayload


class LockSegmentCommand(BaseModel):
    type: Literal[ScheduleCommandType.LOCK_SEGMENT]
    payload: LockSegmentPayload


class UnlockSegmentCommand(BaseModel):
    type: Literal[ScheduleCommandType.UNLOCK_SEGMENT]
    payload: UnlockSegmentPayload


ScheduleCommand = Annotated[
    Union[
        CreateWorkShiftCommand,
        RestoreWorkShiftCommand,
        UpdateWorkShiftCommand,
        DeleteWorkShiftCommand,
        RestoreShiftSegmentCommand,
        DeleteShiftSegmentCommand,
        AssignStaffCommand,
        SwapStaffCommand,
        CreateBreakCommand,
        MoveBreakCommand,
        ResizeBreakCommand,
        CreateWorkSegmentCommand,
        CreateTaskSegmentCommand,
        MoveTaskSegmentCommand,
        SplitSegmentCommand,
        MergeSegmentCommand,
        ResizeSegmentCommand,
        ResizeWorkShiftCommand,
        UpdateSegmentPositionCommand,
        UpdateSegmentTaskCommand,
        UpdateSegmentBreakCommand,
        InsertBreakCommand,
        LockSegmentCommand,
        UnlockSegmentCommand,
    ],
    Field(discriminator="type"),
]


class ScheduleCommandResult(BaseModel):
    schedule_version_id: UUID
    revision: int
    command_type: ScheduleCommandType
    warnings_count: int
