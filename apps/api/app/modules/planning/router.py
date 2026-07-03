from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.modules.planning.service import PlanningService
from app.shared.schemas import PlanningPeriodRead

router = APIRouter(prefix="/planning-periods", tags=["planning-periods"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/{planning_period_id}", response_model=PlanningPeriodRead)
async def get_planning_period(
    planning_period_id: UUID,
    session: SessionDep,
) -> PlanningPeriodRead:
    return await PlanningService(session).get_planning_period(planning_period_id)
