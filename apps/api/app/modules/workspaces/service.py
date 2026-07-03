from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.planning.repository import PlanningRepository
from app.modules.schedule.repository import ScheduleRepository
from app.modules.schedule_editor.warnings import WarningService
from app.modules.stores.repository import StoreRepository
from app.modules.workspaces.schemas import WorkspaceRead, WorkspaceStaffSkillRead
from app.shared.errors import not_found
from app.shared.schemas import (
    PlanningPeriodRead,
    PositionRead,
    ScheduleVersionRead,
    ScheduleWarningRead,
    ShiftRequestRead,
    ShiftRequirementRead,
    ShiftSegmentRead,
    SkillDefinitionRead,
    StaffMemberRead,
    StoreRead,
    TaskTypeRead,
    WorkShiftRead,
)


class WorkspaceService:
    def __init__(self, session: AsyncSession) -> None:
        self.planning_repository = PlanningRepository(session)
        self.schedule_repository = ScheduleRepository(session)
        self.session = session
        self.store_repository = StoreRepository(session)

    async def get_workspace(self, planning_period_id: UUID) -> WorkspaceRead:
        planning_period = await self.planning_repository.get_planning_period(planning_period_id)
        if planning_period is None:
            raise not_found("Planning period not found")

        store = await self.store_repository.get_store(planning_period.store_id)
        if store is None:
            raise not_found("Store not found")

        current_schedule_version = await self.schedule_repository.get_current_schedule_version(
            planning_period.id
        )
        work_shifts = []
        shift_segments = []
        warnings = []
        if current_schedule_version is not None:
            await WarningService(self.session).recalculate(current_schedule_version.id)
            await self.session.commit()
            work_shifts = await self.schedule_repository.list_work_shifts(
                current_schedule_version.id
            )
            shift_segments = await self.schedule_repository.list_shift_segments(
                current_schedule_version.id
            )
            warnings = await self.schedule_repository.list_warnings(current_schedule_version.id)

        staff_members = await self.store_repository.list_staff_members(planning_period.store_id)
        active_staff_ids = {staff_member.id for staff_member in staff_members}
        work_shifts = [
            work_shift
            for work_shift in work_shifts
            if work_shift.staff_member_id in active_staff_ids
        ]
        visible_work_shift_ids = {work_shift.id for work_shift in work_shifts}
        shift_segments = [
            shift_segment
            for shift_segment in shift_segments
            if shift_segment.work_shift_id in visible_work_shift_ids
        ]
        warnings = [
            warning
            for warning in warnings
            if (
                warning.work_shift_id is None
                or warning.work_shift_id in visible_work_shift_ids
            )
        ]

        positions = await self.store_repository.list_positions(planning_period.store_id)
        task_types = await self.store_repository.list_task_types(planning_period.store_id)
        skill_definitions = await self.store_repository.list_skill_definitions(
            planning_period.store_id
        )
        staff_skills = await self.store_repository.list_staff_skills(
            [staff_member.id for staff_member in staff_members]
        )
        shift_requests = await self.planning_repository.list_shift_requests(planning_period.id)
        shift_requirements = await self.planning_repository.list_shift_requirements(
            planning_period.id
        )

        return WorkspaceRead(
            planning_period=PlanningPeriodRead.model_validate(planning_period),
            store=StoreRead.model_validate(store),
            current_schedule_version=(
                await self._schedule_version_read(current_schedule_version)
                if current_schedule_version is not None
                else None
            ),
            staff_members=[StaffMemberRead.model_validate(item) for item in staff_members],
            positions=[PositionRead.model_validate(item) for item in positions],
            task_types=[TaskTypeRead.model_validate(item) for item in task_types],
            skill_definitions=[
                SkillDefinitionRead.model_validate(item) for item in skill_definitions
            ],
            staff_skills=[
                WorkspaceStaffSkillRead(
                    staff_member_id=item.staff_member_id,
                    skill_definition_id=item.skill_definition_id,
                )
                for item in staff_skills
            ],
            shift_requests=[ShiftRequestRead.model_validate(item) for item in shift_requests],
            shift_requirements=[
                ShiftRequirementRead.model_validate(item) for item in shift_requirements
            ],
            work_shifts=[WorkShiftRead.model_validate(item) for item in work_shifts],
            shift_segments=[ShiftSegmentRead.model_validate(item) for item in shift_segments],
            warnings=[ScheduleWarningRead.model_validate(item) for item in warnings],
        )

    async def _schedule_version_read(self, schedule_version) -> ScheduleVersionRead:
        read = ScheduleVersionRead.model_validate(schedule_version)
        if schedule_version.published_by_user_id is None:
            return read
        user = await self.session.get(User, schedule_version.published_by_user_id)
        if user is not None:
            read.published_by = user.display_name
        return read
