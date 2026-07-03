from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.modules.auth.dependencies import ManagerUserDep
from app.modules.schedule.schemas import (
    PublishRequest,
    PublishValidationResult,
    ScheduleVersionActionResult,
)
from app.modules.schedule.service import ScheduleService
from app.modules.schedule_editor.commands import ScheduleCommand, ScheduleCommandResult
from app.modules.schedule_editor.service import ScheduleCommandService
from app.shared.schemas import (
    OptimizationRunRead,
    ScheduleChangeLogRead,
    ScheduleVersionRead,
    ShiftSegmentRead,
    WorkShiftRead,
)

router = APIRouter(prefix="/schedule-versions", tags=["schedule-versions"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
BatchIdHeader = Annotated[Optional[UUID], Header(alias="X-CrewPilot-Batch-Id")]
BatchLabelHeader = Annotated[Optional[str], Header(alias="X-CrewPilot-Batch-Label")]


@router.get("/{schedule_version_id}", response_model=ScheduleVersionRead)
async def get_schedule_version(
    schedule_version_id: UUID,
    session: SessionDep,
) -> ScheduleVersionRead:
    return await ScheduleService(session).get_schedule_version(schedule_version_id)


@router.get("/{schedule_version_id}/work-shifts", response_model=list[WorkShiftRead])
async def list_work_shifts(
    schedule_version_id: UUID,
    session: SessionDep,
) -> list[WorkShiftRead]:
    return await ScheduleService(session).list_work_shifts(schedule_version_id)


@router.get("/{schedule_version_id}/shift-segments", response_model=list[ShiftSegmentRead])
async def list_shift_segments(
    schedule_version_id: UUID,
    session: SessionDep,
) -> list[ShiftSegmentRead]:
    return await ScheduleService(session).list_shift_segments(schedule_version_id)


@router.get("/{schedule_version_id}/change-logs", response_model=list[ScheduleChangeLogRead])
async def list_change_logs(
    schedule_version_id: UUID,
    session: SessionDep,
) -> list[ScheduleChangeLogRead]:
    return await ScheduleService(session).list_change_logs(schedule_version_id)


@router.get("/{schedule_version_id}/optimization-runs", response_model=list[OptimizationRunRead])
async def list_optimization_runs(
    schedule_version_id: UUID,
    session: SessionDep,
) -> list[OptimizationRunRead]:
    return await ScheduleService(session).list_optimization_runs(schedule_version_id)


@router.post("/{schedule_version_id}/validate-publish", response_model=PublishValidationResult)
async def validate_publish(
    schedule_version_id: UUID,
    payload: PublishRequest,
    session: SessionDep,
) -> PublishValidationResult:
    return await ScheduleService(session).validate_for_publish(
        schedule_version_id,
        expected_revision=payload.expected_revision,
    )


@router.post("/{schedule_version_id}/approve", response_model=ScheduleVersionActionResult)
async def approve_schedule_version(
    schedule_version_id: UUID,
    session: SessionDep,
    user: ManagerUserDep,
) -> ScheduleVersionActionResult:
    return await ScheduleService(session).approve(schedule_version_id, actor=user)


@router.post("/{schedule_version_id}/publish", response_model=ScheduleVersionActionResult)
async def publish_schedule_version(
    schedule_version_id: UUID,
    payload: PublishRequest,
    session: SessionDep,
    user: ManagerUserDep,
) -> ScheduleVersionActionResult:
    return await ScheduleService(session).publish(
        schedule_version_id,
        expected_revision=payload.expected_revision,
        actor=user,
    )


@router.post("/{schedule_version_id}/archive", response_model=ScheduleVersionActionResult)
async def archive_schedule_version(
    schedule_version_id: UUID,
    session: SessionDep,
    user: ManagerUserDep,
) -> ScheduleVersionActionResult:
    return await ScheduleService(session).archive(schedule_version_id, actor=user)


@router.post("/{schedule_version_id}/duplicate", response_model=ScheduleVersionActionResult)
async def duplicate_schedule_version(
    schedule_version_id: UUID,
    session: SessionDep,
    user: ManagerUserDep,
) -> ScheduleVersionActionResult:
    return await ScheduleService(session).duplicate(schedule_version_id, actor=user)


@router.post("/{schedule_version_id}/commands", response_model=ScheduleCommandResult)
async def execute_schedule_command(
    schedule_version_id: UUID,
    command: ScheduleCommand,
    session: SessionDep,
    user: ManagerUserDep,
    batch_id: BatchIdHeader = None,
    batch_label: BatchLabelHeader = None,
) -> ScheduleCommandResult:
    return await ScheduleCommandService(session).execute(
        schedule_version_id,
        command,
        actor=user,
        source_type="batch" if batch_id else None,
        batch_id=batch_id,
        batch_label=batch_label,
    )


@router.post("/{schedule_version_id}/undo", response_model=ScheduleCommandResult)
async def undo_latest_schedule_command(
    schedule_version_id: UUID,
    session: SessionDep,
    user: ManagerUserDep,
) -> ScheduleCommandResult:
    return await ScheduleCommandService(session).undo_latest(schedule_version_id, actor=user)


@router.post("/{schedule_version_id}/redo", response_model=ScheduleCommandResult)
async def redo_latest_schedule_command(
    schedule_version_id: UUID,
    session: SessionDep,
    user: ManagerUserDep,
) -> ScheduleCommandResult:
    return await ScheduleCommandService(session).redo_latest(schedule_version_id, actor=user)
