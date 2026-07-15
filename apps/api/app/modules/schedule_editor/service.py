from __future__ import annotations

from datetime import date, datetime, time
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.schedule.models import (
    ScheduleChangeLog,
    ScheduleVersion,
    ShiftSegment,
    WorkShift,
)
from app.modules.schedule_editor.commands import (
    AssignStaffCommand,
    CreateBreakCommand,
    CreateTaskSegmentCommand,
    CreateWorkSegmentCommand,
    CreateWorkShiftCommand,
    DeleteShiftSegmentCommand,
    DeleteWorkShiftCommand,
    InsertBreakCommand,
    LockSegmentCommand,
    MergeSegmentCommand,
    MoveBreakCommand,
    MoveTaskSegmentCommand,
    ResizeBreakCommand,
    ResizeSegmentCommand,
    ResizeWorkShiftCommand,
    RestoreShiftSegmentCommand,
    RestoreWorkShiftCommand,
    ScheduleCommand,
    ScheduleCommandResult,
    SplitSegmentCommand,
    SwapStaffCommand,
    UnlockSegmentCommand,
    UpdateSegmentBreakCommand,
    UpdateSegmentPositionCommand,
    UpdateSegmentTaskCommand,
    UpdateWorkShiftCommand,
)
from app.modules.schedule_editor.warnings import WarningService
from app.modules.staff.models import StaffMember
from app.modules.stores.models import Position, Store, TaskType

BREAK_SHIFT_EDGE_BUFFER_MINUTES = 120


class ScheduleCommandService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(
        self,
        schedule_version_id: UUID,
        command: ScheduleCommand,
        *,
        actor: User | None = None,
        parent_change_log_id: UUID | None = None,
        source_type: str | None = None,
        source_id: UUID | None = None,
        batch_id: UUID | None = None,
        batch_label: str | None = None,
        explanation: dict | None = None,
    ) -> ScheduleCommandResult:
        schedule_version = await self._get_schedule_version(schedule_version_id)
        if schedule_version.status in {"published", "archived"} or schedule_version.is_locked:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Published or archived schedule versions cannot be edited",
            )
        before = None
        after = None
        work_shift_id = None
        segment_id = None

        if isinstance(command, CreateWorkShiftCommand):
            await self._validate_staff(schedule_version.store_id, command.payload.staff_member_id)
            if command.payload.position_id is not None:
                await self._validate_position(
                    schedule_version.store_id,
                    command.payload.position_id,
                )
            if command.payload.task_type_id is not None:
                await self._validate_task_type(
                    schedule_version.store_id,
                    command.payload.task_type_id,
                )
            work_shift = await self._create_work_shift(schedule_version, command)
            work_shift_id = work_shift.id
            after = self._work_shift_snapshot(work_shift)
        elif isinstance(command, RestoreWorkShiftCommand):
            work_shift = await self._restore_work_shift(schedule_version, command)
            work_shift_id = work_shift.id
            after = self._work_shift_with_segments_snapshot(work_shift)
        elif isinstance(command, UpdateWorkShiftCommand):
            work_shift = await self._get_work_shift(
                schedule_version_id, command.payload.work_shift_id
            )
            before = self._work_shift_snapshot(work_shift)
            if command.payload.staff_member_id is not None:
                await self._validate_staff(
                    schedule_version.store_id,
                    command.payload.staff_member_id,
                )
            work_shift = await self._update_work_shift(schedule_version_id, command)
            work_shift_id = work_shift.id
            after = self._work_shift_snapshot(work_shift)
        elif isinstance(command, DeleteWorkShiftCommand):
            work_shift = await self._get_work_shift(
                schedule_version_id, command.payload.work_shift_id
            )
            before = await self._work_shift_with_segments_snapshot(work_shift)
            work_shift_id = None
            segments = await self.session.scalars(
                select(ShiftSegment).where(ShiftSegment.work_shift_id == work_shift.id)
            )
            for segment in segments:
                await self.session.delete(segment)
            await self.session.flush()
            await self.session.delete(work_shift)
            await self.session.flush()
            after = None
        elif isinstance(command, RestoreShiftSegmentCommand):
            segment = await self._restore_shift_segment(schedule_version, command)
            segment_id = segment.id
            after = self._segment_snapshot(segment)
        elif isinstance(command, DeleteShiftSegmentCommand):
            segment = await self._get_segment(schedule_version_id, command.payload.segment_id)
            before = self._segment_snapshot(segment)
            segment_id = None
            await self.session.delete(segment)
            await self.session.flush()
            after = None
        elif isinstance(command, AssignStaffCommand):
            work_shift = await self._get_work_shift(
                schedule_version_id, command.payload.work_shift_id
            )
            await self._validate_staff(schedule_version.store_id, command.payload.staff_member_id)
            before = self._work_shift_snapshot(work_shift)
            work_shift.staff_member_id = command.payload.staff_member_id
            work_shift.assignment_source = "optimized"
            work_shift_id = work_shift.id
            after = self._work_shift_snapshot(work_shift)
        elif isinstance(command, SwapStaffCommand):
            first = await self._get_work_shift(
                schedule_version_id, command.payload.first_work_shift_id
            )
            second = await self._get_work_shift(
                schedule_version_id, command.payload.second_work_shift_id
            )
            before = [self._work_shift_snapshot(first), self._work_shift_snapshot(second)]
            first_staff_member_id = first.staff_member_id
            first.staff_member_id = second.staff_member_id
            second.staff_member_id = first_staff_member_id
            first.assignment_source = "optimized"
            second.assignment_source = "optimized"
            work_shift_id = first.id
            after = [self._work_shift_snapshot(first), self._work_shift_snapshot(second)]
        elif isinstance(command, CreateBreakCommand):
            target = await self._find_segment_covering_break(
                command.payload.work_shift_id,
                command.payload.start_time,
                command.payload.end_time,
            )
            before = self._segment_snapshot(target) if target is not None else None
            segment = await self._create_break(schedule_version_id, command)
            segment_id = segment.id
            after = self._segment_snapshot(segment)
        elif isinstance(command, MoveBreakCommand):
            segment = await self._get_segment(schedule_version_id, command.payload.segment_id)
            before = self._segment_snapshot(segment)
            segment = await self._move_break(schedule_version_id, command)
            segment_id = segment.id
            after = self._segment_snapshot(segment)
        elif isinstance(command, ResizeBreakCommand):
            segment = await self._get_segment(schedule_version_id, command.payload.segment_id)
            before = self._segment_snapshot(segment)
            segment = await self._resize_break(schedule_version_id, command)
            segment_id = segment.id
            after = self._segment_snapshot(segment)
        elif isinstance(command, CreateWorkSegmentCommand):
            await self._validate_position(schedule_version.store_id, command.payload.position_id)
            segment = await self._create_work_segment(schedule_version_id, command)
            segment_id = segment.id
            work_shift_id = segment.work_shift_id
            after = self._segment_snapshot(segment)
        elif isinstance(command, CreateTaskSegmentCommand):
            await self._validate_task_type(schedule_version.store_id, command.payload.task_type_id)
            segment = await self._create_task_segment(schedule_version_id, command)
            segment_id = segment.id
            after = self._segment_snapshot(segment)
        elif isinstance(command, MoveTaskSegmentCommand):
            segment = await self._get_segment(schedule_version_id, command.payload.segment_id)
            before = self._segment_snapshot(segment)
            segment = await self._move_task_segment(schedule_version_id, command)
            segment_id = segment.id
            after = self._segment_snapshot(segment)
        elif isinstance(command, SplitSegmentCommand):
            original = await self._get_segment(schedule_version_id, command.payload.segment_id)
            before = self._segment_snapshot(original)
            segment = await self._split_segment(schedule_version_id, command)
            segment_id = segment.id
            after = {
                "updated_segment": self._segment_snapshot(original),
                "created_segment": self._segment_snapshot(segment),
            }
        elif isinstance(command, MergeSegmentCommand):
            first = await self._get_segment(
                schedule_version_id, command.payload.first_segment_id
            )
            second = await self._get_segment(
                schedule_version_id, command.payload.second_segment_id
            )
            before = [self._segment_snapshot(first), self._segment_snapshot(second)]
            segment = await self._merge_segment(schedule_version_id, command)
            segment_id = segment.id
            after = self._segment_snapshot(segment)
        elif isinstance(command, ResizeWorkShiftCommand):
            work_shift = await self._get_work_shift(
                schedule_version_id, command.payload.work_shift_id
            )
            before = self._work_shift_snapshot(work_shift)
            work_shift = await self._resize_work_shift(schedule_version_id, command)
            work_shift_id = work_shift.id
            after = self._work_shift_snapshot(work_shift)
        elif isinstance(command, ResizeSegmentCommand):
            segment = await self._get_segment(schedule_version_id, command.payload.segment_id)
            before = self._segment_snapshot(segment)
            segment = await self._resize_segment(schedule_version_id, command)
            segment_id = segment.id
            work_shift_id = segment.work_shift_id
            after = self._segment_snapshot(segment)
        elif isinstance(command, UpdateSegmentPositionCommand):
            segment = await self._get_segment(schedule_version_id, command.payload.segment_id)
            position = await self._validate_position(
                schedule_version.store_id, command.payload.position_id
            )
            if command.payload.label in {"SH", "ST"} and position.code != "B":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="SH/ST labels can only be assigned to position B",
                )
            before = self._segment_snapshot(segment)
            segment.segment_type = "WORK"
            segment.position_id = command.payload.position_id
            segment.task_type_id = None
            segment.label = command.payload.label
            segment_id = segment.id
            after = self._segment_snapshot(segment)
        elif isinstance(command, UpdateSegmentTaskCommand):
            segment = await self._get_segment(schedule_version_id, command.payload.segment_id)
            await self._validate_task_type(schedule_version.store_id, command.payload.task_type_id)
            await self._validate_task_segment_window(
                schedule_version.store_id,
                command.payload.task_type_id,
                segment.segment_date,
                segment.start_time,
                segment.end_time,
            )
            before = self._segment_snapshot(segment)
            segment.segment_type = "TASK"
            segment.task_type_id = command.payload.task_type_id
            segment.position_id = None
            segment.label = None
            segment_id = segment.id
            after = self._segment_snapshot(segment)
        elif isinstance(command, UpdateSegmentBreakCommand):
            segment = await self._get_segment(schedule_version_id, command.payload.segment_id)
            before = self._segment_snapshot(segment)
            segment.segment_type = "BREAK"
            segment.position_id = None
            segment.task_type_id = None
            segment.label = None
            segment_id = segment.id
            after = self._segment_snapshot(segment)
        elif isinstance(command, InsertBreakCommand):
            target = await self._find_segment_covering_break(
                command.payload.work_shift_id,
                command.payload.start_time,
                command.payload.end_time,
            )
            before = self._segment_snapshot(target) if target is not None else None
            segment = await self._insert_break(schedule_version_id, command)
            segment_id = segment.id
            after = self._segment_snapshot(segment)
        elif isinstance(command, LockSegmentCommand):
            segment = await self._get_segment(
                schedule_version_id, command.payload.segment_id, allow_locked=True
            )
            before = self._segment_snapshot(segment)
            segment.is_locked = True
            segment.lock_scope = command.payload.lock_scope
            segment.lock_reason = command.payload.lock_reason
            segment.locked_at = datetime.utcnow()
            segment.locked_by_user_id = actor.id if actor else None
            segment_id = segment.id
            after = self._segment_snapshot(segment)
        elif isinstance(command, UnlockSegmentCommand):
            segment = await self._get_segment(
                schedule_version_id, command.payload.segment_id, allow_locked=True
            )
            before = self._segment_snapshot(segment)
            segment.is_locked = False
            segment.lock_scope = None
            segment.lock_reason = None
            segment.locked_at = None
            segment.locked_by_user_id = None
            segment_id = segment.id
            after = self._segment_snapshot(segment)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported command",
            )

        schedule_version.revision += 1
        command_payload = command.model_dump(mode="json")
        self.session.add(
            ScheduleChangeLog(
                schedule_version_id=schedule_version_id,
                work_shift_id=work_shift_id,
                shift_segment_id=segment_id,
                command_type=command.type.value,
                command_payload=command_payload,
                inverse_payload=self._inverse_command_payload(command, before, after),
                executed_by_user_id=actor.id if actor else None,
                before_value=before,
                after_value=after,
                reason=None,
                executed_by=actor.display_name if actor else "manager",
                source_type=source_type,
                source_id=source_id,
                batch_id=batch_id,
                batch_label=batch_label,
                explanation=explanation,
                parent_change_log_id=parent_change_log_id,
            )
        )
        warnings_count = await WarningService(self.session).recalculate(schedule_version_id)
        await self.session.commit()
        return ScheduleCommandResult(
            schedule_version_id=schedule_version_id,
            revision=schedule_version.revision,
            command_type=command.type,
            warnings_count=warnings_count,
        )

    async def undo_latest(
        self,
        schedule_version_id: UUID,
        *,
        actor: User | None = None,
    ) -> ScheduleCommandResult:
        change_log = await self._latest_undoable_change_log(schedule_version_id)
        if change_log.inverse_payload is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Selected command cannot be undone",
            )
        command = TypeAdapter(ScheduleCommand).validate_python(change_log.inverse_payload)
        result = await self.execute(
            schedule_version_id,
            command,
            actor=actor,
            parent_change_log_id=change_log.id,
            source_type="undo",
            source_id=change_log.id,
            batch_id=change_log.batch_id,
            batch_label=change_log.batch_label,
            explanation={"action": "undo", "original_change_log_id": str(change_log.id)},
        )
        change_log.is_undone = True
        change_log.undone_at = datetime.utcnow()
        await self.session.commit()
        return result

    async def redo_latest(
        self,
        schedule_version_id: UUID,
        *,
        actor: User | None = None,
    ) -> ScheduleCommandResult:
        change_log = await self._latest_redoable_change_log(schedule_version_id)
        if change_log.command_payload is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Selected command cannot be redone",
            )
        command = TypeAdapter(ScheduleCommand).validate_python(change_log.command_payload)
        result = await self.execute(
            schedule_version_id,
            command,
            actor=actor,
            parent_change_log_id=change_log.id,
            source_type="redo",
            source_id=change_log.id,
            batch_id=change_log.batch_id,
            batch_label=change_log.batch_label,
            explanation={"action": "redo", "original_change_log_id": str(change_log.id)},
        )
        change_log.is_undone = False
        change_log.undone_at = None
        await self.session.commit()
        return result

    async def _latest_undoable_change_log(self, schedule_version_id: UUID) -> ScheduleChangeLog:
        result = await self.session.scalars(
            select(ScheduleChangeLog)
            .where(ScheduleChangeLog.schedule_version_id == schedule_version_id)
            .where(ScheduleChangeLog.parent_change_log_id.is_(None))
            .where(ScheduleChangeLog.is_undone.is_(False))
            .order_by(ScheduleChangeLog.created_at.desc(), ScheduleChangeLog.id.desc())
            .limit(1)
        )
        change_log = result.first()
        if change_log is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No command to undo",
            )
        return change_log

    async def _latest_redoable_change_log(self, schedule_version_id: UUID) -> ScheduleChangeLog:
        result = await self.session.scalars(
            select(ScheduleChangeLog)
            .where(ScheduleChangeLog.schedule_version_id == schedule_version_id)
            .where(ScheduleChangeLog.parent_change_log_id.is_(None))
            .where(ScheduleChangeLog.is_undone.is_(True))
            .order_by(ScheduleChangeLog.undone_at.desc(), ScheduleChangeLog.id.desc())
            .limit(1)
        )
        change_log = result.first()
        if change_log is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No command to redo",
            )
        return change_log

    async def _create_work_shift(
        self,
        schedule_version: ScheduleVersion,
        command: CreateWorkShiftCommand,
    ) -> WorkShift:
        work_minutes = minutes_between(command.payload.start_time, command.payload.end_time)
        work_shift = WorkShift(
            schedule_version_id=schedule_version.id,
            staff_member_id=command.payload.staff_member_id,
            store_id=schedule_version.store_id,
            work_date=command.payload.work_date,
            start_time=command.payload.start_time,
            end_time=command.payload.end_time,
            total_work_minutes=(
                sum(
                    minutes_between(segment.start_time, segment.end_time)
                    for segment in command.payload.segments
                    if segment.segment_type in {"WORK", "TASK"}
                )
                if command.payload.segments
                else work_minutes
            ),
            total_break_minutes=sum(
                minutes_between(segment.start_time, segment.end_time)
                for segment in command.payload.segments
                if segment.segment_type == "BREAK"
            ),
            assignment_source="optimized",
            is_locked=False,
        )
        self.session.add(work_shift)
        await self.session.flush()
        if command.payload.segments:
            for payload_segment in command.payload.segments:
                self.session.add(
                    ShiftSegment(
                        work_shift_id=work_shift.id,
                        schedule_version_id=schedule_version.id,
                        store_id=schedule_version.store_id,
                        segment_date=command.payload.work_date,
                        start_time=payload_segment.start_time,
                        end_time=payload_segment.end_time,
                        segment_type=payload_segment.segment_type,
                        position_id=payload_segment.position_id,
                        task_type_id=payload_segment.task_type_id,
                        label=payload_segment.label,
                        assignment_source="optimized",
                        is_locked=False,
                    )
                )
        else:
            self.session.add(
                ShiftSegment(
                    work_shift_id=work_shift.id,
                    schedule_version_id=schedule_version.id,
                    store_id=schedule_version.store_id,
                    segment_date=command.payload.work_date,
                    start_time=command.payload.start_time,
                    end_time=command.payload.end_time,
                    segment_type="WORK" if command.payload.position_id is not None else "TASK",
                    position_id=command.payload.position_id,
                    task_type_id=command.payload.task_type_id,
                    label=None,
                    assignment_source="optimized",
                    is_locked=False,
                )
            )
        await self.session.flush()
        return work_shift

    async def _restore_work_shift(
        self,
        schedule_version: ScheduleVersion,
        command: RestoreWorkShiftCommand,
    ) -> WorkShift:
        snapshot = command.payload.snapshot
        work_shift = WorkShift(
            id=UUID(snapshot["id"]),
            schedule_version_id=schedule_version.id,
            staff_member_id=UUID(snapshot["staff_member_id"]),
            store_id=schedule_version.store_id,
            work_date=date.fromisoformat(snapshot["work_date"]),
            start_time=time.fromisoformat(snapshot["start_time"]),
            end_time=time.fromisoformat(snapshot["end_time"]),
            total_work_minutes=snapshot.get("total_work_minutes", 0),
            total_break_minutes=snapshot.get("total_break_minutes", 0),
            assignment_source=snapshot.get("assignment_source", "manual"),
            is_locked=snapshot.get("is_locked", False),
            lock_scope=snapshot.get("lock_scope"),
            lock_reason=snapshot.get("lock_reason"),
            note=snapshot.get("note"),
        )
        self.session.add(work_shift)
        await self.session.flush()
        for segment_snapshot in snapshot.get("segments", []):
            self.session.add(segment_from_snapshot(schedule_version, segment_snapshot))
        await self.session.flush()
        return work_shift

    async def _restore_shift_segment(
        self,
        schedule_version: ScheduleVersion,
        command: RestoreShiftSegmentCommand,
    ) -> ShiftSegment:
        segment = segment_from_snapshot(schedule_version, command.payload.snapshot)
        self.session.add(segment)
        await self.session.flush()
        return segment

    async def _create_task_segment(
        self,
        schedule_version_id: UUID,
        command: CreateTaskSegmentCommand,
    ) -> ShiftSegment:
        work_shift = await self._get_work_shift(schedule_version_id, command.payload.work_shift_id)
        if not (
            work_shift.start_time
            <= command.payload.start_time
            < command.payload.end_time
            <= work_shift.end_time
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Task segment is outside work shift",
            )
        await self._validate_task_segment_window(
            work_shift.store_id,
            command.payload.task_type_id,
            work_shift.work_date,
            command.payload.start_time,
            command.payload.end_time,
        )
        locked_overlap = await self.session.scalar(
            select(ShiftSegment)
            .where(ShiftSegment.work_shift_id == work_shift.id)
            .where(ShiftSegment.is_locked.is_(True))
            .where(ShiftSegment.start_time < command.payload.end_time)
            .where(ShiftSegment.end_time > command.payload.start_time)
            .limit(1)
        )
        if locked_overlap is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Task segment overlaps locked segment",
            )
        segment = ShiftSegment(
            work_shift_id=work_shift.id,
            schedule_version_id=schedule_version_id,
            store_id=work_shift.store_id,
            segment_date=work_shift.work_date,
            start_time=command.payload.start_time,
            end_time=command.payload.end_time,
            segment_type="TASK",
            position_id=None,
            task_type_id=command.payload.task_type_id,
            label=None,
            assignment_source="optimized",
            is_locked=False,
        )
        self.session.add(segment)
        await self.session.flush()
        return segment

    async def _move_task_segment(
        self,
        schedule_version_id: UUID,
        command: MoveTaskSegmentCommand,
    ) -> ShiftSegment:
        segment = await self._get_segment(schedule_version_id, command.payload.segment_id)
        if segment.segment_type != "TASK":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Segment is not TASK",
            )
        work_shift = await self._get_work_shift(schedule_version_id, segment.work_shift_id)
        if not (
            work_shift.start_time
            <= command.payload.start_time
            < command.payload.end_time
            <= work_shift.end_time
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Task segment is outside work shift",
            )
        await self._validate_task_segment_window(
            work_shift.store_id,
            segment.task_type_id,
            work_shift.work_date,
            command.payload.start_time,
            command.payload.end_time,
        )
        segment.start_time = command.payload.start_time
        segment.end_time = command.payload.end_time
        segment.assignment_source = "optimized"
        return segment

    async def _update_work_shift(
        self,
        schedule_version_id: UUID,
        command: UpdateWorkShiftCommand,
    ) -> WorkShift:
        work_shift = await self._get_work_shift(schedule_version_id, command.payload.work_shift_id)
        if command.payload.start_time is not None:
            work_shift.start_time = command.payload.start_time
        if command.payload.end_time is not None:
            work_shift.end_time = command.payload.end_time
        if command.payload.staff_member_id is not None:
            work_shift.staff_member_id = command.payload.staff_member_id
        work_shift.total_work_minutes = minutes_between(work_shift.start_time, work_shift.end_time)
        work_shift.assignment_source = "optimized"
        return work_shift

    async def _get_schedule_version(self, schedule_version_id: UUID) -> ScheduleVersion:
        schedule_version = await self.session.get(ScheduleVersion, schedule_version_id)
        if schedule_version is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Schedule version not found",
            )
        return schedule_version

    async def _get_segment(
        self,
        schedule_version_id: UUID,
        segment_id: UUID,
        *,
        allow_locked: bool = False,
    ) -> ShiftSegment:
        segment = await self.session.get(ShiftSegment, segment_id)
        if segment is None or segment.schedule_version_id != schedule_version_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shift segment not found",
            )
        if segment.is_locked and not allow_locked:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Shift segment is locked",
            )
        return segment

    async def _get_work_shift(self, schedule_version_id: UUID, work_shift_id: UUID) -> WorkShift:
        work_shift = await self.session.get(WorkShift, work_shift_id)
        if work_shift is None or work_shift.schedule_version_id != schedule_version_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work shift not found",
            )
        if work_shift.is_locked:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Work shift is locked")
        return work_shift

    async def _split_segment(
        self,
        schedule_version_id: UUID,
        command: SplitSegmentCommand,
    ) -> ShiftSegment:
        segment = await self._get_segment(schedule_version_id, command.payload.segment_id)
        split_time = command.payload.split_time
        if not segment.start_time < split_time < segment.end_time:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="split_time is outside segment",
            )

        new_segment = ShiftSegment(
            work_shift_id=segment.work_shift_id,
            schedule_version_id=segment.schedule_version_id,
            store_id=segment.store_id,
            segment_date=segment.segment_date,
            start_time=split_time,
            end_time=segment.end_time,
            segment_type=segment.segment_type,
            position_id=segment.position_id,
            task_type_id=segment.task_type_id,
            label=segment.label,
            assignment_source="manual",
            is_locked=False,
        )
        segment.end_time = split_time
        self.session.add(new_segment)
        await self.session.flush()
        return new_segment

    async def _merge_segment(
        self,
        schedule_version_id: UUID,
        command: MergeSegmentCommand,
    ) -> ShiftSegment:
        first = await self._get_segment(schedule_version_id, command.payload.first_segment_id)
        second = await self._get_segment(schedule_version_id, command.payload.second_segment_id)
        if first.work_shift_id != second.work_shift_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Segments must belong to same work shift",
            )
        ordered = sorted([first, second], key=lambda item: item.start_time)
        first, second = ordered[0], ordered[1]
        if first.end_time != second.start_time:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Segments must be adjacent",
            )
        if (
            first.segment_type != second.segment_type
            or first.position_id != second.position_id
            or first.task_type_id != second.task_type_id
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Segments are not compatible",
            )
        first.end_time = second.end_time
        await self.session.delete(second)
        await self.session.flush()
        return first

    async def _resize_work_shift(
        self,
        schedule_version_id: UUID,
        command: ResizeWorkShiftCommand,
    ) -> WorkShift:
        work_shift = await self._get_work_shift(schedule_version_id, command.payload.work_shift_id)
        work_shift.start_time = command.payload.start_time
        work_shift.end_time = command.payload.end_time
        return work_shift

    async def _resize_segment(
        self,
        schedule_version_id: UUID,
        command: ResizeSegmentCommand,
    ) -> ShiftSegment:
        segment = await self._get_segment(schedule_version_id, command.payload.segment_id)
        work_shift = await self._get_work_shift(schedule_version_id, segment.work_shift_id)
        next_start = command.payload.start_time or segment.start_time
        next_end = command.payload.end_time or segment.end_time
        if not (work_shift.start_time <= next_start < next_end <= work_shift.end_time):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Segment is outside work shift",
            )
        if segment.segment_type == "TASK":
            await self._validate_task_segment_window(
                work_shift.store_id,
                segment.task_type_id,
                segment.segment_date,
                next_start,
                next_end,
            )
        segment.start_time = next_start
        segment.end_time = next_end
        segment.assignment_source = "manual"
        return segment

    async def _insert_break(
        self,
        schedule_version_id: UUID,
        command: InsertBreakCommand,
    ) -> ShiftSegment:
        work_shift = await self._get_work_shift(schedule_version_id, command.payload.work_shift_id)
        start_time = command.payload.start_time
        end_time = command.payload.end_time
        if not work_shift.start_time <= start_time < end_time <= work_shift.end_time:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Break is outside work shift",
            )
        self._validate_break_shift_edge_buffer(work_shift, start_time, end_time)

        target = await self._find_segment_covering_break(work_shift.id, start_time, end_time)
        if target is None or target.segment_type != "WORK" or target.is_locked:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Break must be inside an unlocked WORK segment",
            )

        if end_time < target.end_time:
            self.session.add(
                ShiftSegment(
                    work_shift_id=target.work_shift_id,
                    schedule_version_id=target.schedule_version_id,
                    store_id=target.store_id,
                    segment_date=target.segment_date,
                    start_time=end_time,
                    end_time=target.end_time,
                    segment_type=target.segment_type,
                    position_id=target.position_id,
                    task_type_id=target.task_type_id,
                    label=target.label,
                    assignment_source="manual",
                    is_locked=False,
                )
            )

        if target.start_time < start_time:
            target.end_time = start_time
        else:
            await self.session.delete(target)

        break_segment = ShiftSegment(
            work_shift_id=work_shift.id,
            schedule_version_id=schedule_version_id,
            store_id=work_shift.store_id,
            segment_date=work_shift.work_date,
            start_time=start_time,
            end_time=end_time,
            segment_type="BREAK",
            position_id=None,
            task_type_id=None,
            label=None,
            assignment_source="manual",
            is_locked=False,
        )
        self.session.add(break_segment)
        await self.session.flush()
        return break_segment

    async def _create_break(
        self,
        schedule_version_id: UUID,
        command: CreateBreakCommand,
    ) -> ShiftSegment:
        insert_command = InsertBreakCommand(
            type="InsertBreak",
            payload={
                "work_shift_id": command.payload.work_shift_id,
                "start_time": command.payload.start_time,
                "end_time": command.payload.end_time,
            },
        )
        return await self._insert_break(schedule_version_id, insert_command)

    async def _move_break(
        self,
        schedule_version_id: UUID,
        command: MoveBreakCommand,
    ) -> ShiftSegment:
        segment = await self._get_segment(schedule_version_id, command.payload.segment_id)
        if segment.segment_type != "BREAK":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Segment is not BREAK",
            )
        work_shift = await self._get_work_shift(schedule_version_id, segment.work_shift_id)
        if not (
            work_shift.start_time
            <= command.payload.start_time
            < command.payload.end_time
            <= work_shift.end_time
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Break is outside work shift",
            )
        self._validate_break_shift_edge_buffer(
            work_shift,
            command.payload.start_time,
            command.payload.end_time,
        )
        segment.start_time = command.payload.start_time
        segment.end_time = command.payload.end_time
        segment.assignment_source = "optimized"
        return segment

    def _validate_break_shift_edge_buffer(
        self,
        work_shift: WorkShift,
        start_time: time,
        end_time: time,
    ) -> None:
        allowed_start = (
            minutes_since_midnight(work_shift.start_time)
            + BREAK_SHIFT_EDGE_BUFFER_MINUTES
        )
        allowed_end = minutes_since_midnight(work_shift.end_time) - BREAK_SHIFT_EDGE_BUFFER_MINUTES
        start_minute = minutes_since_midnight(start_time)
        end_minute = minutes_since_midnight(end_time)
        if start_minute < allowed_start or end_minute > allowed_end:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Break must be at least 2 hours after shift start "
                    "and 2 hours before shift end"
                ),
            )

    async def _resize_break(
        self,
        schedule_version_id: UUID,
        command: ResizeBreakCommand,
    ) -> ShiftSegment:
        move_command = MoveBreakCommand(
            type="MoveBreak",
            payload={
                "segment_id": command.payload.segment_id,
                "start_time": command.payload.start_time,
                "end_time": command.payload.end_time,
            },
        )
        return await self._move_break(schedule_version_id, move_command)

    async def _create_work_segment(
        self,
        schedule_version_id: UUID,
        command: CreateWorkSegmentCommand,
    ) -> ShiftSegment:
        work_shift = await self._get_work_shift(schedule_version_id, command.payload.work_shift_id)
        if not (
            work_shift.start_time
            <= command.payload.start_time
            < command.payload.end_time
            <= work_shift.end_time
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Work segment is outside work shift",
            )
        overlapping = await self.session.scalars(
            select(ShiftSegment)
            .where(ShiftSegment.work_shift_id == work_shift.id)
            .where(ShiftSegment.start_time < command.payload.end_time)
            .where(ShiftSegment.end_time > command.payload.start_time)
            .limit(1)
        )
        if overlapping.first() is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Work segment overlaps existing segment",
            )
        segment = ShiftSegment(
            work_shift_id=work_shift.id,
            schedule_version_id=schedule_version_id,
            store_id=work_shift.store_id,
            segment_date=work_shift.work_date,
            start_time=command.payload.start_time,
            end_time=command.payload.end_time,
            segment_type="WORK",
            position_id=command.payload.position_id,
            task_type_id=None,
            label=None,
            assignment_source="manual",
            is_locked=False,
        )
        self.session.add(segment)
        await self.session.flush()
        return segment

    async def _validate_position(self, store_id: UUID, position_id: UUID) -> Position:
        position = await self.session.get(Position, position_id)
        if position is None or position.store_id != store_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Position not found",
            )
        return position

    async def _validate_task_type(self, store_id: UUID, task_type_id: UUID) -> None:
        task_type = await self.session.get(TaskType, task_type_id)
        if task_type is None or task_type.store_id != store_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Task type not found",
            )

    async def _validate_task_segment_window(
        self,
        store_id: UUID,
        task_type_id: UUID | None,
        segment_date: date,
        start_time: time,
        end_time: time,
    ) -> None:
        if task_type_id is None:
            return
        task_type = await self.session.get(TaskType, task_type_id)
        if task_type is None or task_type.code != "M":
            return
        store = await self.session.get(Store, store_id)
        close_time = closing_time_for_date(store, segment_date)
        is_primary = start_time == time(10, 0) and end_time == time(10, 30)
        is_close = start_time == add_minutes(close_time, -30) and end_time == close_time
        if not is_primary and not is_close:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="M task must be assigned at 10:00-10:30 or the close 30-minute window",
            )

    async def _validate_staff(self, store_id: UUID, staff_member_id: UUID) -> None:
        staff_member = await self.session.get(StaffMember, staff_member_id)
        if staff_member is None or staff_member.store_id != store_id or not staff_member.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Staff member not found",
            )

    async def _find_segment_covering_break(
        self,
        work_shift_id: UUID,
        start_time: time,
        end_time: time,
    ) -> ShiftSegment | None:
        result = await self.session.scalars(
            select(ShiftSegment)
            .where(ShiftSegment.work_shift_id == work_shift_id)
            .where(ShiftSegment.start_time <= start_time)
            .where(ShiftSegment.end_time >= end_time)
            .limit(1)
        )
        return result.first()

    @staticmethod
    def _segment_snapshot(segment: ShiftSegment) -> dict:
        return {
            "id": str(segment.id),
            "work_shift_id": str(segment.work_shift_id),
            "store_id": str(segment.store_id),
            "segment_date": segment.segment_date.isoformat(),
            "start_time": segment.start_time.isoformat(),
            "end_time": segment.end_time.isoformat(),
            "segment_type": segment.segment_type,
            "position_id": str(segment.position_id) if segment.position_id else None,
            "task_type_id": str(segment.task_type_id) if segment.task_type_id else None,
            "is_locked": segment.is_locked,
            "lock_scope": segment.lock_scope,
            "lock_reason": segment.lock_reason,
            "assignment_source": segment.assignment_source,
            "label": segment.label,
        }

    @staticmethod
    def _work_shift_snapshot(work_shift: WorkShift) -> dict:
        return {
            "id": str(work_shift.id),
            "schedule_version_id": str(work_shift.schedule_version_id),
            "staff_member_id": str(work_shift.staff_member_id),
            "store_id": str(work_shift.store_id),
            "work_date": work_shift.work_date.isoformat(),
            "start_time": work_shift.start_time.isoformat(),
            "end_time": work_shift.end_time.isoformat(),
            "total_work_minutes": work_shift.total_work_minutes,
            "total_break_minutes": work_shift.total_break_minutes,
            "assignment_source": work_shift.assignment_source,
            "is_locked": work_shift.is_locked,
            "lock_scope": work_shift.lock_scope,
            "lock_reason": work_shift.lock_reason,
            "note": work_shift.note,
        }

    async def _work_shift_with_segments_snapshot(self, work_shift: WorkShift) -> dict:
        result = await self.session.scalars(
            select(ShiftSegment)
            .where(ShiftSegment.work_shift_id == work_shift.id)
            .order_by(ShiftSegment.start_time)
        )
        return {
            **self._work_shift_snapshot(work_shift),
            "segments": [self._segment_snapshot(segment) for segment in result],
        }

    @staticmethod
    def _inverse_command_payload(
        command: ScheduleCommand,
        before: object,
        after: object,
    ) -> dict | None:
        if isinstance(command, CreateWorkShiftCommand) and isinstance(after, dict):
            return {
                "type": "DeleteWorkShift",
                "payload": {"work_shift_id": after["id"]},
            }
        if isinstance(command, CreateTaskSegmentCommand) and isinstance(after, dict):
            return {
                "type": "DeleteShiftSegment",
                "payload": {"segment_id": after["id"]},
            }
        if isinstance(command, CreateWorkSegmentCommand) and isinstance(after, dict):
            return {
                "type": "DeleteShiftSegment",
                "payload": {"segment_id": after["id"]},
            }
        if isinstance(command, RestoreWorkShiftCommand) and isinstance(after, dict):
            return {
                "type": "DeleteWorkShift",
                "payload": {"work_shift_id": after["id"]},
            }
        if isinstance(command, UpdateWorkShiftCommand) and isinstance(before, dict):
            return {
                "type": "UpdateWorkShift",
                "payload": {
                    "work_shift_id": before["id"],
                    "staff_member_id": before["staff_member_id"],
                    "start_time": before["start_time"],
                    "end_time": before["end_time"],
                },
            }
        if isinstance(command, AssignStaffCommand) and isinstance(before, dict):
            return {
                "type": "AssignStaff",
                "payload": {
                    "work_shift_id": before["id"],
                    "staff_member_id": before["staff_member_id"],
                },
            }
        if isinstance(command, DeleteWorkShiftCommand) and isinstance(before, dict):
            return {
                "type": "RestoreWorkShift",
                "payload": {"snapshot": before},
            }
        if isinstance(command, DeleteShiftSegmentCommand) and isinstance(before, dict):
            return {
                "type": "RestoreShiftSegment",
                "payload": {"snapshot": before},
            }
        if isinstance(command, RestoreShiftSegmentCommand) and isinstance(after, dict):
            return {
                "type": "DeleteShiftSegment",
                "payload": {"segment_id": after["id"]},
            }
        if isinstance(command, SwapStaffCommand):
            return command.model_dump(mode="json")
        if isinstance(command, ResizeWorkShiftCommand) and isinstance(before, dict):
            return {
                "type": "ResizeWorkShift",
                "payload": {
                    "work_shift_id": before["id"],
                    "start_time": before["start_time"],
                    "end_time": before["end_time"],
                },
            }
        if isinstance(command, ResizeSegmentCommand) and isinstance(before, dict):
            return {
                "type": "ResizeSegment",
                "payload": {
                    "segment_id": before["id"],
                    "start_time": before["start_time"],
                    "end_time": before["end_time"],
                },
            }
        if isinstance(command, UpdateSegmentPositionCommand) and isinstance(before, dict):
            return inverse_segment_assignment(before)
        if isinstance(command, UpdateSegmentTaskCommand) and isinstance(before, dict):
            return inverse_segment_assignment(before)
        if isinstance(command, UpdateSegmentBreakCommand) and isinstance(before, dict):
            return inverse_segment_assignment(before)
        if isinstance(command, MoveBreakCommand) and isinstance(before, dict):
            return inverse_break_move(before)
        if isinstance(command, ResizeBreakCommand) and isinstance(before, dict):
            return inverse_break_move(before)
        if isinstance(command, MoveTaskSegmentCommand) and isinstance(before, dict):
            return {
                "type": "MoveTaskSegment",
                "payload": {
                    "segment_id": before["id"],
                    "start_time": before["start_time"],
                    "end_time": before["end_time"],
                },
            }
        if isinstance(command, SplitSegmentCommand) and isinstance(after, dict):
            created = after.get("created_segment")
            updated = after.get("updated_segment")
            if isinstance(created, dict) and isinstance(updated, dict):
                return {
                    "type": "MergeSegment",
                    "payload": {
                        "first_segment_id": updated["id"],
                        "second_segment_id": created["id"],
                    },
                }
        if isinstance(command, MergeSegmentCommand) and isinstance(before, list):
            first = before[0] if before else None
            if isinstance(first, dict):
                return {
                    "type": "SplitSegment",
                    "payload": {
                        "segment_id": first["id"],
                        "split_time": first["end_time"],
                    },
                }
        if isinstance(command, LockSegmentCommand):
            return {
                "type": "UnlockSegment",
                "payload": {"segment_id": str(command.payload.segment_id)},
            }
        if isinstance(command, UnlockSegmentCommand) and isinstance(before, dict):
            return {
                "type": "LockSegment",
                "payload": {
                    "segment_id": before["id"],
                    "lock_scope": before.get("lock_scope") or "full",
                    "lock_reason": before.get("lock_reason"),
                },
            }
        return None


def minutes_between(start_time: time, end_time: time) -> int:
    return end_time.hour * 60 + end_time.minute - start_time.hour * 60 - start_time.minute


def minutes_since_midnight(value: time) -> int:
    return value.hour * 60 + value.minute


def add_minutes(value: time, minutes: int) -> time:
    total = max(0, min(24 * 60 - 1, value.hour * 60 + value.minute + minutes))
    return time(total // 60, total % 60)


def closing_time_for_date(store: Store | None, target_date: date) -> time:
    if store is None:
        return time(22, 0)
    business_hours = store.business_hours or {}
    day_type = "holiday" if target_date.weekday() >= 5 else "weekday"
    hours = business_hours.get(day_type)
    if isinstance(hours, dict) and isinstance(hours.get("close"), str):
        return time.fromisoformat(hours["close"])
    if isinstance(hours, dict) and isinstance(hours.get("closing_time"), str):
        return time.fromisoformat(hours["closing_time"])
    return store.closing_time


def inverse_segment_assignment(before: dict) -> dict | None:
    if before.get("segment_type") == "WORK" and before.get("position_id") is not None:
        return {
            "type": "UpdateSegmentPosition",
            "payload": {
                "segment_id": before["id"],
                "position_id": before["position_id"],
                "label": before.get("label"),
            },
        }
    if before.get("segment_type") == "TASK" and before.get("task_type_id") is not None:
        return {
            "type": "UpdateSegmentTask",
            "payload": {
                "segment_id": before["id"],
                "task_type_id": before["task_type_id"],
            },
        }
    if before.get("segment_type") == "BREAK":
        return {
            "type": "UpdateSegmentBreak",
            "payload": {
                "segment_id": before["id"],
            },
        }
    return None


def inverse_break_move(before: dict) -> dict:
    return {
        "type": "MoveBreak",
        "payload": {
            "segment_id": before["id"],
            "start_time": before["start_time"],
            "end_time": before["end_time"],
        },
    }


def segment_from_snapshot(schedule_version: ScheduleVersion, snapshot: dict) -> ShiftSegment:
    return ShiftSegment(
        id=UUID(snapshot["id"]),
        work_shift_id=UUID(snapshot["work_shift_id"]),
        schedule_version_id=schedule_version.id,
        store_id=schedule_version.store_id,
        segment_date=date.fromisoformat(snapshot["segment_date"]),
        start_time=time.fromisoformat(snapshot["start_time"]),
        end_time=time.fromisoformat(snapshot["end_time"]),
        segment_type=snapshot["segment_type"],
        position_id=UUID(snapshot["position_id"]) if snapshot.get("position_id") else None,
        task_type_id=UUID(snapshot["task_type_id"]) if snapshot.get("task_type_id") else None,
        label=snapshot.get("label"),
        assignment_source=snapshot.get("assignment_source", "manual"),
        is_locked=snapshot.get("is_locked", False),
        lock_scope=snapshot.get("lock_scope"),
        lock_reason=snapshot.get("lock_reason"),
    )
