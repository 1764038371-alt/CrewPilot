from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.modules.stores.service import StoreService
from app.shared.schemas import PositionRead, SkillDefinitionRead, StaffMemberRead, TaskTypeRead

router = APIRouter(prefix="/stores", tags=["stores"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/{store_id}/staff-members", response_model=list[StaffMemberRead])
async def list_staff_members(
    store_id: UUID,
    session: SessionDep,
) -> list[StaffMemberRead]:
    return await StoreService(session).list_staff_members(store_id)


@router.get("/{store_id}/positions", response_model=list[PositionRead])
async def list_positions(
    store_id: UUID,
    session: SessionDep,
) -> list[PositionRead]:
    return await StoreService(session).list_positions(store_id)


@router.get("/{store_id}/task-types", response_model=list[TaskTypeRead])
async def list_task_types(
    store_id: UUID,
    session: SessionDep,
) -> list[TaskTypeRead]:
    return await StoreService(session).list_task_types(store_id)


@router.get("/{store_id}/skill-definitions", response_model=list[SkillDefinitionRead])
async def list_skill_definitions(
    store_id: UUID,
    session: SessionDep,
) -> list[SkillDefinitionRead]:
    return await StoreService(session).list_skill_definitions(store_id)
