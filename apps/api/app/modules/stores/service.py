from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.stores.repository import StoreRepository
from app.shared.schemas import PositionRead, SkillDefinitionRead, StaffMemberRead, TaskTypeRead


class StoreService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = StoreRepository(session)

    async def list_staff_members(self, store_id: UUID) -> list[StaffMemberRead]:
        items = await self.repository.list_staff_members(store_id)
        return [StaffMemberRead.model_validate(item) for item in items]

    async def list_positions(self, store_id: UUID) -> list[PositionRead]:
        items = await self.repository.list_positions(store_id)
        return [PositionRead.model_validate(item) for item in items]

    async def list_task_types(self, store_id: UUID) -> list[TaskTypeRead]:
        items = await self.repository.list_task_types(store_id)
        return [TaskTypeRead.model_validate(item) for item in items]

    async def list_skill_definitions(self, store_id: UUID) -> list[SkillDefinitionRead]:
        items = await self.repository.list_skill_definitions(store_id)
        return [SkillDefinitionRead.model_validate(item) for item in items]

