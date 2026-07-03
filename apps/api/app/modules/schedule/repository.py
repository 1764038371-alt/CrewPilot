from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.schedule.models import (
    OptimizationRun,
    ScheduleChangeLog,
    ScheduleVersion,
    ScheduleWarning,
    ShiftSegment,
    WorkShift,
)


class ScheduleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_schedule_version(self, schedule_version_id: UUID) -> ScheduleVersion | None:
        return await self.session.get(ScheduleVersion, schedule_version_id)

    async def get_work_shift(self, work_shift_id: UUID) -> WorkShift | None:
        return await self.session.get(WorkShift, work_shift_id)

    async def get_shift_segment(self, shift_segment_id: UUID) -> ShiftSegment | None:
        return await self.session.get(ShiftSegment, shift_segment_id)

    async def get_current_schedule_version(
        self,
        planning_period_id: UUID,
    ) -> ScheduleVersion | None:
        result = await self.session.scalars(
            select(ScheduleVersion)
            .where(ScheduleVersion.planning_period_id == planning_period_id)
            .order_by(ScheduleVersion.version_number.desc())
            .limit(1)
        )
        return result.first()

    async def next_version_number(self, planning_period_id: UUID) -> int:
        result = await self.session.scalar(
            select(func.max(ScheduleVersion.version_number)).where(
                ScheduleVersion.planning_period_id == planning_period_id
            )
        )
        return int(result or 0) + 1

    async def list_work_shifts(self, schedule_version_id: UUID) -> list[WorkShift]:
        result = await self.session.scalars(
            select(WorkShift)
            .where(WorkShift.schedule_version_id == schedule_version_id)
            .order_by(WorkShift.work_date, WorkShift.start_time)
        )
        return list(result)

    async def list_shift_segments(self, schedule_version_id: UUID) -> list[ShiftSegment]:
        result = await self.session.scalars(
            select(ShiftSegment)
            .where(ShiftSegment.schedule_version_id == schedule_version_id)
            .order_by(ShiftSegment.segment_date, ShiftSegment.start_time)
        )
        return list(result)

    async def list_warnings(self, schedule_version_id: UUID) -> list[ScheduleWarning]:
        result = await self.session.scalars(
            select(ScheduleWarning)
            .where(ScheduleWarning.schedule_version_id == schedule_version_id)
            .order_by(ScheduleWarning.created_at, ScheduleWarning.id)
        )
        return list(result)

    async def list_change_logs(self, schedule_version_id: UUID) -> list[ScheduleChangeLog]:
        result = await self.session.scalars(
            select(ScheduleChangeLog)
            .where(ScheduleChangeLog.schedule_version_id == schedule_version_id)
            .order_by(ScheduleChangeLog.created_at.desc())
            .limit(50)
        )
        return list(result)

    async def list_optimization_runs(self, schedule_version_id: UUID) -> list[OptimizationRun]:
        result = await self.session.scalars(
            select(OptimizationRun)
            .where(OptimizationRun.schedule_version_id == schedule_version_id)
            .order_by(OptimizationRun.created_at.desc())
            .limit(20)
        )
        return list(result)

    async def save(self) -> None:
        await self.session.commit()
