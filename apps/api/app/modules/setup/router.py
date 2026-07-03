from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.modules.auth.dependencies import ManagerUserDep
from app.modules.setup.schemas import DailyDraftRead, DailyDraftWrite, SetupRead, SetupWrite
from app.modules.setup.service import SetupService

router = APIRouter(tags=["setup"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/setup", response_model=SetupRead)
async def get_setup(session: SessionDep) -> SetupRead:
    return await SetupService(session).get_setup()


@router.put("/setup", response_model=SetupRead)
async def save_setup(
    payload: SetupWrite,
    session: SessionDep,
    user: ManagerUserDep,
) -> SetupRead:
    return await SetupService(session).save_setup(payload)


@router.get("/planning-periods/{planning_period_id}/daily-draft", response_model=DailyDraftRead)
async def get_daily_draft(
    planning_period_id: UUID,
    target_date: date,
    session: SessionDep,
) -> DailyDraftRead:
    return await SetupService(session).get_daily_draft(planning_period_id, target_date)


@router.put("/planning-periods/{planning_period_id}/daily-draft", response_model=DailyDraftRead)
async def save_daily_draft(
    planning_period_id: UUID,
    payload: DailyDraftWrite,
    session: SessionDep,
    user: ManagerUserDep,
) -> DailyDraftRead:
    return await SetupService(session).save_daily_draft(planning_period_id, payload)
