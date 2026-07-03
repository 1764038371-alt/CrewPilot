from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.modules.workspaces.schemas import WorkspaceRead
from app.modules.workspaces.service import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/planning-periods/{planning_period_id}", response_model=WorkspaceRead)
async def get_workspace(
    planning_period_id: UUID,
    session: SessionDep,
) -> WorkspaceRead:
    return await WorkspaceService(session).get_workspace(planning_period_id)
