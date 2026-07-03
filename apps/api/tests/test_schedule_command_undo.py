from datetime import time
from uuid import UUID

from app.modules.schedule_editor.commands import (
    AssignStaffCommand,
    AssignStaffPayload,
    CreateWorkShiftCommand,
    CreateWorkShiftPayload,
    ScheduleCommandType,
    UpdateSegmentPositionCommand,
    UpdateSegmentPositionPayload,
)
from app.modules.schedule_editor.service import ScheduleCommandService


def test_create_work_shift_inverse_is_delete_work_shift() -> None:
    work_shift_id = "80000000-0000-0000-0000-000000000001"
    command = CreateWorkShiftCommand(
        type=ScheduleCommandType.CREATE_WORK_SHIFT,
        payload=CreateWorkShiftPayload(
            staff_member_id=UUID("40000000-0000-0000-0000-000000000001"),
            work_date="2026-07-01",
            start_time=time(9),
            end_time=time(12),
            position_id=UUID("50000000-0000-0000-0000-000000000001"),
        ),
    )

    inverse = ScheduleCommandService._inverse_command_payload(command, None, {"id": work_shift_id})

    assert inverse == {
        "type": "DeleteWorkShift",
        "payload": {"work_shift_id": work_shift_id},
    }


def test_assign_staff_inverse_restores_previous_staff() -> None:
    command = AssignStaffCommand(
        type=ScheduleCommandType.ASSIGN_STAFF,
        payload=AssignStaffPayload(
            work_shift_id=UUID("80000000-0000-0000-0000-000000000001"),
            staff_member_id=UUID("40000000-0000-0000-0000-000000000002"),
        ),
    )

    inverse = ScheduleCommandService._inverse_command_payload(
        command,
        {
            "id": "80000000-0000-0000-0000-000000000001",
            "staff_member_id": "40000000-0000-0000-0000-000000000001",
        },
        None,
    )

    assert inverse == {
        "type": "AssignStaff",
        "payload": {
            "work_shift_id": "80000000-0000-0000-0000-000000000001",
            "staff_member_id": "40000000-0000-0000-0000-000000000001",
        },
    }


def test_update_segment_position_inverse_restores_previous_position() -> None:
    command = UpdateSegmentPositionCommand(
        type=ScheduleCommandType.UPDATE_SEGMENT_POSITION,
        payload=UpdateSegmentPositionPayload(
            segment_id=UUID("90000000-0000-0000-0000-000000000001"),
            position_id=UUID("50000000-0000-0000-0000-000000000002"),
        ),
    )

    inverse = ScheduleCommandService._inverse_command_payload(
        command,
        {
            "id": "90000000-0000-0000-0000-000000000001",
            "segment_type": "WORK",
            "position_id": "50000000-0000-0000-0000-000000000001",
        },
        None,
    )

    assert inverse == {
        "type": "UpdateSegmentPosition",
        "payload": {
            "segment_id": "90000000-0000-0000-0000-000000000001",
            "position_id": "50000000-0000-0000-0000-000000000001",
        },
    }
