from __future__ import annotations

import asyncio
from datetime import date, time
from uuid import UUID

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.modules.planning.models import PlanningPeriod, ShiftRequirement
from app.modules.schedule.models import ScheduleVersion, ShiftSegment, WorkShift
from app.modules.staff.models import StaffMember
from app.modules.stores.models import Position, SkillDefinition, StaffSkill, Store, TaskType

STORE_ID = UUID("10000000-0000-0000-0000-000000000001")
PLANNING_PERIOD_ID = UUID("20000000-0000-0000-0000-000000000001")
SCHEDULE_VERSION_ID = UUID("30000000-0000-0000-0000-000000000001")

STAFF_TANAKA_ID = UUID("40000000-0000-0000-0000-000000000001")
STAFF_SATO_ID = UUID("40000000-0000-0000-0000-000000000002")
STAFF_SUZUKI_ID = UUID("40000000-0000-0000-0000-000000000003")

POSITION_C_ID = UUID("50000000-0000-0000-0000-000000000001")
POSITION_F_ID = UUID("50000000-0000-0000-0000-000000000002")
POSITION_B_ID = UUID("50000000-0000-0000-0000-000000000003")
POSITION_S_ID = UUID("50000000-0000-0000-0000-000000000004")

TASK_M_ID = UUID("60000000-0000-0000-0000-000000000001")

SKILL_C_ID = UUID("70000000-0000-0000-0000-000000000001")
SKILL_C_OPEN_ID = UUID("70000000-0000-0000-0000-000000000002")
SKILL_B_CLOSE_ID = UUID("70000000-0000-0000-0000-000000000003")
SKILL_M_ID = UUID("70000000-0000-0000-0000-000000000004")
SKILL_B_ID = UUID("70000000-0000-0000-0000-000000000005")
SKILL_F_ID = UUID("70000000-0000-0000-0000-000000000006")
SKILL_S_ID = UUID("70000000-0000-0000-0000-000000000007")
SKILL_B_OPEN_ID = UUID("70000000-0000-0000-0000-000000000008")
SKILL_C_CLOSE_ID = UUID("70000000-0000-0000-0000-000000000009")
SKILL_F_CLOSE_ID = UUID("70000000-0000-0000-0000-000000000010")

WORK_SHIFT_TANAKA_ID = UUID("80000000-0000-0000-0000-000000000001")
WORK_SHIFT_SATO_ID = UUID("80000000-0000-0000-0000-000000000002")
WORK_SHIFT_SUZUKI_ID = UUID("80000000-0000-0000-0000-000000000003")


async def main() -> None:
    async with AsyncSessionLocal() as session:
        existing_store = await session.scalar(select(Store).where(Store.id == STORE_ID))
        if existing_store is not None:
            print("Seed data already exists.")
            return

        store = Store(
            id=STORE_ID,
            name="CrewPilot Cafe",
            code="CREWPILOT-CAFE",
            timezone="Asia/Tokyo",
            opening_time=time(9, 0),
            closing_time=time(18, 0),
            time_slot_minutes=15,
            is_active=True,
        )
        session.add(store)
        await session.flush()

        positions = [
            Position(
                id=POSITION_C_ID,
                store_id=STORE_ID,
                code="C",
                name="キャッシャー",
                priority=10,
                color="#0ea5e9",
                is_active=True,
            ),
            Position(
                id=POSITION_F_ID,
                store_id=STORE_ID,
                code="F",
                name="フロア",
                priority=20,
                color="#22c55e",
                is_active=True,
            ),
            Position(
                id=POSITION_B_ID,
                store_id=STORE_ID,
                code="B",
                name="バリ",
                priority=30,
                color="#a855f7",
                is_active=True,
            ),
            Position(
                id=POSITION_S_ID,
                store_id=STORE_ID,
                code="S",
                name="サブ",
                priority=40,
                color="#f97316",
                is_active=True,
            ),
        ]
        session.add_all(positions)
        await session.flush()

        task_m = TaskType(
            id=TASK_M_ID,
            store_id=STORE_ID,
            code="M",
            name="入金",
            description="店舗外で行う入金業務",
            default_duration_minutes=45,
            requires_offsite=True,
            priority=10,
            is_active=True,
        )
        session.add(task_m)
        await session.flush()

        skills = [
            SkillDefinition(
                id=SKILL_C_ID,
                store_id=STORE_ID,
                code="C",
                name="キャッシャー",
                skill_category="position",
                position_id=POSITION_C_ID,
                task_type_id=None,
                description=None,
                is_active=True,
            ),
            SkillDefinition(
                id=SKILL_C_OPEN_ID,
                store_id=STORE_ID,
                code="C_OPEN",
                name="オープンC",
                skill_category="opening",
                position_id=POSITION_C_ID,
                task_type_id=None,
                description=None,
                is_active=True,
            ),
            SkillDefinition(
                id=SKILL_B_CLOSE_ID,
                store_id=STORE_ID,
                code="B_CLOSE",
                name="クローズB",
                skill_category="closing",
                position_id=POSITION_B_ID,
                task_type_id=None,
                description=None,
                is_active=True,
            ),
            SkillDefinition(
                id=SKILL_B_ID,
                store_id=STORE_ID,
                code="B",
                name="バリ",
                skill_category="position",
                position_id=POSITION_B_ID,
                task_type_id=None,
                description=None,
                is_active=True,
            ),
            SkillDefinition(
                id=SKILL_F_ID,
                store_id=STORE_ID,
                code="F",
                name="フロア",
                skill_category="position",
                position_id=POSITION_F_ID,
                task_type_id=None,
                description=None,
                is_active=True,
            ),
            SkillDefinition(
                id=SKILL_S_ID,
                store_id=STORE_ID,
                code="S",
                name="サブ",
                skill_category="position",
                position_id=POSITION_S_ID,
                task_type_id=None,
                description=None,
                is_active=True,
            ),
            SkillDefinition(
                id=SKILL_B_OPEN_ID,
                store_id=STORE_ID,
                code="B_OPEN",
                name="オープンB",
                skill_category="opening",
                position_id=POSITION_B_ID,
                task_type_id=None,
                description=None,
                is_active=True,
            ),
            SkillDefinition(
                id=SKILL_C_CLOSE_ID,
                store_id=STORE_ID,
                code="C_CLOSE",
                name="クローズC",
                skill_category="closing",
                position_id=POSITION_C_ID,
                task_type_id=None,
                description=None,
                is_active=True,
            ),
            SkillDefinition(
                id=SKILL_F_CLOSE_ID,
                store_id=STORE_ID,
                code="F_CLOSE",
                name="クローズF",
                skill_category="closing",
                position_id=POSITION_F_ID,
                task_type_id=None,
                description=None,
                is_active=True,
            ),
            SkillDefinition(
                id=SKILL_M_ID,
                store_id=STORE_ID,
                code="M",
                name="入金",
                skill_category="task",
                position_id=None,
                task_type_id=TASK_M_ID,
                description=None,
                is_active=True,
            ),
        ]
        session.add_all(skills)
        await session.flush()

        staff_members = [
            StaffMember(
                id=STAFF_TANAKA_ID,
                store_id=STORE_ID,
                display_name="田中",
                employment_type="part_time",
                max_weekly_minutes=1800,
                min_shift_minutes=180,
                max_shift_minutes=480,
                priority=10,
                is_active=True,
                joined_on=date(2025, 4, 1),
                left_on=None,
            ),
            StaffMember(
                id=STAFF_SATO_ID,
                store_id=STORE_ID,
                display_name="佐藤",
                employment_type="part_time",
                max_weekly_minutes=1500,
                min_shift_minutes=180,
                max_shift_minutes=420,
                priority=20,
                is_active=True,
                joined_on=date(2025, 7, 1),
                left_on=None,
            ),
            StaffMember(
                id=STAFF_SUZUKI_ID,
                store_id=STORE_ID,
                display_name="鈴木",
                employment_type="part_time",
                max_weekly_minutes=1200,
                min_shift_minutes=180,
                max_shift_minutes=360,
                priority=30,
                is_active=True,
                joined_on=date(2026, 1, 15),
                left_on=None,
            ),
        ]
        session.add_all(staff_members)
        await session.flush()

        session.add_all(
            [
                StaffSkill(
                    staff_member_id=STAFF_TANAKA_ID,
                    skill_definition_id=SKILL_C_ID,
                    skill_level=5,
                    is_preferred=True,
                ),
                StaffSkill(
                    staff_member_id=STAFF_TANAKA_ID,
                    skill_definition_id=SKILL_B_ID,
                    skill_level=3,
                    is_preferred=False,
                ),
                StaffSkill(
                    staff_member_id=STAFF_TANAKA_ID,
                    skill_definition_id=SKILL_C_OPEN_ID,
                    skill_level=4,
                    is_preferred=True,
                ),
                StaffSkill(
                    staff_member_id=STAFF_TANAKA_ID,
                    skill_definition_id=SKILL_B_OPEN_ID,
                    skill_level=4,
                    is_preferred=True,
                ),
                StaffSkill(
                    staff_member_id=STAFF_TANAKA_ID,
                    skill_definition_id=SKILL_B_CLOSE_ID,
                    skill_level=4,
                    is_preferred=True,
                ),
                StaffSkill(
                    staff_member_id=STAFF_TANAKA_ID,
                    skill_definition_id=SKILL_C_CLOSE_ID,
                    skill_level=4,
                    is_preferred=True,
                ),
                StaffSkill(
                    staff_member_id=STAFF_TANAKA_ID,
                    skill_definition_id=SKILL_M_ID,
                    skill_level=3,
                    is_preferred=False,
                ),
                StaffSkill(
                    staff_member_id=STAFF_SATO_ID,
                    skill_definition_id=SKILL_C_ID,
                    skill_level=3,
                    is_preferred=False,
                ),
                StaffSkill(
                    staff_member_id=STAFF_SATO_ID,
                    skill_definition_id=SKILL_F_ID,
                    skill_level=3,
                    is_preferred=False,
                ),
                StaffSkill(
                    staff_member_id=STAFF_SATO_ID,
                    skill_definition_id=SKILL_C_OPEN_ID,
                    skill_level=4,
                    is_preferred=True,
                ),
                StaffSkill(
                    staff_member_id=STAFF_SATO_ID,
                    skill_definition_id=SKILL_B_CLOSE_ID,
                    skill_level=4,
                    is_preferred=True,
                ),
                StaffSkill(
                    staff_member_id=STAFF_SATO_ID,
                    skill_definition_id=SKILL_C_CLOSE_ID,
                    skill_level=4,
                    is_preferred=True,
                ),
                StaffSkill(
                    staff_member_id=STAFF_SATO_ID,
                    skill_definition_id=SKILL_F_CLOSE_ID,
                    skill_level=4,
                    is_preferred=True,
                ),
                StaffSkill(
                    staff_member_id=STAFF_SUZUKI_ID,
                    skill_definition_id=SKILL_C_ID,
                    skill_level=2,
                    is_preferred=False,
                ),
            ]
        )
        await session.flush()

        planning_period = PlanningPeriod(
            id=PLANNING_PERIOD_ID,
            store_id=STORE_ID,
            name="2026年7月前半シフト",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 15),
            status="draft",
            request_deadline=None,
        )
        session.add(planning_period)
        await session.flush()

        schedule_version = ScheduleVersion(
            id=SCHEDULE_VERSION_ID,
            planning_period_id=PLANNING_PERIOD_ID,
            store_id=STORE_ID,
            parent_schedule_version_id=None,
            version_number=1,
            revision=0,
            name="v1 サンプル自動生成案",
            status="draft",
            is_locked=False,
            published_at=None,
            change_summary="MVP表示確認用サンプル",
        )
        session.add(schedule_version)
        await session.flush()

        session.add_all(
            [
                ShiftRequirement(
                    planning_period_id=PLANNING_PERIOD_ID,
                    store_id=STORE_ID,
                    requirement_date=date(2026, 7, 1),
                    start_time=time(9, 0),
                    end_time=time(12, 0),
                    requirement_type="WORK",
                    position_id=POSITION_C_ID,
                    task_type_id=None,
                    min_staff_count=1,
                    target_staff_count=2,
                    max_staff_count=None,
                    priority=10,
                ),
                ShiftRequirement(
                    planning_period_id=PLANNING_PERIOD_ID,
                    store_id=STORE_ID,
                    requirement_date=date(2026, 7, 1),
                    start_time=time(10, 0),
                    end_time=time(10, 30),
                    requirement_type="TASK",
                    position_id=None,
                    task_type_id=TASK_M_ID,
                    min_staff_count=1,
                    target_staff_count=1,
                    max_staff_count=1,
                    priority=5,
                ),
                ShiftRequirement(
                    planning_period_id=PLANNING_PERIOD_ID,
                    store_id=STORE_ID,
                    requirement_date=date(2026, 7, 2),
                    start_time=time(11, 0),
                    end_time=time(12, 0),
                    requirement_type="WORK",
                    position_id=POSITION_C_ID,
                    task_type_id=None,
                    min_staff_count=2,
                    target_staff_count=2,
                    max_staff_count=None,
                    priority=20,
                ),
            ]
        )
        await session.flush()

        work_shifts = [
            WorkShift(
                id=WORK_SHIFT_TANAKA_ID,
                schedule_version_id=SCHEDULE_VERSION_ID,
                staff_member_id=STAFF_TANAKA_ID,
                store_id=STORE_ID,
                work_date=date(2026, 7, 1),
                start_time=time(9, 0),
                end_time=time(17, 0),
                total_work_minutes=435,
                total_break_minutes=45,
                assignment_source="optimized",
                is_locked=False,
                lock_scope=None,
                locked_at=None,
                lock_reason=None,
                note=None,
            ),
            WorkShift(
                id=WORK_SHIFT_SATO_ID,
                schedule_version_id=SCHEDULE_VERSION_ID,
                staff_member_id=STAFF_SATO_ID,
                store_id=STORE_ID,
                work_date=date(2026, 7, 1),
                start_time=time(10, 0),
                end_time=time(16, 0),
                total_work_minutes=345,
                total_break_minutes=15,
                assignment_source="optimized",
                is_locked=True,
                lock_scope="full",
                locked_at=None,
                lock_reason="店長確認済み",
                note=None,
            ),
            WorkShift(
                id=WORK_SHIFT_SUZUKI_ID,
                schedule_version_id=SCHEDULE_VERSION_ID,
                staff_member_id=STAFF_SUZUKI_ID,
                store_id=STORE_ID,
                work_date=date(2026, 7, 2),
                start_time=time(11, 0),
                end_time=time(15, 0),
                total_work_minutes=240,
                total_break_minutes=0,
                assignment_source="manual",
                is_locked=False,
                lock_scope=None,
                locked_at=None,
                lock_reason=None,
                note="手動追加サンプル",
            ),
        ]
        session.add_all(work_shifts)
        await session.flush()

        session.add_all(
            [
                ShiftSegment(
                    work_shift_id=WORK_SHIFT_TANAKA_ID,
                    schedule_version_id=SCHEDULE_VERSION_ID,
                    store_id=STORE_ID,
                    segment_date=date(2026, 7, 1),
                    start_time=time(9, 0),
                    end_time=time(10, 0),
                    segment_type="WORK",
                    position_id=POSITION_C_ID,
                    task_type_id=None,
                    label="C_OPEN",
                    assignment_source="optimized",
                    is_locked=False,
                ),
                ShiftSegment(
                    work_shift_id=WORK_SHIFT_TANAKA_ID,
                    schedule_version_id=SCHEDULE_VERSION_ID,
                    store_id=STORE_ID,
                    segment_date=date(2026, 7, 1),
                    start_time=time(10, 0),
                    end_time=time(12, 0),
                    segment_type="WORK",
                    position_id=POSITION_C_ID,
                    task_type_id=None,
                    label=None,
                    assignment_source="optimized",
                    is_locked=False,
                ),
                ShiftSegment(
                    work_shift_id=WORK_SHIFT_TANAKA_ID,
                    schedule_version_id=SCHEDULE_VERSION_ID,
                    store_id=STORE_ID,
                    segment_date=date(2026, 7, 1),
                    start_time=time(12, 0),
                    end_time=time(12, 45),
                    segment_type="BREAK",
                    position_id=None,
                    task_type_id=None,
                    label=None,
                    assignment_source="optimized",
                    is_locked=False,
                ),
                ShiftSegment(
                    work_shift_id=WORK_SHIFT_TANAKA_ID,
                    schedule_version_id=SCHEDULE_VERSION_ID,
                    store_id=STORE_ID,
                    segment_date=date(2026, 7, 1),
                    start_time=time(12, 45),
                    end_time=time(14, 0),
                    segment_type="WORK",
                    position_id=POSITION_F_ID,
                    task_type_id=None,
                    label=None,
                    assignment_source="optimized",
                    is_locked=False,
                ),
                ShiftSegment(
                    work_shift_id=WORK_SHIFT_TANAKA_ID,
                    schedule_version_id=SCHEDULE_VERSION_ID,
                    store_id=STORE_ID,
                    segment_date=date(2026, 7, 1),
                    start_time=time(14, 45),
                    end_time=time(17, 0),
                    segment_type="WORK",
                    position_id=POSITION_B_ID,
                    task_type_id=None,
                    label=None,
                    assignment_source="optimized",
                    is_locked=False,
                ),
                ShiftSegment(
                    work_shift_id=WORK_SHIFT_SATO_ID,
                    schedule_version_id=SCHEDULE_VERSION_ID,
                    store_id=STORE_ID,
                    segment_date=date(2026, 7, 1),
                    start_time=time(10, 0),
                    end_time=time(13, 0),
                    segment_type="WORK",
                    position_id=POSITION_B_ID,
                    task_type_id=None,
                    label=None,
                    assignment_source="optimized",
                    is_locked=True,
                    lock_scope="full",
                    lock_reason="店長確認済み",
                ),
                ShiftSegment(
                    work_shift_id=WORK_SHIFT_SATO_ID,
                    schedule_version_id=SCHEDULE_VERSION_ID,
                    store_id=STORE_ID,
                    segment_date=date(2026, 7, 1),
                    start_time=time(13, 0),
                    end_time=time(13, 15),
                    segment_type="BREAK",
                    position_id=None,
                    task_type_id=None,
                    label=None,
                    assignment_source="optimized",
                    is_locked=False,
                ),
                ShiftSegment(
                    work_shift_id=WORK_SHIFT_SATO_ID,
                    schedule_version_id=SCHEDULE_VERSION_ID,
                    store_id=STORE_ID,
                    segment_date=date(2026, 7, 1),
                    start_time=time(13, 15),
                    end_time=time(16, 0),
                    segment_type="WORK",
                    position_id=POSITION_S_ID,
                    task_type_id=None,
                    label=None,
                    assignment_source="optimized",
                    is_locked=False,
                ),
                ShiftSegment(
                    work_shift_id=WORK_SHIFT_SUZUKI_ID,
                    schedule_version_id=SCHEDULE_VERSION_ID,
                    store_id=STORE_ID,
                    segment_date=date(2026, 7, 2),
                    start_time=time(11, 0),
                    end_time=time(15, 0),
                    segment_type="WORK",
                    position_id=POSITION_F_ID,
                    task_type_id=None,
                    label=None,
                    assignment_source="manual",
                    is_locked=False,
                ),
            ]
        )

        await session.commit()
        print("Seed data inserted.")
        print(f"PlanningPeriod ID: {PLANNING_PERIOD_ID}")


if __name__ == "__main__":
    asyncio.run(main())
