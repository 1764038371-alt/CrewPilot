from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.schedule.models import (
    OptimizationProposal,
    ScheduleVersion,
    ShiftSegment,
    WorkShift,
)
from app.modules.schedule.repository import ScheduleRepository
from app.modules.schedule.schemas import (
    PublishValidationIssue,
    PublishValidationResult,
    ScheduleVersionActionResult,
    ShiftSegmentUpdate,
    WorkShiftUpdate,
)
from app.modules.schedule_editor.warnings import WarningService
from app.shared.errors import not_found
from app.shared.schemas import (
    OptimizationRunRead,
    ScheduleChangeLogRead,
    ScheduleVersionRead,
    ShiftSegmentRead,
    WorkShiftRead,
)


class ScheduleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ScheduleRepository(session)

    async def get_schedule_version(self, schedule_version_id: UUID) -> ScheduleVersionRead:
        schedule_version = await self.repository.get_schedule_version(schedule_version_id)
        if schedule_version is None:
            raise not_found("Schedule version not found")
        return ScheduleVersionRead.model_validate(schedule_version)

    async def list_work_shifts(self, schedule_version_id: UUID) -> list[WorkShiftRead]:
        items = await self.repository.list_work_shifts(schedule_version_id)
        return [WorkShiftRead.model_validate(item) for item in items]

    async def list_shift_segments(self, schedule_version_id: UUID) -> list[ShiftSegmentRead]:
        items = await self.repository.list_shift_segments(schedule_version_id)
        return [ShiftSegmentRead.model_validate(item) for item in items]

    async def list_change_logs(self, schedule_version_id: UUID) -> list[ScheduleChangeLogRead]:
        items = await self.repository.list_change_logs(schedule_version_id)
        user_ids = {
            item.executed_by_user_id
            for item in items
            if item.executed_by_user_id is not None
        }
        users_by_id: dict[UUID, User] = {}
        if user_ids:
            users = await self.session.scalars(select(User).where(User.id.in_(user_ids)))
            users_by_id = {user.id: user for user in users}

        reads: list[ScheduleChangeLogRead] = []
        for item in items:
            read = ScheduleChangeLogRead.model_validate(item)
            if item.executed_by_user_id is not None and item.executed_by_user_id in users_by_id:
                read.executed_by = users_by_id[item.executed_by_user_id].display_name
            reads.append(read)
        return reads

    async def list_optimization_runs(
        self,
        schedule_version_id: UUID,
    ) -> list[OptimizationRunRead]:
        items = await self.repository.list_optimization_runs(schedule_version_id)
        return [OptimizationRunRead.model_validate(item) for item in items]

    async def validate_for_publish(
        self,
        schedule_version_id: UUID,
        *,
        expected_revision: int | None = None,
    ) -> PublishValidationResult:
        schedule_version = await self.repository.get_schedule_version(schedule_version_id)
        if schedule_version is None:
            raise not_found("Schedule version not found")

        await WarningService(self.session).recalculate(schedule_version_id)
        await self.session.flush()

        issues: list[PublishValidationIssue] = []
        if schedule_version.status not in {"draft", "approved"}:
            issues.append(
                PublishValidationIssue(
                    code="INVALID_STATUS",
                    message="draftまたはapprovedのScheduleVersionのみ公開できます。",
                )
            )
        if expected_revision is not None and schedule_version.revision != expected_revision:
            issues.append(
                PublishValidationIssue(
                    code="STALE_REVISION",
                    message="ScheduleVersionが最新Revisionではありません。再読み込みしてください。",
                )
            )

        warnings = await self.repository.list_warnings(schedule_version_id)
        for warning in warnings:
            if warning.severity in {"error", "critical"}:
                issues.append(
                    PublishValidationIssue(
                        code="CRITICAL_WARNING",
                        message=f"{warning.warning_type}: {warning.message}",
                    )
                )

        pending_proposals = await self._count_pending_proposals(schedule_version_id)
        if pending_proposals > 0:
            issues.append(
                PublishValidationIssue(
                    code="PENDING_PROPOSAL",
                    message=f"未適用のAI Proposalが{pending_proposals}件残っています。",
                )
            )

        work_shifts = await self.repository.list_work_shifts(schedule_version_id)
        segments = await self.repository.list_shift_segments(schedule_version_id)
        if not work_shifts:
            issues.append(
                PublishValidationIssue(
                    code="MISSING_WORK_SHIFTS",
                    message="勤務が1件もありません。",
                )
            )
        if not segments:
            issues.append(
                PublishValidationIssue(
                    code="MISSING_SEGMENTS",
                    message="勤務中の区間が1件もありません。",
                )
            )
        for shift in work_shifts:
            if not any(segment.work_shift_id == shift.id for segment in segments):
                label = f"{shift.work_date} {shift.start_time}-{shift.end_time}"
                issues.append(
                    PublishValidationIssue(
                        code="WORK_SHIFT_WITHOUT_SEGMENTS",
                        message=f"{label} の勤務に区間がありません。",
                    )
                )
        for segment in segments:
            label = f"{segment.segment_date} {segment.start_time}-{segment.end_time}"
            if segment.segment_type == "WORK" and segment.position_id is None:
                issues.append(
                    PublishValidationIssue(
                        code="WORK_SEGMENT_MISSING_POSITION",
                        message=f"{label} のWORKにポジションがありません。",
                    )
                )
            if segment.segment_type == "TASK" and segment.task_type_id is None:
                issues.append(
                    PublishValidationIssue(
                        code="TASK_SEGMENT_MISSING_TASK",
                        message=f"{label} のTASKに業務種別がありません。",
                    )
                )

        return PublishValidationResult(
            schedule_version_id=schedule_version_id,
            can_publish=not issues,
            issues=issues,
        )

    async def approve(
        self,
        schedule_version_id: UUID,
        *,
        actor: User | None = None,
    ) -> ScheduleVersionActionResult:
        schedule_version = await self._get_action_target(schedule_version_id)
        if schedule_version.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only draft schedule versions can be approved",
            )
        schedule_version.status = "approved"
        await self.repository.save()
        return ScheduleVersionActionResult(
            schedule_version=ScheduleVersionRead.model_validate(schedule_version),
        )

    async def publish(
        self,
        schedule_version_id: UUID,
        *,
        expected_revision: int | None = None,
        actor: User | None = None,
    ) -> ScheduleVersionActionResult:
        schedule_version = await self._get_action_target(schedule_version_id)
        validation = await self.validate_for_publish(
            schedule_version_id,
            expected_revision=expected_revision,
        )
        if not validation.can_publish:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=validation.model_dump(mode="json"),
            )
        schedule_version.status = "published"
        schedule_version.is_locked = True
        schedule_version.published_at = datetime.utcnow()
        schedule_version.published_by_user_id = actor.id if actor else None
        await self.repository.save()
        if actor is not None:
            schedule_version.published_by = actor.display_name
        return ScheduleVersionActionResult(
            schedule_version=ScheduleVersionRead.model_validate(schedule_version),
            validation=validation,
        )

    async def archive(
        self,
        schedule_version_id: UUID,
        *,
        actor: User | None = None,
    ) -> ScheduleVersionActionResult:
        schedule_version = await self._get_action_target(schedule_version_id)
        if schedule_version.status == "archived":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Schedule version is already archived",
            )
        schedule_version.status = "archived"
        schedule_version.is_locked = True
        await self.repository.save()
        return ScheduleVersionActionResult(
            schedule_version=ScheduleVersionRead.model_validate(schedule_version),
        )

    async def duplicate(
        self,
        schedule_version_id: UUID,
        *,
        actor: User | None = None,
    ) -> ScheduleVersionActionResult:
        source = await self.repository.get_schedule_version(schedule_version_id)
        if source is None:
            raise not_found("Schedule version not found")
        next_version = await self.repository.next_version_number(source.planning_period_id)
        duplicate = ScheduleVersion(
            planning_period_id=source.planning_period_id,
            store_id=source.store_id,
            parent_schedule_version_id=source.id,
            version_number=next_version,
            revision=0,
            name=f"{source.name} copy",
            status="draft",
            is_locked=False,
            published_at=None,
            change_summary="公開済みVersionから複製",
        )
        self.session.add(duplicate)
        await self.session.flush()

        work_shift_id_map: dict[UUID, UUID] = {}
        for shift in await self.repository.list_work_shifts(schedule_version_id):
            new_id = uuid4()
            work_shift_id_map[shift.id] = new_id
            self.session.add(
                WorkShift(
                    id=new_id,
                    schedule_version_id=duplicate.id,
                    staff_member_id=shift.staff_member_id,
                    store_id=shift.store_id,
                    work_date=shift.work_date,
                    start_time=shift.start_time,
                    end_time=shift.end_time,
                    total_work_minutes=shift.total_work_minutes,
                    total_break_minutes=shift.total_break_minutes,
                    assignment_source=shift.assignment_source,
                    is_locked=False,
                    lock_scope=None,
                    locked_at=None,
                    lock_reason=None,
                    note=shift.note,
                )
            )
        await self.session.flush()
        for segment in await self.repository.list_shift_segments(schedule_version_id):
            new_work_shift_id = work_shift_id_map.get(segment.work_shift_id)
            if new_work_shift_id is None:
                continue
            self.session.add(
                ShiftSegment(
                    schedule_version_id=duplicate.id,
                    work_shift_id=new_work_shift_id,
                    store_id=segment.store_id,
                    segment_date=segment.segment_date,
                    start_time=segment.start_time,
                    end_time=segment.end_time,
                    segment_type=segment.segment_type,
                    position_id=segment.position_id,
                    task_type_id=segment.task_type_id,
                    label=segment.label,
                    assignment_source=segment.assignment_source,
                    is_locked=False,
                    lock_scope=None,
                    locked_at=None,
                    lock_reason=None,
                    confidence_score=segment.confidence_score,
                    note=segment.note,
                )
            )
        await self.session.commit()
        return ScheduleVersionActionResult(
            schedule_version=ScheduleVersionRead.model_validate(duplicate),
        )

    async def update_work_shift(
        self,
        work_shift_id: UUID,
        payload: WorkShiftUpdate,
    ) -> WorkShiftRead:
        work_shift = await self.repository.get_work_shift(work_shift_id)
        if work_shift is None:
            raise not_found("Work shift not found")

        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(work_shift, field, value)

        await self.repository.save()
        return WorkShiftRead.model_validate(work_shift)

    async def update_shift_segment(
        self,
        shift_segment_id: UUID,
        payload: ShiftSegmentUpdate,
    ) -> ShiftSegmentRead:
        shift_segment = await self.repository.get_shift_segment(shift_segment_id)
        if shift_segment is None:
            raise not_found("Shift segment not found")

        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(shift_segment, field, value)

        if shift_segment.segment_type == "WORK":
            shift_segment.task_type_id = None
        elif shift_segment.segment_type == "TASK":
            shift_segment.position_id = None
        elif shift_segment.segment_type == "BREAK":
            shift_segment.position_id = None
            shift_segment.task_type_id = None

        await self.repository.save()
        return ShiftSegmentRead.model_validate(shift_segment)

    async def _get_action_target(self, schedule_version_id: UUID) -> ScheduleVersion:
        schedule_version = await self.repository.get_schedule_version(schedule_version_id)
        if schedule_version is None:
            raise not_found("Schedule version not found")
        return schedule_version

    async def _count_pending_proposals(self, schedule_version_id: UUID) -> int:
        result = await self.session.scalars(
            select(OptimizationProposal).where(
                OptimizationProposal.schedule_version_id == schedule_version_id,
                OptimizationProposal.status == "pending",
            )
        )
        return len(list(result))
