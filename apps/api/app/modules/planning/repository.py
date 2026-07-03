from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.planning.models import PlanningPeriod, ShiftRequest, ShiftRequirement


class PlanningRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_planning_period(self, planning_period_id: UUID) -> PlanningPeriod | None:
        return await self.session.get(PlanningPeriod, planning_period_id)

    async def list_shift_requests(self, planning_period_id: UUID) -> list[ShiftRequest]:
        result = await self.session.scalars(
            select(ShiftRequest)
            .where(ShiftRequest.planning_period_id == planning_period_id)
            .order_by(ShiftRequest.request_date, ShiftRequest.staff_member_id)
        )
        return list(result)

    async def list_shift_requirements(self, planning_period_id: UUID) -> list[ShiftRequirement]:
        result = await self.session.scalars(
            select(ShiftRequirement)
            .where(ShiftRequirement.planning_period_id == planning_period_id)
            .order_by(ShiftRequirement.requirement_date, ShiftRequirement.start_time)
        )
        return list(result)
