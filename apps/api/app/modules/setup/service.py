from __future__ import annotations

from datetime import date, time
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.planning.models import PlanningPeriod, ShiftRequest, ShiftRequirement
from app.modules.setup.schemas import (
    DailyDraftRead,
    DailyDraftWrite,
    SetupRead,
    SetupWrite,
    StaffSkillRead,
)
from app.modules.staff.models import StaffMember
from app.modules.stores.models import Position, SkillDefinition, StaffSkill, Store, TaskType
from app.shared.errors import not_found
from app.shared.schemas import (
    PlanningPeriodRead,
    PositionRead,
    ShiftRequestRead,
    SkillDefinitionRead,
    StaffMemberRead,
    StoreRead,
    TaskTypeRead,
)


class SetupService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_setup(self) -> SetupRead:
        store = await self._current_store()
        planning_period = await self._current_planning_period(store.id)
        staff_members = await self._staff_members(store.id)
        positions = await self._positions(store.id)
        task_types = await self._task_types(store.id)
        skill_definitions = await self._skill_definitions(store.id)
        staff_skills = await self._staff_skills([staff.id for staff in staff_members])
        return SetupRead(
            store=StoreRead.model_validate(store),
            planning_period=PlanningPeriodRead.model_validate(planning_period),
            staff_members=[StaffMemberRead.model_validate(item) for item in staff_members],
            positions=[PositionRead.model_validate(item) for item in positions],
            task_types=[TaskTypeRead.model_validate(item) for item in task_types],
            skill_definitions=[
                SkillDefinitionRead.model_validate(item) for item in skill_definitions
            ],
            staff_skills=[
                StaffSkillRead(
                    staff_member_id=item.staff_member_id,
                    skill_definition_id=item.skill_definition_id,
                )
                for item in staff_skills
            ],
        )

    async def save_setup(self, payload: SetupWrite) -> SetupRead:
        store = await self._current_store()
        store.name = payload.store.name
        store.opening_time = payload.store.opening_time
        store.closing_time = payload.store.closing_time
        store.business_hours = payload.store.business_hours
        store.operational_settings = payload.store.operational_settings

        positions = await self._positions(store.id)
        skill_definitions = await self._skill_definitions(store.id)
        kept_staff_ids: set[UUID] = set()
        for index, staff_payload in enumerate(payload.staff_members, start=1):
            staff = await self._find_staff(
                store.id,
                staff_payload.id,
                staff_payload.employee_number,
            )
            if staff is None:
                staff = StaffMember(id=uuid4(), store_id=store.id)
                self.session.add(staff)
            staff.employee_number = staff_payload.employee_number
            staff.display_name = staff_payload.display_name
            staff.employment_type = staff_payload.employment_type
            staff.hourly_wage_yen = staff_payload.hourly_wage_yen
            staff.priority = index * 10
            staff.is_active = staff_payload.is_active
            await self.session.flush()
            kept_staff_ids.add(staff.id)
            await self._replace_staff_skills(staff, staff_payload, positions, skill_definitions)

        await self._deactivate_removed_staff(store.id, kept_staff_ids)

        await self.session.commit()
        return await self.get_setup()

    async def get_daily_draft(self, planning_period_id: UUID, target_date: date) -> DailyDraftRead:
        planning_period = await self.session.get(PlanningPeriod, planning_period_id)
        if planning_period is None:
            raise not_found("Planning period not found")
        store = await self.session.get(Store, planning_period.store_id)
        if store is None:
            raise not_found("Store not found")
        store = await self.session.get(Store, planning_period.store_id)
        if store is None:
            raise not_found("Store not found")
        requests = await self.session.scalars(
            select(ShiftRequest)
            .where(ShiftRequest.planning_period_id == planning_period_id)
            .where(ShiftRequest.request_date == target_date)
            .order_by(ShiftRequest.staff_member_id)
        )
        return DailyDraftRead(
            planning_period=PlanningPeriodRead.model_validate(planning_period),
            store=StoreRead.model_validate(store),
            staff_members=[
                StaffMemberRead.model_validate(item)
                for item in await self._staff_members(planning_period.store_id)
            ],
            shift_requests=[ShiftRequestRead.model_validate(item) for item in requests],
        )

    async def save_daily_draft(
        self,
        planning_period_id: UUID,
        payload: DailyDraftWrite,
    ) -> DailyDraftRead:
        planning_period = await self.session.get(PlanningPeriod, planning_period_id)
        if planning_period is None:
            raise not_found("Planning period not found")
        store = await self.session.get(Store, planning_period.store_id)
        if store is None:
            raise not_found("Store not found")

        await self.session.execute(
            delete(ShiftRequest)
            .where(ShiftRequest.planning_period_id == planning_period_id)
            .where(ShiftRequest.request_date == payload.target_date)
        )
        await self.session.execute(
            delete(ShiftRequirement)
            .where(ShiftRequirement.planning_period_id == planning_period_id)
            .where(ShiftRequirement.requirement_date == payload.target_date)
        )

        for request in payload.requests:
            self.session.add(
                ShiftRequest(
                    planning_period_id=planning_period_id,
                    staff_member_id=request.staff_member_id,
                    request_date=payload.target_date,
                    start_time=request.start_time,
                    end_time=request.end_time,
                    request_type=request.request_type,
                    priority=10,
                    note=request.note,
                )
            )
        await self._create_requirements(planning_period, payload, store)
        await self.session.commit()
        return await self.get_daily_draft(planning_period_id, payload.target_date)

    async def _create_requirements(
        self,
        planning_period: PlanningPeriod,
        payload: DailyDraftWrite,
        store: Store,
    ) -> None:
        templates = payload.required_staff_templates or templates_for_date(
            store.operational_settings,
            payload.target_date,
        )
        for item in templates:
            self.session.add(
                ShiftRequirement(
                    planning_period_id=planning_period.id,
                    store_id=planning_period.store_id,
                    requirement_date=payload.target_date,
                    start_time=parse_time(item.get("start_time"), time(9, 0)),
                    end_time=parse_time(item.get("end_time"), time(18, 0)),
                    requirement_type="WORK",
                    position_id=None,
                    task_type_id=None,
                    min_staff_count=int(item.get("target_staff_count", 1)),
                    target_staff_count=int(item.get("target_staff_count", 1)),
                    max_staff_count=None,
                    priority=100,
                )
            )
        task_m = await self.session.scalar(
            select(TaskType)
            .where(TaskType.store_id == planning_period.store_id)
            .where(TaskType.code == "M")
        )
        if task_m is not None:
            self.session.add(
                ShiftRequirement(
                    planning_period_id=planning_period.id,
                    store_id=planning_period.store_id,
                    requirement_date=payload.target_date,
                    start_time=time(10, 0),
                    end_time=time(10, 30),
                    requirement_type="TASK",
                    position_id=None,
                    task_type_id=task_m.id,
                    min_staff_count=1,
                    target_staff_count=1,
                    max_staff_count=1,
                    priority=5,
                )
            )

    async def _current_store(self) -> Store:
        store = await self.session.scalar(select(Store).order_by(Store.created_at).limit(1))
        if store is None:
            raise not_found("Store not found")
        return store

    async def _current_planning_period(self, store_id: UUID) -> PlanningPeriod:
        planning_period = await self.session.scalar(
            select(PlanningPeriod)
            .where(PlanningPeriod.store_id == store_id)
            .order_by(PlanningPeriod.start_date.desc())
            .limit(1)
        )
        if planning_period is None:
            raise not_found("Planning period not found")
        return planning_period

    async def _find_staff(
        self,
        store_id: UUID,
        staff_id: UUID | None,
        employee_number: str,
    ) -> StaffMember | None:
        if staff_id is not None:
            staff = await self.session.get(StaffMember, staff_id)
            if staff is not None and staff.store_id == store_id:
                return staff
        return await self.session.scalar(
            select(StaffMember)
            .where(StaffMember.store_id == store_id)
            .where(StaffMember.employee_number == employee_number)
        )

    async def _replace_staff_skills(
        self,
        staff: StaffMember,
        payload,
        positions: list[Position],
        skill_definitions: list[SkillDefinition],
    ) -> None:
        await self.session.execute(
            delete(StaffSkill).where(StaffSkill.staff_member_id == staff.id)
        )
        skill_ids: set[UUID] = set()
        skill_ids.update(payload.skill_definition_ids)
        for position_id in payload.position_ids:
            skill_ids.update(
                skill.id
                for skill in skill_definitions
                if skill.position_id == position_id and skill.skill_category == "position"
            )
        if payload.can_open:
            skill_ids.update(skill.id for skill in skill_definitions if "OPEN" in skill.code)
        if payload.can_close:
            skill_ids.update(skill.id for skill in skill_definitions if "CLOSE" in skill.code)
        if payload.can_deposit:
            skill_ids.update(skill.id for skill in skill_definitions if skill.code == "M")
        valid_skill_ids = {skill.id for skill in skill_definitions}
        skill_ids = skill_ids & valid_skill_ids
        self.session.add_all(
            [
                StaffSkill(
                    staff_member_id=staff.id,
                    skill_definition_id=skill_id,
                    skill_level=3,
                    is_preferred=False,
                )
                for skill_id in skill_ids
            ]
        )

    async def _deactivate_removed_staff(
        self,
        store_id: UUID,
        kept_staff_ids: set[UUID],
    ) -> None:
        result = await self.session.scalars(
            select(StaffMember)
            .where(StaffMember.store_id == store_id)
            .where(StaffMember.is_active.is_(True))
        )
        for staff in result:
            if staff.id not in kept_staff_ids:
                staff.is_active = False
                await self.session.execute(
                    delete(StaffSkill).where(StaffSkill.staff_member_id == staff.id)
                )

    async def _staff_members(self, store_id: UUID) -> list[StaffMember]:
        result = await self.session.scalars(
            select(StaffMember)
            .where(StaffMember.store_id == store_id)
            .where(StaffMember.is_active.is_(True))
            .order_by(StaffMember.employee_number, StaffMember.priority)
        )
        return list(result)

    async def _positions(self, store_id: UUID) -> list[Position]:
        result = await self.session.scalars(
            select(Position)
            .where(Position.store_id == store_id)
            .where(Position.is_active.is_(True))
            .order_by(Position.priority, Position.code)
        )
        return list(result)

    async def _task_types(self, store_id: UUID) -> list[TaskType]:
        result = await self.session.scalars(select(TaskType).where(TaskType.store_id == store_id))
        return list(result)

    async def _skill_definitions(self, store_id: UUID) -> list[SkillDefinition]:
        result = await self.session.scalars(
            select(SkillDefinition).where(SkillDefinition.store_id == store_id)
        )
        return list(result)

    async def _staff_skills(self, staff_ids: list[UUID]) -> list[StaffSkill]:
        if not staff_ids:
            return []
        result = await self.session.scalars(
            select(StaffSkill).where(StaffSkill.staff_member_id.in_(staff_ids))
        )
        return list(result)


def parse_time(value: object, fallback: time) -> time:
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        hour, minute = value.split(":", 1)
        return time(int(hour), int(minute))
    return fallback


def templates_for_date(settings: dict | None, target_date: date) -> list[dict]:
    if not settings:
        return []
    day_type = "holiday" if target_date.weekday() >= 5 else "weekday"
    templates = settings.get(f"{day_type}_required_staff_templates")
    if isinstance(templates, list):
        return templates
    legacy_templates = settings.get("required_staff_templates")
    if isinstance(legacy_templates, list):
        return legacy_templates
    return []
