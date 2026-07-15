from collections import Counter
from datetime import date, time
from types import SimpleNamespace
from typing import Optional
from uuid import UUID

from app.modules.optimization.scope import DateScope, FullScope, OptimizationScopeType
from app.modules.optimization.solver.ortools_solver import (
    MAX_ASSIGNMENT_CANDIDATES,
    ORToolsSolver,
    fairness_score,
)
from app.modules.schedule_editor.warnings import WarningService, requirement_shortage_windows

SHIFT_ID = UUID("10000000-0000-0000-0000-000000000001")
SEGMENT_ID = UUID("20000000-0000-0000-0000-000000000001")
STAFF_ID = UUID("30000000-0000-0000-0000-000000000001")
POSITION_C_ID = UUID("40000000-0000-0000-0000-000000000001")
POSITION_F_ID = UUID("40000000-0000-0000-0000-000000000002")
POSITION_B_ID = UUID("40000000-0000-0000-0000-000000000003")
POSITION_S_ID = UUID("40000000-0000-0000-0000-000000000004")
SKILL_C_ID = UUID("50000000-0000-0000-0000-000000000001")
SKILL_B_ID = UUID("50000000-0000-0000-0000-000000000002")
SKILL_F_ID = UUID("50000000-0000-0000-0000-000000000003")
SKILL_S_ID = UUID("50000000-0000-0000-0000-000000000004")
TASK_M_ID = UUID("60000000-0000-0000-0000-000000000001")
SKILL_M_ID = UUID("70000000-0000-0000-0000-000000000004")
STAFF_SECOND_ID = UUID("30000000-0000-0000-0000-000000000002")
SKILL_C_OPEN_ID = UUID("70000000-0000-0000-0000-000000000005")
SKILL_B_OPEN_ID = UUID("70000000-0000-0000-0000-000000000006")


def test_request_constraint_prevents_assignment_outside_available_time() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    shift = work_shift()
    segment = work_segment(position_id=POSITION_F_ID, start_time=time(13), end_time=time(14))
    decisions = solver._build_decisions(
        scope=FullScope(),
        shifts=[shift],
        segments=[segment],
        warnings=[],
        positions=[position(POSITION_C_ID), position(POSITION_F_ID)],
        requests=[
            SimpleNamespace(
                staff_member_id=STAFF_ID,
                request_date=date(2026, 7, 1),
                start_time=time(9),
                end_time=time(12),
                request_type="available",
            )
        ],
        skills=[skill(SKILL_C_ID, POSITION_C_ID)],
        staff_skills=[staff_skill(SKILL_C_ID)],
    )

    assert decisions == []


def test_staff_shortage_warning_improves_with_proposed_position() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    shift = work_shift()
    segment = work_segment(position_id=POSITION_F_ID, start_time=time(9), end_time=time(10))
    requirement = SimpleNamespace(
        requirement_date=date(2026, 7, 1),
        start_time=time(9),
        end_time=time(10),
        requirement_type="WORK",
        position_id=POSITION_C_ID,
        task_type_id=None,
        min_staff_count=1,
    )

    before = solver._simulate_warning_counts(
        shifts=[shift],
        segments=[segment],
        requirements=[requirement],
        requests=[],
        skills=[skill(SKILL_C_ID, POSITION_C_ID)],
        staff_skills=[staff_skill(SKILL_C_ID)],
        proposed_positions={},
    )
    after = solver._simulate_warning_counts(
        shifts=[shift],
        segments=[segment],
        requirements=[requirement],
        requests=[],
        skills=[skill(SKILL_C_ID, POSITION_C_ID)],
        staff_skills=[staff_skill(SKILL_C_ID)],
        proposed_positions={SEGMENT_ID: POSITION_C_ID},
    )

    assert before["STAFF_SHORTAGE"] == 1
    assert after["STAFF_SHORTAGE"] == 0


def test_locked_segment_is_not_editable() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    decisions = solver._build_decisions(
        scope=FullScope(),
        shifts=[work_shift()],
        segments=[work_segment(position_id=POSITION_F_ID, is_locked=True)],
        warnings=[],
        positions=[position(POSITION_C_ID), position(POSITION_F_ID)],
        requests=[],
        skills=[skill(SKILL_C_ID, POSITION_C_ID)],
        staff_skills=[staff_skill(SKILL_C_ID)],
    )

    assert decisions == []


def test_skill_constraint_excludes_unqualified_position() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    decisions = solver._build_decisions(
        scope=FullScope(),
        shifts=[work_shift()],
        segments=[work_segment(position_id=POSITION_F_ID)],
        warnings=[],
        positions=[position(POSITION_F_ID), position(POSITION_B_ID)],
        requests=[],
        skills=[skill(SKILL_B_ID, POSITION_B_ID)],
        staff_skills=[],
    )

    choice_ids = {choice.position_id for decision in decisions for choice in decision.choices}

    assert POSITION_F_ID in choice_ids
    assert POSITION_B_ID not in choice_ids


def test_staff_shortage_is_detected_for_partial_requirement_window() -> None:
    requirement = requirement_for_position(POSITION_C_ID)
    requirement.position_id = None
    requirement.start_time = time(16)
    requirement.end_time = time(18)
    requirement.min_staff_count = 3
    segments = [
        work_segment_for_shift(
            SHIFT_ID,
            POSITION_C_ID,
            start_time=time(16),
            end_time=time(18),
        ),
        work_segment_for_shift(
            UUID("10000000-0000-0000-0000-000000000002"),
            POSITION_B_ID,
            start_time=time(16),
            end_time=time(17),
        ),
        work_segment_for_shift(
            UUID("10000000-0000-0000-0000-000000000003"),
            POSITION_F_ID,
            start_time=time(16),
            end_time=time(17, 30),
        ),
    ]

    shortage_windows = requirement_shortage_windows(requirement, segments)

    assert shortage_windows == [
        (time(17), time(17, 30), 2),
        (time(17, 30), time(18), 1),
    ]


def test_bc_coverage_warning_detects_missing_b() -> None:
    service = WarningService(session=None)  # type: ignore[arg-type]
    shift_ids = [
        UUID("10000000-0000-0000-0000-000000000011"),
        UUID("10000000-0000-0000-0000-000000000012"),
    ]
    warnings = service._bc_coverage_warnings(
        schedule_version_id=SHIFT_ID,
        shifts=[SimpleNamespace(id=shift_id) for shift_id in shift_ids],
        segments=[
            work_segment_for_shift(
                shift_ids[0],
                POSITION_C_ID,
                start_time=time(10),
                end_time=time(11),
            ),
            work_segment_for_shift(
                shift_ids[1],
                POSITION_F_ID,
                start_time=time(10),
                end_time=time(11),
            ),
        ],
        positions=[
            position(POSITION_B_ID, "B"),
            position(POSITION_C_ID, "C"),
            position(POSITION_F_ID, "F"),
        ],
    )

    assert len(warnings) == 1
    assert warnings[0].warning_type == "BC_COVERAGE"
    assert warnings[0].details["missing_position_codes"] == ["B"]


def test_closing_with_only_two_staff_is_critical() -> None:
    service = WarningService(session=None)  # type: ignore[arg-type]
    shifts = [
        SimpleNamespace(
            id=UUID(f"10000000-0000-0000-0000-00000000003{index}"),
            staff_member_id=staff_id,
            work_date=date(2026, 7, 5),
            start_time=time(14),
            end_time=time(21),
        )
        for index, staff_id in enumerate([STAFF_ID, STAFF_SECOND_ID], start=1)
    ]

    warnings = service._closing_staff_shortage_warnings(
        schedule_version_id=SHIFT_ID,
        shifts=shifts,
        store=SimpleNamespace(
            closing_time=time(21),
            business_hours={},
            operational_settings={},
        ),
    )

    assert len(warnings) == 1
    assert warnings[0].warning_type == "CLOSING_STAFF_SHORTAGE"
    assert warnings[0].severity == "critical"
    assert warnings[0].details["current_count"] == 2
    assert warnings[0].details["min_staff_count"] == 3


def test_position_mix_warning_detects_missing_f_for_three_active_staff() -> None:
    service = WarningService(session=None)  # type: ignore[arg-type]
    shift_ids = [
        UUID("10000000-0000-0000-0000-000000000021"),
        UUID("10000000-0000-0000-0000-000000000022"),
        UUID("10000000-0000-0000-0000-000000000023"),
    ]
    warnings = service._bc_coverage_warnings(
        schedule_version_id=SHIFT_ID,
        shifts=[SimpleNamespace(id=shift_id) for shift_id in shift_ids],
        segments=[
            work_segment_for_shift(
                shift_ids[0],
                POSITION_B_ID,
                start_time=time(10),
                end_time=time(11),
            ),
            work_segment_for_shift(
                shift_ids[1],
                POSITION_C_ID,
                start_time=time(10),
                end_time=time(11),
            ),
            work_segment_for_shift(
                shift_ids[2],
                POSITION_S_ID,
                start_time=time(10),
                end_time=time(11),
            ),
        ],
        positions=[
            position(POSITION_B_ID, "B"),
            position(POSITION_C_ID, "C"),
            position(POSITION_F_ID, "F"),
            position(POSITION_S_ID, "S"),
        ],
    )

    assert len(warnings) == 1
    assert warnings[0].warning_type == "BC_COVERAGE"
    assert warnings[0].details["missing_position_codes"] == ["F"]
    assert warnings[0].details["extra_position_codes"] == ["S"]


def test_break_duration_rules_are_consistent_between_solver_and_warnings() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    warning_service = WarningService(session=None)  # type: ignore[arg-type]

    expected_minutes = {
        239: 0,
        240: 0,
        241: 15,
        360: 15,
        361: 45,
        480: 45,
        481: 60,
        540: 60,
    }

    for shift_minutes, required_break_minutes in expected_minutes.items():
        assert solver._required_break_minutes(shift_minutes) == required_break_minutes
        assert warning_service._required_break_minutes(shift_minutes) == required_break_minutes


def test_position_skill_does_not_accept_opening_skill_for_normal_work() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]

    assert not solver._staff_can_cover_position(
        STAFF_ID,
        POSITION_C_ID,
        [
            skill(SKILL_C_ID, POSITION_C_ID, code="C", skill_category="position"),
            skill(SKILL_C_OPEN_ID, POSITION_C_ID, code="C_OPEN", skill_category="opening"),
        ],
        [staff_skill(SKILL_C_OPEN_ID)],
    )


def test_open_segment_requires_matching_open_skill() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    segment = work_segment(
        position_id=POSITION_C_ID,
        start_time=time(9),
        end_time=time(10),
        label="C_OPEN",
    )

    assert not solver._staff_can_cover_segment(
        STAFF_ID,
        segment,
        [
            skill(SKILL_C_ID, POSITION_C_ID, code="C", skill_category="position"),
            skill(SKILL_C_OPEN_ID, POSITION_C_ID, code="C_OPEN", skill_category="opening"),
        ],
        [staff_skill(SKILL_C_ID)],
    )
    assert solver._staff_can_cover_segment(
        STAFF_ID,
        segment,
        [skill(SKILL_C_OPEN_ID, POSITION_C_ID, code="C_OPEN", skill_category="opening")],
        [staff_skill(SKILL_C_OPEN_ID)],
    )


def test_request_generation_never_assigns_open_c_to_normal_c_only_staff() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    planned = {
        STAFF_ID: [
            {
                "start_time": time(8, 30),
                "end_time": time(10, 30),
                "segment_type": "WORK",
                "position_code": "C",
                "position_id": POSITION_C_ID,
                "task_type_id": None,
                "label": None,
            }
        ],
        STAFF_SECOND_ID: [
            {
                "start_time": time(8, 30),
                "end_time": time(10, 30),
                "segment_type": "WORK",
                "position_code": "B",
                "position_id": POSITION_B_ID,
                "task_type_id": None,
                "label": None,
            }
        ],
    }
    skills = [
        skill(SKILL_C_ID, POSITION_C_ID),
        skill(SKILL_B_ID, POSITION_B_ID),
        skill(SKILL_C_OPEN_ID, POSITION_C_ID, code="C_OPEN", skill_category="opening"),
        skill(SKILL_B_OPEN_ID, POSITION_B_ID, code="B_OPEN", skill_category="opening"),
    ]
    staff_skills = [
        staff_skill(SKILL_C_ID, STAFF_ID),
        staff_skill(SKILL_B_ID, STAFF_ID),
        staff_skill(SKILL_B_OPEN_ID, STAFF_ID),
        staff_skill(SKILL_C_ID, STAFF_SECOND_ID),
        staff_skill(SKILL_B_ID, STAFF_SECOND_ID),
        staff_skill(SKILL_C_OPEN_ID, STAFF_SECOND_ID),
    ]

    solver._apply_opening_role_skills(
        planned,
        date(2026, 7, 1),
        SimpleNamespace(opening_time=time(8, 30), business_hours={}),
        {
            "B": position(POSITION_B_ID, "B"),
            "C": position(POSITION_C_ID, "C"),
        },
        skills,
        staff_skills,
    )

    assert planned[STAFF_ID][0]["label"] == "B_OPEN"
    assert planned[STAFF_SECOND_ID][0]["label"] == "C_OPEN"


def test_work_shift_generation_creates_proposal_for_shortage() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    requirement = requirement_for_position(POSITION_C_ID)

    changes = solver._build_create_work_shift_changes(
        FullScope(),
        shifts=[],
        segments=[],
        requirements=[requirement],
        requests=[],
        staff_members=[staff_member(STAFF_ID)],
        skills=[skill(SKILL_C_ID, POSITION_C_ID)],
        staff_skills=[staff_skill(SKILL_C_ID)],
    )

    assert len(changes) == 1
    assert changes[0].change_type == "create_work_shift"
    assert changes[0].command_type == "CreateWorkShift"


def test_staff_swap_or_assignment_is_created_for_skill_mismatch() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    shift = work_shift()
    segment = work_segment(position_id=POSITION_B_ID)
    candidate_staff_id = UUID("30000000-0000-0000-0000-000000000002")

    changes = solver._build_staff_assignment_changes(
        scope=FullScope(),
        shifts=[shift],
        segments=[segment],
        requests=[],
        warnings=[
            SimpleNamespace(
                warning_type="SKILL_MISMATCH",
                shift_segment_id=SEGMENT_ID,
            )
        ],
        staff_members=[staff_member(STAFF_ID), staff_member(candidate_staff_id)],
        skills=[skill(SKILL_B_ID, POSITION_B_ID)],
        staff_skills=[
            SimpleNamespace(
                staff_member_id=candidate_staff_id,
                skill_definition_id=SKILL_B_ID,
            )
        ],
    )

    assert changes[0].change_type == "assign_staff"
    assert changes[0].command_type == "AssignStaff"


def test_break_generation_creates_proposal_for_violation() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    shift = work_shift()
    segment = work_segment(position_id=POSITION_C_ID, start_time=time(9), end_time=time(15))

    changes = solver._build_break_changes(
        FullScope(),
        shifts=[shift],
        segments=[segment],
        warnings=[
            SimpleNamespace(
                warning_type="BREAK_VIOLATION",
                work_shift_id=SHIFT_ID,
            )
        ],
    )

    assert changes[0].change_type == "create_break"
    assert changes[0].command_type == "CreateBreak"


def test_deposit_is_assigned_to_same_day_when_m_staff_is_available() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    changes = solver._build_deposit_task_changes(
        scope=FullScope(),
        shifts=[work_shift(start_time=time(9), end_time=time(17))],
        segments=[work_segment(position_id=POSITION_C_ID, start_time=time(9), end_time=time(17))],
        requirements=[requirement_for_task()],
        requests=[],
        staff_members=[staff_member(STAFF_ID)],
        skills=[task_skill()],
        staff_skills=[staff_skill(SKILL_M_ID)],
        task_types=[task_type_m()],
        store=store(),
    )

    assert len(changes) == 1
    assert changes[0].change_type == "create_task_segment"
    assert changes[0].command_type == "CreateTaskSegment"
    assert changes[0].command_payload["start_time"] == "10:00:00"
    assert changes[0].explanation["deposit_rule"]["placement"] == "same_day"


def test_deposit_requirement_ignores_non_primary_requirement_time() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    requirement = requirement_for_task()
    requirement.start_time = time(14)
    requirement.end_time = time(14, 30)

    changes = solver._build_deposit_task_changes(
        scope=FullScope(),
        shifts=[work_shift(start_time=time(9), end_time=time(17))],
        segments=[work_segment(position_id=POSITION_C_ID, start_time=time(9), end_time=time(17))],
        requirements=[requirement],
        requests=[],
        staff_members=[staff_member(STAFF_ID)],
        skills=[task_skill()],
        staff_skills=[staff_skill(SKILL_M_ID)],
        task_types=[task_type_m()],
        store=store(),
    )

    assert len(changes) == 1
    assert changes[0].command_payload["start_time"] == "10:00:00"
    assert changes[0].command_payload["end_time"] == "10:30:00"


def test_deposit_assignment_at_other_time_does_not_satisfy_requirement() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    shift = work_shift(start_time=time(9), end_time=time(17))
    base_segment = work_segment(
        position_id=POSITION_C_ID,
        start_time=time(14),
        end_time=time(14, 30),
    )
    segment = SimpleNamespace(
        **{
            **base_segment.__dict__,
            "segment_type": "TASK",
            "position_id": None,
            "task_type_id": TASK_M_ID,
        }
    )

    assert not solver._deposit_requirement_satisfied(
        requirement_for_task(),
        [shift],
        [segment],
        [task_skill()],
        [staff_skill(SKILL_M_ID)],
        store(),
    )


def test_existing_deposit_at_other_time_is_moved_instead_of_duplicated() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    shift = work_shift(start_time=time(9), end_time=time(17))
    base_segment = work_segment(
        position_id=POSITION_C_ID,
        start_time=time(14),
        end_time=time(14, 30),
    )
    segment = SimpleNamespace(
        **{
            **base_segment.__dict__,
            "segment_type": "TASK",
            "position_id": None,
            "task_type_id": TASK_M_ID,
        }
    )

    changes = solver._build_deposit_task_changes(
        scope=FullScope(),
        shifts=[shift],
        segments=[segment],
        requirements=[requirement_for_task()],
        requests=[],
        staff_members=[staff_member(STAFF_ID)],
        skills=[task_skill()],
        staff_skills=[staff_skill(SKILL_M_ID)],
        task_types=[task_type_m()],
        store=store(),
    )

    assert len(changes) == 1
    assert changes[0].change_type == "move_task_segment"
    assert changes[0].command_type == "MoveTaskSegment"
    assert changes[0].command_payload["start_time"] == "10:00:00"


def test_deposit_uses_previous_day_close_when_same_day_is_unavailable() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    previous_shift = SimpleNamespace(
        **{
            **work_shift(start_time=time(21, 30), end_time=time(22)).__dict__,
            "work_date": date(2026, 6, 30),
        }
    )
    changes = solver._build_deposit_task_changes(
        scope=FullScope(),
        shifts=[previous_shift],
        segments=[
            SimpleNamespace(
                **{
                    **work_segment(
                        position_id=POSITION_C_ID,
                        start_time=time(21, 30),
                        end_time=time(22),
                    ).__dict__,
                    "work_shift_id": previous_shift.id,
                    "segment_date": date(2026, 6, 30),
                }
            )
        ],
        requirements=[requirement_for_task()],
        requests=[
            SimpleNamespace(
                staff_member_id=STAFF_ID,
                request_date=date(2026, 7, 1),
                start_time=time(10),
                end_time=time(10, 30),
                request_type="unavailable",
            )
        ],
        staff_members=[staff_member(STAFF_ID)],
        skills=[task_skill()],
        staff_skills=[staff_skill(SKILL_M_ID)],
        task_types=[task_type_m()],
        store=store(),
    )

    assert len(changes) == 1
    assert changes[0].command_payload["start_time"] == "21:30:00"
    assert changes[0].explanation["deposit_rule"]["placement"] == "previous_day_close"
    assert "前日クローズ30分で救済配置可能" in changes[0].explanation["reasons"]


def test_deposit_warning_is_critical_when_primary_and_fallback_are_impossible() -> None:
    warning_service = WarningService(session=None)  # type: ignore[arg-type]
    warnings = warning_service._deposit_warnings(
        schedule_version_id=SHIFT_ID,
        requirements=[requirement_for_task()],
        shifts=[],
        segments=[],
        skill_definitions=[task_skill()],
        staff_skills=[],
        store=store(),
    )

    assert len(warnings) == 1
    assert warnings[0].warning_type == "DEPOSIT_COVERAGE"
    assert warnings[0].severity == "critical"


def test_duplicate_deposit_requirements_create_one_warning() -> None:
    warning_service = WarningService(session=None)  # type: ignore[arg-type]
    requirement = requirement_for_task()

    warnings = warning_service._deposit_warnings(
        schedule_version_id=SHIFT_ID,
        requirements=[requirement, requirement],
        shifts=[],
        segments=[],
        skill_definitions=[task_skill()],
        staff_skills=[],
        store=store(),
    )

    assert len(warnings) == 1
    assert warnings[0].warning_type == "DEPOSIT_COVERAGE"


def test_saved_primary_deposit_clears_deposit_coverage_warning() -> None:
    warning_service = WarningService(session=None)  # type: ignore[arg-type]
    deposit_segment = SimpleNamespace(
        id=SEGMENT_ID,
        work_shift_id=SHIFT_ID,
        segment_date=date(2026, 7, 1),
        start_time=time(10),
        end_time=time(10, 30),
        segment_type="TASK",
        position_id=None,
        task_type_id=TASK_M_ID,
    )

    warnings = warning_service._deposit_warnings(
        schedule_version_id=SHIFT_ID,
        requirements=[requirement_for_task()],
        shifts=[work_shift(start_time=time(6, 45), end_time=time(15, 45))],
        segments=[deposit_segment],
        skill_definitions=[task_skill()],
        staff_skills=[staff_skill(SKILL_M_ID)],
        store=store(),
    )

    assert warnings == []


def test_deposit_is_not_assigned_to_staff_without_m_skill() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    changes = solver._build_deposit_task_changes(
        scope=FullScope(),
        shifts=[work_shift(start_time=time(9), end_time=time(17))],
        segments=[work_segment(position_id=POSITION_C_ID, start_time=time(9), end_time=time(17))],
        requirements=[requirement_for_task()],
        requests=[],
        staff_members=[staff_member(STAFF_ID)],
        skills=[task_skill()],
        staff_skills=[],
        task_types=[task_type_m()],
        store=store(),
    )

    assert changes == []


def test_fairness_score_improves_when_load_is_balanced() -> None:
    short_shift = SimpleNamespace(
        **{
            **work_shift().__dict__,
            "id": UUID("10000000-0000-0000-0000-000000000002"),
            "staff_member_id": UUID("30000000-0000-0000-0000-000000000002"),
            "start_time": time(9),
            "end_time": time(10),
        }
    )
    balanced_second = SimpleNamespace(
        **{
            **work_shift().__dict__,
            "id": UUID("10000000-0000-0000-0000-000000000002"),
            "staff_member_id": UUID("30000000-0000-0000-0000-000000000002"),
            "start_time": time(9),
            "end_time": time(13),
        }
    )

    assert fairness_score([work_shift(start_time=time(9), end_time=time(17)), short_shift]) > (
        fairness_score([work_shift(start_time=time(9), end_time=time(13)), balanced_second])
    )


def test_request_based_generation_uses_requested_work_times() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    request = shift_request(STAFF_ID, start_time=time(6, 45), end_time=time(21, 30))

    changes = solver._build_request_schedule_generation_changes(
        scope=DateScope(type=OptimizationScopeType.DATE, date=date(2026, 7, 1)),
        shifts=[],
        requests=[request],
        staff_members=[staff_member(STAFF_ID)],
        positions=[position(POSITION_C_ID, "C")],
        skills=[skill(SKILL_C_ID, POSITION_C_ID)],
        staff_skills=[staff_skill(SKILL_C_ID)],
        task_types=[],
    )

    create_change = next(change for change in changes if change.command_type == "CreateWorkShift")
    assert create_change.command_payload["start_time"] == "06:45:00"
    assert create_change.command_payload["end_time"] == "21:30:00"


def test_request_based_generation_skips_full_day_off_request() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]

    changes = solver._build_request_schedule_generation_changes(
        scope=DateScope(type=OptimizationScopeType.DATE, date=date(2026, 7, 1)),
        shifts=[],
        requests=[
            shift_request(
                STAFF_ID,
                start_time=None,
                end_time=None,
                request_type="off",
            ),
            shift_request(STAFF_SECOND_ID, start_time=time(9), end_time=time(17)),
        ],
        staff_members=[staff_member(STAFF_ID), staff_member(STAFF_SECOND_ID)],
        positions=[position(POSITION_B_ID, "B"), position(POSITION_C_ID, "C")],
        skills=[skill(SKILL_B_ID, POSITION_B_ID), skill(SKILL_C_ID, POSITION_C_ID)],
        staff_skills=[
            staff_skill(SKILL_B_ID, STAFF_ID),
            staff_skill(SKILL_C_ID, STAFF_ID),
            staff_skill(SKILL_B_ID, STAFF_SECOND_ID),
            staff_skill(SKILL_C_ID, STAFF_SECOND_ID),
        ],
        task_types=[],
    )

    created_staff_ids = {
        change.command_payload["staff_member_id"]
        for change in changes
        if change.command_type == "CreateWorkShift"
    }
    assert str(STAFF_ID) not in created_staff_ids
    assert str(STAFF_SECOND_ID) in created_staff_ids


def test_request_based_generation_deletes_locked_shift_for_full_day_off_request() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    locked_shift = work_shift(start_time=time(10), end_time=time(13))
    locked_shift.is_locked = True

    changes = solver._build_request_schedule_generation_changes(
        scope=DateScope(type=OptimizationScopeType.DATE, date=date(2026, 7, 1)),
        shifts=[locked_shift],
        requests=[
            shift_request(
                STAFF_ID,
                start_time=None,
                end_time=None,
                request_type="off",
            ),
            shift_request(STAFF_SECOND_ID, start_time=time(9), end_time=time(17)),
        ],
        staff_members=[staff_member(STAFF_ID), staff_member(STAFF_SECOND_ID)],
        positions=[position(POSITION_B_ID, "B"), position(POSITION_C_ID, "C")],
        skills=[skill(SKILL_B_ID, POSITION_B_ID), skill(SKILL_C_ID, POSITION_C_ID)],
        staff_skills=[
            staff_skill(SKILL_B_ID, STAFF_ID),
            staff_skill(SKILL_C_ID, STAFF_ID),
            staff_skill(SKILL_B_ID, STAFF_SECOND_ID),
            staff_skill(SKILL_C_ID, STAFF_SECOND_ID),
        ],
        task_types=[],
    )

    assert any(
        change.command_type == "DeleteWorkShift" and change.target_id == SHIFT_ID
        for change in changes
    )


def test_request_based_generation_covers_b_and_c_with_two_staff() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]

    changes = solver._build_request_schedule_generation_changes(
        scope=DateScope(type=OptimizationScopeType.DATE, date=date(2026, 7, 1)),
        shifts=[],
        requests=[
            shift_request(STAFF_ID, start_time=time(9), end_time=time(11)),
            shift_request(STAFF_SECOND_ID, start_time=time(9), end_time=time(11)),
        ],
        staff_members=[staff_member(STAFF_ID), staff_member(STAFF_SECOND_ID)],
        positions=[position(POSITION_B_ID, "B"), position(POSITION_C_ID, "C")],
        skills=[skill(SKILL_B_ID, POSITION_B_ID), skill(SKILL_C_ID, POSITION_C_ID)],
        staff_skills=[
            staff_skill(SKILL_B_ID, STAFF_ID),
            staff_skill(SKILL_C_ID, STAFF_ID),
            staff_skill(SKILL_B_ID, STAFF_SECOND_ID),
            staff_skill(SKILL_C_ID, STAFF_SECOND_ID),
        ],
        task_types=[],
    )

    assert position_codes_for_window(changes, time(9), time(11)) == {"B", "C"}


def test_request_based_generation_covers_f_c_b_with_three_staff() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    third_staff_id = UUID("30000000-0000-0000-0000-000000000003")

    changes = solver._build_request_schedule_generation_changes(
        scope=DateScope(type=OptimizationScopeType.DATE, date=date(2026, 7, 1)),
        shifts=[],
        requests=[
            shift_request(STAFF_ID, start_time=time(9), end_time=time(12, 30)),
            shift_request(STAFF_SECOND_ID, start_time=time(9), end_time=time(12, 30)),
            shift_request(third_staff_id, start_time=time(9), end_time=time(12, 30)),
        ],
        staff_members=[
            staff_member(STAFF_ID),
            staff_member(STAFF_SECOND_ID),
            staff_member(third_staff_id),
        ],
        positions=[
            position(POSITION_F_ID, "F"),
            position(POSITION_C_ID, "C"),
            position(POSITION_B_ID, "B"),
        ],
        skills=[
            skill(SKILL_F_ID, POSITION_F_ID),
            skill(SKILL_C_ID, POSITION_C_ID),
            skill(SKILL_B_ID, POSITION_B_ID),
        ],
        staff_skills=[
            staff_skill(SKILL_F_ID, STAFF_ID),
            staff_skill(SKILL_C_ID, STAFF_ID),
            staff_skill(SKILL_B_ID, STAFF_ID),
            staff_skill(SKILL_F_ID, STAFF_SECOND_ID),
            staff_skill(SKILL_C_ID, STAFF_SECOND_ID),
            staff_skill(SKILL_B_ID, STAFF_SECOND_ID),
            staff_skill(SKILL_F_ID, third_staff_id),
            staff_skill(SKILL_C_ID, third_staff_id),
            staff_skill(SKILL_B_ID, third_staff_id),
        ],
        task_types=[],
    )

    assert active_position_codes_at(changes, time(9, 30)) == {"F", "C", "B"}
    assert active_position_codes_at(changes, time(11, 30)) == {"F", "C", "B"}


def test_request_based_generation_uses_b_c_f_s_with_four_staff() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    third_staff_id = UUID("30000000-0000-0000-0000-000000000003")
    fourth_staff_id = UUID("30000000-0000-0000-0000-000000000004")

    changes = solver._build_request_schedule_generation_changes(
        scope=DateScope(type=OptimizationScopeType.DATE, date=date(2026, 7, 1)),
        shifts=[],
        requests=[
            shift_request(STAFF_ID, start_time=time(9), end_time=time(13)),
            shift_request(STAFF_SECOND_ID, start_time=time(9), end_time=time(13)),
            shift_request(third_staff_id, start_time=time(9), end_time=time(13)),
            shift_request(fourth_staff_id, start_time=time(9), end_time=time(13)),
        ],
        staff_members=[
            staff_member(STAFF_ID),
            staff_member(STAFF_SECOND_ID),
            staff_member(third_staff_id),
            staff_member(fourth_staff_id),
        ],
        positions=[
            position(POSITION_B_ID, "B"),
            position(POSITION_C_ID, "C"),
            position(POSITION_F_ID, "F"),
            position(POSITION_S_ID, "S"),
        ],
        skills=[
            skill(SKILL_B_ID, POSITION_B_ID),
            skill(SKILL_C_ID, POSITION_C_ID),
            skill(SKILL_F_ID, POSITION_F_ID),
            skill(SKILL_S_ID, POSITION_S_ID),
        ],
        staff_skills=[
            staff_skill(skill_id, staff_id)
            for staff_id in [STAFF_ID, STAFF_SECOND_ID, third_staff_id, fourth_staff_id]
            for skill_id in [SKILL_B_ID, SKILL_C_ID, SKILL_F_ID, SKILL_S_ID]
        ],
        task_types=[],
    )

    assert position_code_counts_at(changes, time(9, 30)) == {
        "B": 1,
        "C": 1,
        "F": 1,
        "S": 1,
    }


def test_request_based_generation_uses_two_b_with_five_staff() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    staff_ids = [
        STAFF_ID,
        STAFF_SECOND_ID,
        UUID("30000000-0000-0000-0000-000000000003"),
        UUID("30000000-0000-0000-0000-000000000004"),
        UUID("30000000-0000-0000-0000-000000000005"),
    ]

    changes = solver._build_request_schedule_generation_changes(
        scope=DateScope(type=OptimizationScopeType.DATE, date=date(2026, 7, 1)),
        shifts=[],
        requests=[
            shift_request(staff_id, start_time=time(9), end_time=time(13))
            for staff_id in staff_ids
        ],
        staff_members=[staff_member(staff_id) for staff_id in staff_ids],
        positions=[
            position(POSITION_B_ID, "B"),
            position(POSITION_C_ID, "C"),
            position(POSITION_F_ID, "F"),
            position(POSITION_S_ID, "S"),
        ],
        skills=[
            skill(SKILL_B_ID, POSITION_B_ID),
            skill(SKILL_C_ID, POSITION_C_ID),
            skill(SKILL_F_ID, POSITION_F_ID),
            skill(SKILL_S_ID, POSITION_S_ID),
        ],
        staff_skills=[
            staff_skill(skill_id, staff_id)
            for staff_id in staff_ids
            for skill_id in [SKILL_B_ID, SKILL_C_ID, SKILL_F_ID, SKILL_S_ID]
        ],
        task_types=[],
    )

    assert position_code_counts_at(changes, time(9, 30)) == {
        "B": 2,
        "C": 1,
        "F": 1,
        "S": 1,
    }
    assert b_labels_at(changes, time(9, 30)) == {"ST", "SH"}


def test_interval_assignment_keeps_positions_across_short_adjacent_intervals() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    staff_ids = [
        STAFF_ID,
        STAFF_SECOND_ID,
        UUID("30000000-0000-0000-0000-000000000003"),
        UUID("30000000-0000-0000-0000-000000000004"),
    ]
    requests = [
        SimpleNamespace(staff_member_id=staff_id)
        for staff_id in staff_ids
    ]

    assignments = solver._assign_positions_across_intervals(
        [
            (time(9), time(10), requests),
            (time(10), time(11), requests),
        ],
        positions_by_code(),
        all_position_skills(),
        all_position_staff_skills(staff_ids),
    )

    first_assignment = assignments[(time(9), time(10))]
    assert Counter(first_assignment.values()) == Counter({"B": 1, "C": 1, "F": 1, "S": 1})
    assert assignments[(time(10), time(11))] == first_assignment


def test_interval_assignment_avoids_churn_for_very_short_intervals() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    staff_ids = [
        STAFF_ID,
        STAFF_SECOND_ID,
        UUID("30000000-0000-0000-0000-000000000003"),
        UUID("30000000-0000-0000-0000-000000000004"),
    ]
    requests = [SimpleNamespace(staff_member_id=staff_id) for staff_id in staff_ids]

    assignments = solver._assign_positions_across_intervals(
        [
            (time(9), time(10), requests),
            (time(10), time(10, 15), requests),
            (time(10, 15), time(11, 15), requests),
        ],
        positions_by_code(),
        all_position_skills(),
        all_position_staff_skills(staff_ids),
    )

    assert assignments[(time(10), time(10, 15))] == assignments[(time(9), time(10))]


def test_interval_assignment_handles_eleven_simultaneous_staff() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    staff_ids = [
        UUID(f"30000000-0000-0000-0000-{index:012d}")
        for index in range(1, 12)
    ]
    requests = [SimpleNamespace(staff_member_id=staff_id) for staff_id in staff_ids]

    assignments = solver._assign_positions_across_intervals(
        [
            (time(9), time(10), requests),
            (time(10), time(10, 30), requests),
            (time(10, 30), time(12), requests),
        ],
        positions_by_code(),
        all_position_skills(),
        all_position_staff_skills(staff_ids),
    )

    expected_counts = Counter({"B": 3, "C": 2, "F": 3, "S": 3})
    assert Counter(assignments[(time(9), time(10))].values()) == expected_counts
    assert Counter(assignments[(time(10), time(10, 30))].values()) == expected_counts
    assert Counter(assignments[(time(10, 30), time(12))].values()) == expected_counts


def test_exact_mix_candidates_are_bounded_for_eleven_simultaneous_staff() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    staff_ids = [
        UUID(f"30000000-0000-0000-0000-{index:012d}")
        for index in range(1, 12)
    ]
    active_work = [
        (staff_id, {"position_code": "B"})
        for staff_id in staff_ids
    ]

    candidates = solver._exact_mix_candidates_for_active_work(
        active_work,
        positions_by_code(),
        all_position_skills(),
        all_position_staff_skills(staff_ids),
    )

    expected_counts = Counter({"B": 3, "C": 2, "F": 3, "S": 3})
    assert len(candidates) == MAX_ASSIGNMENT_CANDIDATES
    assert all(Counter(candidate.values()) == expected_counts for candidate in candidates)


def test_interval_assignment_rotates_long_cashier_without_short_churn() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    staff_ids = [
        STAFF_ID,
        STAFF_SECOND_ID,
        UUID("30000000-0000-0000-0000-000000000003"),
        UUID("30000000-0000-0000-0000-000000000004"),
    ]
    requests = [SimpleNamespace(staff_member_id=staff_id) for staff_id in staff_ids]

    assignments = solver._assign_positions_across_intervals(
        [
            (time(9), time(10, 30), requests),
            (time(10, 30), time(12), requests),
            (time(12), time(13, 30), requests),
            (time(13, 30), time(15), requests),
        ],
        positions_by_code(),
        all_position_skills(),
        all_position_staff_skills(staff_ids),
    )

    cashier_by_interval = [
        next(
            staff_id
            for staff_id, position_code in assignments[interval].items()
            if position_code == "C"
        )
        for interval in [
            (time(9), time(10, 30)),
            (time(10, 30), time(12)),
            (time(12), time(13, 30)),
            (time(13, 30), time(15)),
        ]
    ]

    assert len(set(cashier_by_interval)) > 1


def test_request_based_deposit_keeps_b_and_c_covered() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    staff_ids = [
        STAFF_ID,
        STAFF_SECOND_ID,
        UUID("30000000-0000-0000-0000-000000000003"),
    ]

    changes = solver._build_request_schedule_generation_changes(
        scope=DateScope(type=OptimizationScopeType.DATE, date=date(2026, 7, 1)),
        shifts=[],
        requests=[
            shift_request(staff_id, start_time=time(9), end_time=time(13))
            for staff_id in staff_ids
        ],
        staff_members=[staff_member(staff_id) for staff_id in staff_ids],
        positions=[
            position(POSITION_B_ID, "B"),
            position(POSITION_C_ID, "C"),
            position(POSITION_F_ID, "F"),
            position(POSITION_S_ID, "S"),
        ],
        skills=[
            skill(SKILL_B_ID, POSITION_B_ID),
            skill(SKILL_C_ID, POSITION_C_ID),
            skill(SKILL_F_ID, POSITION_F_ID),
            skill(SKILL_S_ID, POSITION_S_ID),
            task_skill(),
        ],
        staff_skills=[
            staff_skill(skill_id, staff_id)
            for staff_id in staff_ids
            for skill_id in [SKILL_B_ID, SKILL_C_ID, SKILL_F_ID, SKILL_S_ID, SKILL_M_ID]
        ],
        task_types=[task_type_m()],
    )

    active_codes_during_deposit = active_position_codes_at(changes, time(10, 15))

    assert {"B", "C"}.issubset(active_codes_during_deposit)
    assert "F" not in active_codes_during_deposit
    assert task_segment_count_at(changes, time(10, 15), TASK_M_ID) == 1


def test_request_based_deposit_reserves_window_before_breaks() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    staff_ids = [
        STAFF_ID,
        STAFF_SECOND_ID,
        UUID("30000000-0000-0000-0000-000000000003"),
    ]
    position_skill_ids = [SKILL_B_ID, SKILL_C_ID, SKILL_F_ID, SKILL_S_ID]

    changes = solver._build_request_schedule_generation_changes(
        scope=DateScope(type=OptimizationScopeType.DATE, date=date(2026, 7, 1)),
        shifts=[],
        requests=[
            shift_request(staff_id, start_time=time(8), end_time=time(13))
            for staff_id in staff_ids
        ],
        staff_members=[staff_member(staff_id) for staff_id in staff_ids],
        positions=[
            position(POSITION_B_ID, "B"),
            position(POSITION_C_ID, "C"),
            position(POSITION_F_ID, "F"),
            position(POSITION_S_ID, "S"),
        ],
        skills=[
            skill(SKILL_B_ID, POSITION_B_ID),
            skill(SKILL_C_ID, POSITION_C_ID),
            skill(SKILL_F_ID, POSITION_F_ID),
            skill(SKILL_S_ID, POSITION_S_ID),
            task_skill(),
        ],
        staff_skills=[
            *[
                staff_skill(skill_id, staff_id)
                for staff_id in staff_ids
                for skill_id in position_skill_ids
            ],
            staff_skill(SKILL_M_ID, STAFF_ID),
        ],
        task_types=[task_type_m()],
    )

    assert task_segment_count_at(changes, time(10, 15), TASK_M_ID) == 1
    assert {"B", "C"}.issubset(active_position_codes_at(changes, time(10, 15)))


def test_short_staffed_shift_places_break_when_third_staff_arrives() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    third_staff_id = UUID("30000000-0000-0000-0000-000000000003")
    planned = {
        STAFF_ID: [planned_work("B", POSITION_B_ID, time(6, 45), time(11))],
        STAFF_SECOND_ID: [planned_work("C", POSITION_C_ID, time(6, 45), time(16))],
        third_staff_id: [planned_work("B", POSITION_B_ID, time(9), time(14))],
    }

    break_window = solver._choose_break_window(
        planned,
        SimpleNamespace(
            staff_member_id=STAFF_ID,
            start_time=time(6, 45),
            end_time=time(11),
        ),
        break_minutes=15,
        preferred_center=round((6 * 60 + 45 + 11 * 60) / 2),
        positions_by_code=positions_by_code(),
        skills=all_position_skills(),
        staff_skills=all_position_staff_skills(
            [STAFF_ID, STAFF_SECOND_ID, third_staff_id]
        ),
    )

    assert break_window == (time(9), time(9, 15))


def test_break_is_not_scheduled_when_it_would_remove_b_or_c_coverage() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    staff_ids = [
        STAFF_ID,
        STAFF_SECOND_ID,
        UUID("30000000-0000-0000-0000-000000000003"),
    ]

    changes = solver._build_request_schedule_generation_changes(
        scope=DateScope(type=OptimizationScopeType.DATE, date=date(2026, 7, 1)),
        shifts=[],
        requests=[
            shift_request(STAFF_ID, start_time=time(6, 45), end_time=time(15, 45)),
            shift_request(STAFF_SECOND_ID, start_time=time(6, 45), end_time=time(17)),
            shift_request(staff_ids[2], start_time=time(9), end_time=time(14)),
        ],
        staff_members=[staff_member(staff_id) for staff_id in staff_ids],
        positions=[
            position(POSITION_B_ID, "B"),
            position(POSITION_C_ID, "C"),
            position(POSITION_F_ID, "F"),
            position(POSITION_S_ID, "S"),
        ],
        skills=[
            skill(SKILL_B_ID, POSITION_B_ID),
            skill(SKILL_C_ID, POSITION_C_ID),
            skill(SKILL_F_ID, POSITION_F_ID),
            skill(SKILL_S_ID, POSITION_S_ID),
        ],
        staff_skills=[
            staff_skill(skill_id, staff_id)
            for staff_id in staff_ids
            for skill_id in [SKILL_B_ID, SKILL_C_ID, SKILL_F_ID, SKILL_S_ID]
        ],
        task_types=[],
    )

    for target_time in [time(7, 45), time(8), time(8, 45), time(9, 15)]:
        active_codes = active_position_codes_at(changes, target_time)
        if active_work_count_at(changes, target_time) >= 2:
            assert {"B", "C"}.issubset(active_codes)


def test_request_based_generation_staggers_breaks_and_keeps_b_c_covered() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    staff_ids = [
        STAFF_ID,
        STAFF_SECOND_ID,
        UUID("30000000-0000-0000-0000-000000000003"),
        UUID("30000000-0000-0000-0000-000000000004"),
    ]

    changes = solver._build_request_schedule_generation_changes(
        scope=DateScope(type=OptimizationScopeType.DATE, date=date(2026, 7, 1)),
        shifts=[],
        requests=[
            shift_request(staff_id, start_time=time(9), end_time=time(17))
            for staff_id in staff_ids
        ],
        staff_members=[staff_member(staff_id) for staff_id in staff_ids],
        positions=[
            position(POSITION_B_ID, "B"),
            position(POSITION_C_ID, "C"),
            position(POSITION_F_ID, "F"),
            position(POSITION_S_ID, "S"),
        ],
        skills=[
            skill(SKILL_B_ID, POSITION_B_ID),
            skill(SKILL_C_ID, POSITION_C_ID),
            skill(SKILL_F_ID, POSITION_F_ID),
            skill(SKILL_S_ID, POSITION_S_ID),
        ],
        staff_skills=[
            staff_skill(skill_id, staff_id)
            for staff_id in staff_ids
            for skill_id in [SKILL_B_ID, SKILL_C_ID, SKILL_F_ID, SKILL_S_ID]
        ],
        task_types=[],
    )

    break_windows = break_windows_from_changes(changes)
    assert len(break_windows) == 8
    assert max_simultaneous_windows(break_windows) <= 1
    assert all(
        time(11) <= start and end <= time(15)
        for start, end in break_windows
    )
    for start_hour in range(11, 15):
        assert {"B", "C"}.issubset(
            active_position_codes_at(changes, time(start_hour, 30))
        )


def test_request_based_generation_uses_break_rules_by_shift_length() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    short_staff_id = STAFF_ID
    middle_staff_id = STAFF_SECOND_ID
    long_staff_id = UUID("30000000-0000-0000-0000-000000000003")

    changes = solver._build_request_schedule_generation_changes(
        scope=DateScope(type=OptimizationScopeType.DATE, date=date(2026, 7, 1)),
        shifts=[],
        requests=[
            shift_request(short_staff_id, start_time=time(9), end_time=time(12, 30)),
            shift_request(middle_staff_id, start_time=time(9), end_time=time(14)),
            shift_request(long_staff_id, start_time=time(9), end_time=time(17)),
        ],
        staff_members=[
            staff_member(short_staff_id),
            staff_member(middle_staff_id),
            staff_member(long_staff_id),
        ],
        positions=[position(POSITION_C_ID, "C")],
        skills=[skill(SKILL_C_ID, POSITION_C_ID)],
        staff_skills=[
            staff_skill(SKILL_C_ID, short_staff_id),
            staff_skill(SKILL_C_ID, middle_staff_id),
            staff_skill(SKILL_C_ID, long_staff_id),
        ],
        task_types=[],
    )

    break_windows_by_staff = break_windows_by_staff_from_changes(changes)

    assert break_windows_by_staff.get(str(short_staff_id), []) == []
    assert break_durations(break_windows_by_staff[str(middle_staff_id)]) == [15]
    assert all(
        time(11) <= start and end <= time(12)
        for start, end in break_windows_by_staff[str(middle_staff_id)]
    )
    assert break_durations(break_windows_by_staff[str(long_staff_id)]) == [15, 30]
    assert all(
        time(11) <= start and end <= time(15)
        for start, end in break_windows_by_staff[str(long_staff_id)]
    )
    assert staff_breaks_are_spaced(break_windows_by_staff[str(long_staff_id)])


def test_request_based_generation_skips_break_when_only_edge_slots_exist() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]

    changes = solver._build_request_schedule_generation_changes(
        scope=DateScope(type=OptimizationScopeType.DATE, date=date(2026, 7, 1)),
        shifts=[],
        requests=[
            shift_request(STAFF_ID, start_time=time(9), end_time=time(13)),
        ],
        staff_members=[staff_member(STAFF_ID)],
        positions=[position(POSITION_C_ID, "C")],
        skills=[skill(SKILL_C_ID, POSITION_C_ID)],
        staff_skills=[staff_skill(SKILL_C_ID, STAFF_ID)],
        task_types=[],
    )

    assert break_windows_from_changes(changes) == []


def test_request_based_generation_rebuilds_exact_mix_after_breaks() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    staff_ids = [
        STAFF_ID,
        STAFF_SECOND_ID,
        UUID("30000000-0000-0000-0000-000000000003"),
        UUID("30000000-0000-0000-0000-000000000004"),
        UUID("30000000-0000-0000-0000-000000000005"),
    ]

    changes = solver._build_request_schedule_generation_changes(
        scope=DateScope(type=OptimizationScopeType.DATE, date=date(2026, 7, 1)),
        shifts=[],
        requests=[
            shift_request(staff_ids[0], start_time=time(6, 45), end_time=time(15, 45)),
            shift_request(staff_ids[1], start_time=time(6, 45), end_time=time(13, 45)),
            shift_request(staff_ids[2], start_time=time(9), end_time=time(14)),
            shift_request(staff_ids[3], start_time=time(9), end_time=time(15)),
            shift_request(staff_ids[4], start_time=time(12, 30), end_time=time(21, 30)),
        ],
        staff_members=[staff_member(staff_id) for staff_id in staff_ids],
        positions=[
            position(POSITION_B_ID, "B"),
            position(POSITION_C_ID, "C"),
            position(POSITION_F_ID, "F"),
            position(POSITION_S_ID, "S"),
        ],
        skills=[
            skill(SKILL_B_ID, POSITION_B_ID),
            skill(SKILL_C_ID, POSITION_C_ID),
            skill(SKILL_F_ID, POSITION_F_ID),
            skill(SKILL_S_ID, POSITION_S_ID),
        ],
        staff_skills=[
            staff_skill(skill_id, staff_id)
            for staff_id in staff_ids
            for skill_id in [SKILL_B_ID, SKILL_C_ID, SKILL_F_ID, SKILL_S_ID]
        ],
        task_types=[],
    )

    for target_time in [
        time(7, 30),
        time(9, 30),
        time(10, 15),
        time(12, 45),
        time(14, 30),
    ]:
        assert_exact_position_mix_at(changes, target_time)

    for change in changes:
        if change.command_type != "CreateWorkShift":
            continue
        previous_segment = None
        for segment in change.command_payload["segments"]:
            if previous_segment is not None:
                assert not (
                    previous_segment["segment_type"] == "WORK"
                    and segment["segment_type"] == "WORK"
                    and previous_segment["position_id"] == segment["position_id"]
                    and previous_segment.get("label") == segment.get("label")
                    and previous_segment["end_time"] == segment["start_time"]
                    and segment_payload_minutes(
                        previous_segment["start_time"],
                        segment["end_time"],
                    )
                    <= 150
                )
            previous_segment = segment


def test_request_based_generation_rotates_positions_every_two_hours() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    third_staff_id = UUID("30000000-0000-0000-0000-000000000003")

    changes = solver._build_request_schedule_generation_changes(
        scope=DateScope(type=OptimizationScopeType.DATE, date=date(2026, 7, 1)),
        shifts=[],
        requests=[
            shift_request(STAFF_ID, start_time=time(9), end_time=time(13)),
            shift_request(STAFF_SECOND_ID, start_time=time(9), end_time=time(13)),
            shift_request(third_staff_id, start_time=time(9), end_time=time(13)),
        ],
        staff_members=[
            staff_member(STAFF_ID),
            staff_member(STAFF_SECOND_ID),
            staff_member(third_staff_id),
        ],
        positions=[
            position(POSITION_F_ID, "F"),
            position(POSITION_C_ID, "C"),
            position(POSITION_B_ID, "B"),
        ],
        skills=[
            skill(SKILL_F_ID, POSITION_F_ID),
            skill(SKILL_C_ID, POSITION_C_ID),
            skill(SKILL_B_ID, POSITION_B_ID),
        ],
        staff_skills=[
            staff_skill(SKILL_F_ID, STAFF_ID),
            staff_skill(SKILL_C_ID, STAFF_ID),
            staff_skill(SKILL_B_ID, STAFF_ID),
            staff_skill(SKILL_F_ID, STAFF_SECOND_ID),
            staff_skill(SKILL_C_ID, STAFF_SECOND_ID),
            staff_skill(SKILL_B_ID, STAFF_SECOND_ID),
            staff_skill(SKILL_F_ID, third_staff_id),
            staff_skill(SKILL_C_ID, third_staff_id),
            staff_skill(SKILL_B_ID, third_staff_id),
        ],
        task_types=[],
    )

    create_change = next(
        change
        for change in changes
        if change.command_type == "CreateWorkShift"
        and change.command_payload["staff_member_id"] == str(STAFF_ID)
    )
    work_segments = [
        segment
        for segment in create_change.command_payload["segments"]
        if segment["segment_type"] == "WORK"
    ]
    assert len(work_segments) == 2
    assert work_segments[0]["position_id"] != work_segments[1]["position_id"]


def test_request_based_generation_keeps_exact_position_mix_from_early_start() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    third_staff_id = UUID("30000000-0000-0000-0000-000000000003")
    fourth_staff_id = UUID("30000000-0000-0000-0000-000000000004")
    staff_ids = [STAFF_ID, STAFF_SECOND_ID, third_staff_id, fourth_staff_id]

    changes = solver._build_request_schedule_generation_changes(
        scope=DateScope(type=OptimizationScopeType.DATE, date=date(2026, 7, 1)),
        shifts=[],
        requests=[
            shift_request(STAFF_ID, start_time=time(6, 45), end_time=time(16)),
            shift_request(STAFF_SECOND_ID, start_time=time(6, 45), end_time=time(14)),
            shift_request(third_staff_id, start_time=time(8), end_time=time(17)),
            shift_request(fourth_staff_id, start_time=time(12), end_time=time(18)),
        ],
        staff_members=[staff_member(staff_id) for staff_id in staff_ids],
        positions=[
            position(POSITION_B_ID, "B"),
            position(POSITION_C_ID, "C"),
            position(POSITION_F_ID, "F"),
            position(POSITION_S_ID, "S"),
        ],
        skills=[
            skill(SKILL_B_ID, POSITION_B_ID),
            skill(SKILL_C_ID, POSITION_C_ID),
            skill(SKILL_F_ID, POSITION_F_ID),
            skill(SKILL_S_ID, POSITION_S_ID),
        ],
        staff_skills=[
            staff_skill(skill_id, staff_id)
            for staff_id in staff_ids
            for skill_id in [SKILL_B_ID, SKILL_C_ID, SKILL_F_ID, SKILL_S_ID]
        ],
        task_types=[],
    )

    for target_time in [
        time(6, 45),
        time(8),
        time(9),
        time(10),
        time(12),
        time(13),
        time(14),
        time(15, 30),
        time(16, 30),
    ]:
        assert_exact_position_mix_at(changes, target_time)

    long_support_segments = [
        segment
        for change in changes
        if change.command_type == "CreateWorkShift"
        for segment in change.command_payload["segments"]
        if segment["segment_type"] == "WORK"
        and segment["position_id"] == str(POSITION_S_ID)
        and window_minutes(
            (
                time.fromisoformat(segment["start_time"]),
                time.fromisoformat(segment["end_time"]),
            )
        )
        > 120
    ]
    assert long_support_segments == []


def test_request_based_generation_uses_two_b_lanes_only_with_five_people() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    third_staff_id = UUID("30000000-0000-0000-0000-000000000003")
    fourth_staff_id = UUID("30000000-0000-0000-0000-000000000004")
    fifth_staff_id = UUID("30000000-0000-0000-0000-000000000005")
    staff_ids = [STAFF_ID, STAFF_SECOND_ID, third_staff_id, fourth_staff_id, fifth_staff_id]

    changes = solver._build_request_schedule_generation_changes(
        scope=DateScope(type=OptimizationScopeType.DATE, date=date(2026, 7, 1)),
        shifts=[],
        requests=[
            shift_request(staff_id, start_time=time(9), end_time=time(17))
            for staff_id in staff_ids
        ],
        staff_members=[staff_member(staff_id) for staff_id in staff_ids],
        positions=[
            position(POSITION_B_ID, "B"),
            position(POSITION_C_ID, "C"),
            position(POSITION_F_ID, "F"),
            position(POSITION_S_ID, "S"),
        ],
        skills=[
            skill(SKILL_B_ID, POSITION_B_ID),
            skill(SKILL_C_ID, POSITION_C_ID),
            skill(SKILL_F_ID, POSITION_F_ID),
            skill(SKILL_S_ID, POSITION_S_ID),
        ],
        staff_skills=[
            staff_skill(skill_id, staff_id)
            for staff_id in staff_ids
            for skill_id in [SKILL_B_ID, SKILL_C_ID, SKILL_F_ID, SKILL_S_ID]
        ],
        task_types=[],
    )

    assert position_code_counts_at(changes, time(10)) == {
        "B": 2,
        "C": 1,
        "F": 1,
        "S": 1,
    }
    assert b_labels_at(changes, time(10)) == {"ST", "SH"}


def test_request_based_generation_avoids_short_work_position_fragments() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    third_staff_id = UUID("30000000-0000-0000-0000-000000000003")
    fourth_staff_id = UUID("30000000-0000-0000-0000-000000000004")
    staff_ids = [STAFF_ID, STAFF_SECOND_ID, third_staff_id, fourth_staff_id]

    changes = solver._build_request_schedule_generation_changes(
        scope=DateScope(type=OptimizationScopeType.DATE, date=date(2026, 7, 1)),
        shifts=[],
        requests=[
            shift_request(staff_id, start_time=time(9), end_time=time(17, 15))
            for staff_id in staff_ids
        ],
        staff_members=[staff_member(staff_id) for staff_id in staff_ids],
        positions=[
            position(POSITION_B_ID, "B"),
            position(POSITION_C_ID, "C"),
            position(POSITION_F_ID, "F"),
            position(POSITION_S_ID, "S"),
        ],
        skills=[
            skill(SKILL_B_ID, POSITION_B_ID),
            skill(SKILL_C_ID, POSITION_C_ID),
            skill(SKILL_F_ID, POSITION_F_ID),
            skill(SKILL_S_ID, POSITION_S_ID),
        ],
        staff_skills=[
            staff_skill(skill_id, staff_id)
            for staff_id in staff_ids
            for skill_id in [SKILL_B_ID, SKILL_C_ID, SKILL_F_ID, SKILL_S_ID]
        ],
        task_types=[],
    )

    all_segments = [
        segment
        for change in changes
        if change.command_type == "CreateWorkShift"
        for segment in change.command_payload["segments"]
    ]
    short_work_segments = [
        (change.command_payload["segments"], all_segments, segment)
        for change in changes
        if change.command_type == "CreateWorkShift"
        for segment in change.command_payload["segments"]
        if segment["segment_type"] == "WORK"
        and window_minutes(
            (
                time.fromisoformat(segment["start_time"]),
                time.fromisoformat(segment["end_time"]),
            )
        )
        < 60
    ]

    assert all(
        work_segment_touches_break(own_segments, segment)
        or work_segment_overlaps_break(all_segments, segment)
        for own_segments, all_segments, segment in short_work_segments
    )


def test_short_work_fragments_are_absorbed_into_adjacent_positions() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    segments = [
        planned_work("B", POSITION_B_ID, time(9), time(10)),
        planned_work("S", POSITION_S_ID, time(10), time(10, 15)),
        planned_work("B", POSITION_B_ID, time(10, 15), time(11)),
    ]

    solver._smooth_short_work_fragments(segments)
    solver._merge_adjacent_planned_segments(segments)

    assert segments == [
        planned_work("B", POSITION_B_ID, time(9), time(11)),
    ]


def test_adjacent_same_position_segments_do_not_merge_past_two_and_half_hours() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    segments = [
        planned_work("B", POSITION_B_ID, time(18), time(18, 45)),
        planned_work("B", POSITION_B_ID, time(18, 45), time(20, 45)),
        planned_work("C", POSITION_C_ID, time(20, 45), time(21, 30)),
    ]

    solver._merge_adjacent_planned_segments(segments)

    assert segments == [
        planned_work("B", POSITION_B_ID, time(18), time(18, 45)),
        planned_work("B", POSITION_B_ID, time(18, 45), time(20, 45)),
        planned_work("C", POSITION_C_ID, time(20, 45), time(21, 30)),
    ]


def test_coverage_repair_changes_surplus_c_to_missing_b() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    third_staff_id = UUID("30000000-0000-0000-0000-000000000003")
    planned = {
        STAFF_ID: [planned_work("C", POSITION_C_ID, time(9), time(11))],
        STAFF_SECOND_ID: [planned_work("C", POSITION_C_ID, time(9), time(11))],
        third_staff_id: [planned_work("F", POSITION_F_ID, time(9), time(11))],
    }

    solver._ensure_break_coverage_positions(
        planned,
        positions_by_code(),
        all_position_skills(),
        all_position_staff_skills([STAFF_ID, STAFF_SECOND_ID, third_staff_id]),
    )

    assert planned_position_code_counts_at(planned, time(9, 45)) == {
        "B": 1,
        "C": 1,
        "F": 1,
    }


def test_exact_mix_rebuild_changes_duplicate_c_to_bc() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    planned = {
        STAFF_ID: [planned_work("C", POSITION_C_ID, time(10), time(12))],
        STAFF_SECOND_ID: [planned_work("C", POSITION_C_ID, time(10), time(12))],
    }

    solver._rebuild_work_positions_by_exact_mix(
        planned,
        positions_by_code(),
        all_position_skills(),
        all_position_staff_skills([STAFF_ID, STAFF_SECOND_ID]),
    )

    assert planned_position_code_counts_at(planned, time(10, 30)) == {
        "B": 1,
        "C": 1,
    }


def test_exact_mix_rebuild_keeps_c_covered_around_breaks() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    third_staff_id = UUID("30000000-0000-0000-0000-000000000003")
    planned = {
        STAFF_ID: [
            planned_work("C", POSITION_C_ID, time(10), time(12, 30)),
            planned_break(time(12, 30), time(12, 45)),
            planned_work("C", POSITION_C_ID, time(12, 45), time(15)),
        ],
        STAFF_SECOND_ID: [planned_work("B", POSITION_B_ID, time(10), time(15))],
        third_staff_id: [planned_work("F", POSITION_F_ID, time(10), time(15))],
    }

    solver._rebuild_work_positions_by_exact_mix(
        planned,
        positions_by_code(),
        all_position_skills(),
        all_position_staff_skills([STAFF_ID, STAFF_SECOND_ID, third_staff_id]),
    )

    assert planned_position_code_counts_at(planned, time(12, 35)) == {
        "B": 1,
        "C": 1,
    }
    assert planned_position_code_counts_at(planned, time(12, 50)) == {
        "B": 1,
        "C": 1,
        "F": 1,
    }


def test_merge_adjacent_planned_segments_keeps_short_same_position_together() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    segments = [
        planned_work("S", POSITION_S_ID, time(13), time(13, 15)),
        planned_work("S", POSITION_S_ID, time(13, 15), time(14)),
    ]

    solver._merge_adjacent_planned_segments(segments)

    assert segments == [planned_work("S", POSITION_S_ID, time(13), time(14))]


def test_merge_adjacent_planned_segments_does_not_create_overlong_position_block() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    segments = [
        planned_work("C", POSITION_C_ID, time(9), time(11)),
        planned_work("C", POSITION_C_ID, time(11), time(12)),
    ]

    solver._merge_adjacent_planned_segments(segments)

    assert segments == [
        planned_work("C", POSITION_C_ID, time(9), time(11)),
        planned_work("C", POSITION_C_ID, time(11), time(12)),
    ]


def test_coverage_repair_changes_surplus_b_to_missing_c() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    planned = {
        STAFF_ID: [planned_work("B", POSITION_B_ID, time(6, 45), time(9))],
        STAFF_SECOND_ID: [planned_work("B", POSITION_B_ID, time(6, 45), time(9))],
    }

    solver._ensure_break_coverage_positions(
        planned,
        positions_by_code(),
        all_position_skills(),
        all_position_staff_skills([STAFF_ID, STAFF_SECOND_ID]),
    )

    assert planned_position_code_counts_at(planned, time(7, 0)) == {
        "B": 1,
        "C": 1,
    }


def test_coverage_repair_reserves_scarce_cashier_skill() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    planned = {
        STAFF_ID: [planned_work("B", POSITION_B_ID, time(6, 45), time(9))],
        STAFF_SECOND_ID: [planned_work("B", POSITION_B_ID, time(6, 45), time(9))],
    }

    solver._ensure_break_coverage_positions(
        planned,
        positions_by_code(),
        all_position_skills(),
        [
            staff_skill(SKILL_B_ID, STAFF_ID),
            staff_skill(SKILL_B_ID, STAFF_SECOND_ID),
            staff_skill(SKILL_C_ID, STAFF_SECOND_ID),
        ],
    )

    assert planned_position_code_counts_at(planned, time(7, 0)) == {
        "B": 1,
        "C": 1,
    }


def test_coverage_repair_prefers_f_over_s_when_three_people_work() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    third_staff_id = UUID("30000000-0000-0000-0000-000000000003")
    planned = {
        STAFF_ID: [planned_work("B", POSITION_B_ID, time(12), time(14))],
        STAFF_SECOND_ID: [planned_work("C", POSITION_C_ID, time(12), time(14))],
        third_staff_id: [planned_work("S", POSITION_S_ID, time(12), time(14))],
    }

    solver._ensure_break_coverage_positions(
        planned,
        positions_by_code(),
        all_position_skills(),
        all_position_staff_skills([STAFF_ID, STAFF_SECOND_ID, third_staff_id]),
    )

    assert planned_position_code_counts_at(planned, time(12, 15)) == {
        "B": 1,
        "C": 1,
        "F": 1,
    }


def test_b_lane_label_is_not_kept_when_segment_has_only_one_b_later() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    third_staff_id = UUID("30000000-0000-0000-0000-000000000003")
    fourth_staff_id = UUID("30000000-0000-0000-0000-000000000004")
    fifth_staff_id = UUID("30000000-0000-0000-0000-000000000005")
    planned = {
        STAFF_ID: [planned_work("B", POSITION_B_ID, time(9), time(12))],
        STAFF_SECOND_ID: [planned_work("B", POSITION_B_ID, time(9), time(10))],
        third_staff_id: [planned_work("C", POSITION_C_ID, time(9), time(12))],
        fourth_staff_id: [planned_work("F", POSITION_F_ID, time(9), time(12))],
        fifth_staff_id: [planned_work("S", POSITION_S_ID, time(9), time(12))],
    }

    solver._normalize_b_lane_labels(planned)

    staff_labels = [
        (segment["start_time"], segment["end_time"], segment["label"])
        for segment in planned[STAFF_ID]
    ]
    assert staff_labels == [
        (time(9), time(10), "ST"),
        (time(10), time(12), None),
    ]
    assert planned[STAFF_SECOND_ID][0]["label"] is not None


def test_coverage_repair_limits_f_to_one_when_s_is_needed() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    third_staff_id = UUID("30000000-0000-0000-0000-000000000003")
    fourth_staff_id = UUID("30000000-0000-0000-0000-000000000004")
    planned = {
        STAFF_ID: [planned_work("B", POSITION_B_ID, time(13), time(15))],
        STAFF_SECOND_ID: [planned_work("C", POSITION_C_ID, time(13), time(15))],
        third_staff_id: [planned_work("F", POSITION_F_ID, time(13), time(15))],
        fourth_staff_id: [planned_work("F", POSITION_F_ID, time(13), time(15))],
    }

    solver._ensure_break_coverage_positions(
        planned,
        positions_by_code(),
        all_position_skills(),
        all_position_staff_skills([STAFF_ID, STAFF_SECOND_ID, third_staff_id, fourth_staff_id]),
    )

    assert planned_position_code_counts_at(planned, time(13, 30)) == {
        "B": 1,
        "C": 1,
        "F": 1,
        "S": 1,
    }


def test_coverage_repair_restores_c_when_deposit_removes_cashier() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    third_staff_id = UUID("30000000-0000-0000-0000-000000000003")
    planned = {
        STAFF_ID: [
            {
                "start_time": time(10),
                "end_time": time(10, 30),
                "segment_type": "TASK",
                "position_code": None,
                "position_id": None,
                "task_type_id": TASK_M_ID,
                "label": "M",
            }
        ],
        STAFF_SECOND_ID: [planned_work("B", POSITION_B_ID, time(10), time(10, 30))],
        third_staff_id: [planned_work("F", POSITION_F_ID, time(10), time(10, 30))],
    }

    solver._ensure_break_coverage_positions(
        planned,
        positions_by_code(),
        all_position_skills(),
        all_position_staff_skills([STAFF_ID, STAFF_SECOND_ID, third_staff_id]),
    )

    assert planned_position_code_counts_at(planned, time(10, 15)) == {
        "B": 1,
        "C": 1,
    }


def test_coverage_repair_does_not_allow_two_b_when_four_people_work() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    third_staff_id = UUID("30000000-0000-0000-0000-000000000003")
    fourth_staff_id = UUID("30000000-0000-0000-0000-000000000004")
    planned = {
        STAFF_ID: [planned_work("B", POSITION_B_ID, time(14), time(15))],
        STAFF_SECOND_ID: [planned_work("B", POSITION_B_ID, time(14), time(15))],
        third_staff_id: [planned_work("C", POSITION_C_ID, time(14), time(15))],
        fourth_staff_id: [planned_work("F", POSITION_F_ID, time(14), time(15))],
    }

    solver._ensure_break_coverage_positions(
        planned,
        positions_by_code(),
        all_position_skills(),
        all_position_staff_skills([STAFF_ID, STAFF_SECOND_ID, third_staff_id, fourth_staff_id]),
    )

    assert planned_position_code_counts_at(planned, time(14, 15)) == {
        "B": 1,
        "C": 1,
        "F": 1,
        "S": 1,
    }


def test_coverage_repair_does_not_allow_two_c_when_b_is_missing() -> None:
    solver = ORToolsSolver(session=None)  # type: ignore[arg-type]
    third_staff_id = UUID("30000000-0000-0000-0000-000000000003")
    planned = {
        STAFF_ID: [planned_work("C", POSITION_C_ID, time(17), time(18))],
        STAFF_SECOND_ID: [planned_work("C", POSITION_C_ID, time(17), time(18))],
        third_staff_id: [planned_work("F", POSITION_F_ID, time(17), time(18))],
    }

    solver._ensure_break_coverage_positions(
        planned,
        positions_by_code(),
        all_position_skills(),
        all_position_staff_skills([STAFF_ID, STAFF_SECOND_ID, third_staff_id]),
    )

    assert planned_position_code_counts_at(planned, time(17, 30)) == {
        "B": 1,
        "C": 1,
        "F": 1,
    }


def work_shift(start_time: time = time(9), end_time: time = time(15)) -> SimpleNamespace:
    return SimpleNamespace(
        id=SHIFT_ID,
        staff_member_id=STAFF_ID,
        work_date=date(2026, 7, 1),
        start_time=start_time,
        end_time=end_time,
        is_locked=False,
    )


def work_segment(
    *,
    position_id: UUID,
    start_time: time = time(9),
    end_time: time = time(10),
    is_locked: bool = False,
    label: Optional[str] = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=SEGMENT_ID,
        work_shift_id=SHIFT_ID,
        segment_date=date(2026, 7, 1),
        start_time=start_time,
        end_time=end_time,
        segment_type="WORK",
        position_id=position_id,
        task_type_id=None,
        label=label,
        is_locked=is_locked,
    )


def work_segment_for_shift(
    work_shift_id: UUID,
    position_id: UUID,
    *,
    start_time: time,
    end_time: time,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=UUID(int=time_to_int(start_time) + time_to_int(end_time)),
        work_shift_id=work_shift_id,
        segment_date=date(2026, 7, 1),
        start_time=start_time,
        end_time=end_time,
        segment_type="WORK",
        position_id=position_id,
        task_type_id=None,
        label=None,
        is_locked=False,
    )


def time_to_int(value: time) -> int:
    return value.hour * 100 + value.minute


def segment_payload_minutes(start_value: str, end_value: str) -> int:
    start_time = time.fromisoformat(start_value)
    end_time = time.fromisoformat(end_value)
    return (end_time.hour * 60 + end_time.minute) - (start_time.hour * 60 + start_time.minute)


def position(position_id: UUID, code: str = "C") -> SimpleNamespace:
    return SimpleNamespace(id=position_id, code=code)


def positions_by_code() -> dict[str, SimpleNamespace]:
    return {
        "B": position(POSITION_B_ID, "B"),
        "C": position(POSITION_C_ID, "C"),
        "F": position(POSITION_F_ID, "F"),
        "S": position(POSITION_S_ID, "S"),
    }


def staff_member(staff_member_id: UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=staff_member_id,
        display_name=str(staff_member_id)[:8],
        employee_number=str(staff_member_id)[:3],
        is_active=True,
    )


def shift_request(
    staff_member_id: UUID,
    *,
    start_time: Optional[time],
    end_time: Optional[time],
    request_type: str = "available",
) -> SimpleNamespace:
    return SimpleNamespace(
        staff_member_id=staff_member_id,
        request_date=date(2026, 7, 1),
        start_time=start_time,
        end_time=end_time,
        request_type=request_type,
    )


def planned_work(position_code: str, position_id: UUID, start_time: time, end_time: time) -> dict:
    return {
        "start_time": start_time,
        "end_time": end_time,
        "segment_type": "WORK",
        "position_code": position_code,
        "position_id": position_id,
        "task_type_id": None,
        "label": None,
    }


def planned_break(start_time: time, end_time: time) -> dict:
    return {
        "start_time": start_time,
        "end_time": end_time,
        "segment_type": "BREAK",
        "position_code": None,
        "position_id": None,
        "task_type_id": None,
        "label": None,
    }


def all_position_skills() -> list[SimpleNamespace]:
    return [
        skill(SKILL_B_ID, POSITION_B_ID, code="B"),
        skill(SKILL_C_ID, POSITION_C_ID, code="C"),
        skill(SKILL_F_ID, POSITION_F_ID, code="F"),
        skill(SKILL_S_ID, POSITION_S_ID, code="S"),
    ]


def all_position_staff_skills(staff_ids: list[UUID]) -> list[SimpleNamespace]:
    return [
        staff_skill(skill_id, staff_id)
        for staff_id in staff_ids
        for skill_id in [SKILL_B_ID, SKILL_C_ID, SKILL_F_ID, SKILL_S_ID]
    ]


def planned_position_code_counts_at(
    planned: dict[UUID, list[dict]],
    target_time: time,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for segments in planned.values():
        for segment in segments:
            if segment["segment_type"] != "WORK":
                continue
            if segment["start_time"] <= target_time < segment["end_time"]:
                code = segment["position_code"]
                counts[code] = counts.get(code, 0) + 1
    return counts


def position_codes_for_window(changes, start_time: time, end_time: time) -> set[str]:
    position_code_by_id = {
        str(POSITION_B_ID): "B",
        str(POSITION_C_ID): "C",
        str(POSITION_F_ID): "F",
        str(POSITION_S_ID): "S",
    }
    codes = set()
    for change in changes:
        if change.command_type != "CreateWorkShift":
            continue
        for segment in change.command_payload["segments"]:
            if segment["segment_type"] != "WORK":
                continue
            if segment_covers_window(segment, start_time, end_time):
                codes.add(position_code_by_id[segment["position_id"]])
    return codes


def position_code_counts_for_window(changes, start_time: time, end_time: time) -> dict[str, int]:
    position_code_by_id = {
        str(POSITION_B_ID): "B",
        str(POSITION_C_ID): "C",
        str(POSITION_F_ID): "F",
        str(POSITION_S_ID): "S",
    }
    counts: dict[str, int] = {}
    for change in changes:
        if change.command_type != "CreateWorkShift":
            continue
        for segment in change.command_payload["segments"]:
            if segment["segment_type"] != "WORK":
                continue
            if segment_covers_window(segment, start_time, end_time):
                code = position_code_by_id[segment["position_id"]]
                counts[code] = counts.get(code, 0) + 1
    return counts


def position_code_counts_at(changes, target_time: time) -> dict[str, int]:
    position_code_by_id = {
        str(POSITION_B_ID): "B",
        str(POSITION_C_ID): "C",
        str(POSITION_F_ID): "F",
        str(POSITION_S_ID): "S",
    }
    counts: dict[str, int] = {}
    for change in changes:
        if change.command_type != "CreateWorkShift":
            continue
        for segment in change.command_payload["segments"]:
            if segment["segment_type"] != "WORK":
                continue
            if (
                time.fromisoformat(segment["start_time"])
                <= target_time
                < time.fromisoformat(segment["end_time"])
            ):
                code = position_code_by_id[segment["position_id"]]
                counts[code] = counts.get(code, 0) + 1
    return counts


def assert_exact_position_mix_at(changes, target_time: time) -> None:
    active_count = active_work_count_at(changes, target_time)
    counts = position_code_counts_at(changes, target_time)
    if active_count < 2:
        return
    if active_count == 2:
        assert counts == {"B": 1, "C": 1}
    elif active_count == 3:
        assert counts == {"B": 1, "C": 1, "F": 1}
    elif active_count == 4:
        assert counts == {"B": 1, "C": 1, "F": 1, "S": 1}
    elif active_count == 5:
        assert counts == {"B": 2, "C": 1, "F": 1, "S": 1}


def b_labels_at(changes, target_time: time) -> set[str]:
    labels = set()
    for change in changes:
        if change.command_type != "CreateWorkShift":
            continue
        for segment in change.command_payload["segments"]:
            if segment["segment_type"] != "WORK":
                continue
            if segment.get("position_id") != str(POSITION_B_ID):
                continue
            if (
                time.fromisoformat(segment["start_time"])
                <= target_time
                < time.fromisoformat(segment["end_time"])
            ):
                labels.add(segment.get("label"))
    return labels


def task_segment_count_at(changes, target_time: time, task_type_id: UUID) -> int:
    count = 0
    for change in changes:
        if change.command_type != "CreateWorkShift":
            continue
        for segment in change.command_payload["segments"]:
            if segment["segment_type"] != "TASK":
                continue
            if segment.get("task_type_id") != str(task_type_id):
                continue
            if (
                time.fromisoformat(segment["start_time"])
                <= target_time
                < time.fromisoformat(segment["end_time"])
            ):
                count += 1
    return count


def active_work_count_at(changes, target_time: time) -> int:
    count = 0
    for change in changes:
        if change.command_type != "CreateWorkShift":
            continue
        for segment in change.command_payload["segments"]:
            if segment["segment_type"] != "WORK":
                continue
            if (
                time.fromisoformat(segment["start_time"])
                <= target_time
                < time.fromisoformat(segment["end_time"])
            ):
                count += 1
                break
    return count


def work_segment_touches_break(segments: list[dict], work_segment: dict) -> bool:
    return any(
        segment["segment_type"] == "BREAK"
        and (
            segment["end_time"] == work_segment["start_time"]
            or segment["start_time"] == work_segment["end_time"]
        )
        for segment in segments
    )


def work_segment_overlaps_break(segments: list[dict], work_segment: dict) -> bool:
    work_start = time.fromisoformat(work_segment["start_time"])
    work_end = time.fromisoformat(work_segment["end_time"])
    return any(
        segment["segment_type"] == "BREAK"
        and work_start < time.fromisoformat(segment["end_time"])
        and time.fromisoformat(segment["start_time"]) < work_end
        for segment in segments
    )


def break_windows_from_changes(changes) -> list[tuple[time, time]]:
    windows = []
    for change in changes:
        if change.command_type != "CreateWorkShift":
            continue
        for segment in change.command_payload["segments"]:
            if segment["segment_type"] == "BREAK":
                windows.append(
                    (
                        time.fromisoformat(segment["start_time"]),
                        time.fromisoformat(segment["end_time"]),
                    )
                )
    return windows


def break_windows_by_staff_from_changes(changes) -> dict[str, list[tuple[time, time]]]:
    windows: dict[str, list[tuple[time, time]]] = {}
    for change in changes:
        if change.command_type != "CreateWorkShift":
            continue
        staff_id = change.command_payload["staff_member_id"]
        for segment in change.command_payload["segments"]:
            if segment["segment_type"] != "BREAK":
                continue
            windows.setdefault(staff_id, []).append(
                (
                    time.fromisoformat(segment["start_time"]),
                    time.fromisoformat(segment["end_time"]),
                )
            )
    return windows


def break_durations(windows: list[tuple[time, time]]) -> list[int]:
    return sorted(window_minutes(window) for window in windows)


def window_minutes(window: tuple[time, time]) -> int:
    start, end = window
    return (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)


def staff_breaks_are_spaced(windows: list[tuple[time, time]]) -> bool:
    sorted_windows = sorted(windows)
    return all(
        window_minutes((sorted_windows[index][1], sorted_windows[index + 1][0])) >= 60
        for index in range(len(sorted_windows) - 1)
    )


def any_windows_overlap(windows: list[tuple[time, time]]) -> bool:
    sorted_windows = sorted(windows)
    return any(
        sorted_windows[index][1] > sorted_windows[index + 1][0]
        for index in range(len(sorted_windows) - 1)
    )


def max_simultaneous_windows(windows: list[tuple[time, time]]) -> int:
    max_count = 0
    for target_start, target_end in windows:
        for minute in range(
            target_start.hour * 60 + target_start.minute,
            target_end.hour * 60 + target_end.minute,
            15,
        ):
            target_time = time(minute // 60, minute % 60)
            max_count = max(
                max_count,
                sum(start <= target_time < end for start, end in windows),
            )
    return max_count


def active_position_codes_at(changes, target_time: time) -> set[str]:
    position_code_by_id = {
        str(POSITION_B_ID): "B",
        str(POSITION_C_ID): "C",
        str(POSITION_F_ID): "F",
        str(POSITION_S_ID): "S",
    }
    codes = set()
    for change in changes:
        if change.command_type != "CreateWorkShift":
            continue
        for segment in change.command_payload["segments"]:
            if segment["segment_type"] != "WORK":
                continue
            if (
                time.fromisoformat(segment["start_time"])
                <= target_time
                < time.fromisoformat(segment["end_time"])
            ):
                codes.add(position_code_by_id[segment["position_id"]])
    return codes


def segment_covers_window(segment, start_time: time, end_time: time) -> bool:
    return (
        time.fromisoformat(segment["start_time"]) <= start_time
        and end_time <= time.fromisoformat(segment["end_time"])
    )


def requirement_for_position(position_id: UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=UUID("90000000-0000-0000-0000-000000000001"),
        requirement_date=date(2026, 7, 1),
        start_time=time(9),
        end_time=time(12),
        requirement_type="WORK",
        position_id=position_id,
        task_type_id=None,
        min_staff_count=1,
    )


def requirement_for_task() -> SimpleNamespace:
    return SimpleNamespace(
        id=UUID("90000000-0000-0000-0000-000000000002"),
        requirement_date=date(2026, 7, 1),
        start_time=time(10),
        end_time=time(10, 30),
        requirement_type="TASK",
        position_id=None,
        task_type_id=TASK_M_ID,
        min_staff_count=1,
    )


def skill(
    skill_id: UUID,
    position_id: UUID,
    *,
    code: str = "C",
    skill_category: str = "position",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=skill_id,
        code=code,
        skill_category=skill_category,
        position_id=position_id,
        task_type_id=None,
    )


def task_skill() -> SimpleNamespace:
    return SimpleNamespace(
        id=SKILL_M_ID,
        code="M",
        skill_category="task",
        position_id=None,
        task_type_id=TASK_M_ID,
    )


def task_type_m() -> SimpleNamespace:
    return SimpleNamespace(id=TASK_M_ID, code="M")


def staff_skill(skill_id: UUID, staff_id: UUID = STAFF_ID) -> SimpleNamespace:
    return SimpleNamespace(staff_member_id=staff_id, skill_definition_id=skill_id)


def store() -> SimpleNamespace:
    return SimpleNamespace(closing_time=time(22), business_hours=None)
