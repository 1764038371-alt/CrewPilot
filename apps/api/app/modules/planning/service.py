from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.planning.repository import PlanningRepository
from app.shared.errors import not_found
from app.shared.schemas import PlanningPeriodRead


class PlanningService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = PlanningRepository(session)

    async def get_planning_period(self, planning_period_id: UUID) -> PlanningPeriodRead:
        planning_period = await self.repository.get_planning_period(planning_period_id)
        if planning_period is None:
            raise not_found("Planning period not found")
        return PlanningPeriodRead.model_validate(planning_period)

