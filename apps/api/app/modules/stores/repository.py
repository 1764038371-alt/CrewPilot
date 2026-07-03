from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.staff.models import StaffMember
from app.modules.stores.models import Position, SkillDefinition, StaffSkill, Store, TaskType


class StoreRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_store(self, store_id: UUID) -> Store | None:
        return await self.session.get(Store, store_id)

    async def list_staff_members(self, store_id: UUID) -> list[StaffMember]:
        result = await self.session.scalars(
            select(StaffMember)
            .where(StaffMember.store_id == store_id)
            .where(StaffMember.is_active.is_(True))
            .order_by(StaffMember.priority, StaffMember.display_name)
        )
        return list(result)

    async def list_positions(self, store_id: UUID) -> list[Position]:
        result = await self.session.scalars(
            select(Position)
            .where(Position.store_id == store_id)
            .order_by(Position.priority, Position.code)
        )
        return list(result)

    async def list_task_types(self, store_id: UUID) -> list[TaskType]:
        result = await self.session.scalars(
            select(TaskType)
            .where(TaskType.store_id == store_id)
            .order_by(TaskType.priority, TaskType.code)
        )
        return list(result)

    async def list_skill_definitions(self, store_id: UUID) -> list[SkillDefinition]:
        result = await self.session.scalars(
            select(SkillDefinition)
            .where(SkillDefinition.store_id == store_id)
            .order_by(SkillDefinition.code)
        )
        return list(result)

    async def list_staff_skills(self, staff_member_ids: list[UUID]) -> list[StaffSkill]:
        if not staff_member_ids:
            return []
        result = await self.session.scalars(
            select(StaffSkill).where(StaffSkill.staff_member_id.in_(staff_member_ids))
        )
        return list(result)
