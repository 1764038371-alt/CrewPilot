from __future__ import annotations

from collections import Counter
from datetime import date, time, timedelta
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.planning.models import ShiftRequest, ShiftRequirement
from app.modules.schedule.models import ScheduleVersion, ScheduleWarning, ShiftSegment, WorkShift
from app.modules.stores.models import Position, SkillDefinition, StaffSkill, Store


class WarningService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def recalculate(self, schedule_version_id: UUID) -> int:
        schedule_version = await self.session.get(ScheduleVersion, schedule_version_id)
        if schedule_version is None:
            return 0

        await self.session.execute(
            delete(ScheduleWarning).where(
                ScheduleWarning.schedule_version_id == schedule_version_id
            )
        )

        shifts = await self._list_shifts(schedule_version_id)
        segments = await self._list_segments(schedule_version_id)
        requirements = await self._list_requirements(schedule_version.planning_period_id)
        requests = await self._list_requests(schedule_version.planning_period_id)
        skill_definitions = await self._list_skill_definitions(schedule_version.store_id)
        staff_skills = await self._list_staff_skills()
        positions = await self._list_positions(schedule_version.store_id)
        store = await self.session.get(Store, schedule_version.store_id)

        warnings: list[ScheduleWarning] = []
        warnings.extend(
            self._bc_coverage_warnings(schedule_version_id, shifts, segments, positions)
        )
        warnings.extend(
            self._opening_coverage_warnings(
                schedule_version_id,
                shifts,
                segments,
                requirements,
                positions,
                skill_definitions,
                staff_skills,
                store,
            )
        )
        warnings.extend(self._break_violation_warnings(schedule_version_id, shifts, segments))
        warnings.extend(
            self._skill_mismatch_warnings(
                schedule_version_id,
                shifts,
                segments,
                skill_definitions,
                staff_skills,
            )
        )
        warnings.extend(
            self._request_violation_warnings(schedule_version_id, shifts, requests)
        )
        warnings.extend(
            self._deposit_warnings(
                schedule_version_id,
                requirements,
                shifts,
                segments,
                skill_definitions,
                staff_skills,
                store,
            )
        )

        self.session.add_all(warnings)
        await self.session.flush()
        return len(warnings)

    async def _list_shifts(self, schedule_version_id: UUID) -> list[WorkShift]:
        result = await self.session.scalars(
            select(WorkShift)
            .where(WorkShift.schedule_version_id == schedule_version_id)
            .order_by(WorkShift.work_date, WorkShift.start_time)
        )
        return list(result)

    async def _list_segments(self, schedule_version_id: UUID) -> list[ShiftSegment]:
        result = await self.session.scalars(
            select(ShiftSegment)
            .where(ShiftSegment.schedule_version_id == schedule_version_id)
            .order_by(ShiftSegment.segment_date, ShiftSegment.start_time)
        )
        return list(result)

    async def _list_requirements(self, planning_period_id: UUID) -> list[ShiftRequirement]:
        result = await self.session.scalars(
            select(ShiftRequirement).where(
                ShiftRequirement.planning_period_id == planning_period_id
            )
        )
        return list(result)

    async def _list_requests(self, planning_period_id: UUID) -> list[ShiftRequest]:
        result = await self.session.scalars(
            select(ShiftRequest).where(ShiftRequest.planning_period_id == planning_period_id)
        )
        return list(result)

    async def _list_skill_definitions(self, store_id: UUID) -> list[SkillDefinition]:
        result = await self.session.scalars(
            select(SkillDefinition)
            .where(SkillDefinition.store_id == store_id)
            .where(SkillDefinition.is_active.is_(True))
        )
        return list(result)

    async def _list_staff_skills(self) -> list[StaffSkill]:
        result = await self.session.scalars(select(StaffSkill))
        return list(result)

    async def _list_positions(self, store_id: UUID) -> list[Position]:
        result = await self.session.scalars(
            select(Position)
            .where(Position.store_id == store_id)
            .where(Position.is_active.is_(True))
        )
        return list(result)

    def _staff_shortage_warnings(
        self,
        schedule_version_id: UUID,
        requirements: list[ShiftRequirement],
        segments: list[ShiftSegment],
    ) -> list[ScheduleWarning]:
        warnings = []
        for requirement in requirements:
            shortage_windows = requirement_shortage_windows(requirement, segments)
            for start_time, end_time, matching_count in shortage_windows:
                warnings.append(
                    ScheduleWarning(
                        schedule_version_id=schedule_version_id,
                        work_shift_id=None,
                        shift_segment_id=None,
                        warning_type="STAFF_SHORTAGE",
                        severity="warning",
                        message="必要人数を下回っている時間帯があります。",
                        details={
                            "requirement_id": str(requirement.id),
                            "current_count": matching_count,
                            "min_staff_count": requirement.min_staff_count,
                            "date": requirement.requirement_date.isoformat(),
                            "start_time": start_time.isoformat(),
                            "end_time": end_time.isoformat(),
                        },
                    )
                )
        return warnings

    def _bc_coverage_warnings(
        self,
        schedule_version_id: UUID,
        shifts: list[WorkShift],
        segments: list[ShiftSegment],
        positions: list[Position],
    ) -> list[ScheduleWarning]:
        positions_by_id = {position.id: position for position in positions}
        shifts_by_id = {shift.id: shift for shift in shifts}
        work_segments = [
            segment
            for segment in segments
            if segment.segment_type == "WORK"
            and segment.work_shift_id in shifts_by_id
            and segment.position_id in positions_by_id
        ]
        segments_by_date = group_by_segment_date(work_segments)
        warnings: list[ScheduleWarning] = []

        for work_date, date_segments in segments_by_date.items():
            start_minute = min(time_to_minutes(segment.start_time) for segment in date_segments)
            end_minute = max(time_to_minutes(segment.end_time) for segment in date_segments)
            current_start: time | None = None
            current_end: time | None = None
            current_missing: tuple[str, ...] | None = None
            current_extra: tuple[str, ...] | None = None
            current_required: tuple[str, ...] | None = None
            current_actual: dict[str, int] | None = None
            current_active_count: int | None = None
            current_target_segment_id: UUID | None = None

            for minute in range(start_minute, end_minute, 15):
                slot_start = add_minutes(time(0, 0), minute)
                slot_end = add_minutes(time(0, 0), min(minute + 15, end_minute))
                active_segments = [
                    segment
                    for segment in date_segments
                    if segment.start_time <= slot_start and slot_end <= segment.end_time
                ]
                active_codes = [
                    positions_by_id[segment.position_id].code
                    for segment in active_segments
                    if segment.position_id in positions_by_id
                ]
                required_counts = required_position_counts_for_active_count(
                    len(active_segments),
                    {position.code for position in positions},
                )
                active_counts = Counter(active_codes)
                missing = tuple(
                    code
                    for code in ("B", "C", "F", "S")
                    for _ in range(max(0, required_counts[code] - active_counts[code]))
                )
                extra = tuple(
                    code
                    for code in ("B", "C", "F", "S")
                    for _ in range(max(0, active_counts[code] - required_counts[code]))
                )
                required_codes = tuple(required_counts.elements())

                if len(active_segments) < 2 or (not missing and not extra):
                    if (
                        current_start is not None
                        and current_end is not None
                        and current_missing is not None
                        and current_extra is not None
                        and current_required is not None
                        and current_actual is not None
                        and current_active_count is not None
                    ):
                        warnings.append(
                            bc_coverage_warning(
                                schedule_version_id,
                                work_date,
                                current_start,
                                current_end,
                                current_missing,
                                current_extra,
                                current_required,
                                current_actual,
                                current_active_count,
                                current_target_segment_id,
                            )
                        )
                    current_start = None
                    current_end = None
                    current_missing = None
                    current_extra = None
                    current_required = None
                    current_actual = None
                    current_active_count = None
                    current_target_segment_id = None
                    continue

                actual_counts = {code: active_counts[code] for code in ("B", "C", "F", "S")}
                if (
                    current_start is None
                    or current_missing != missing
                    or current_extra != extra
                    or current_required != required_codes
                ):
                    if (
                        current_start is not None
                        and current_end is not None
                        and current_missing is not None
                        and current_extra is not None
                        and current_required is not None
                        and current_actual is not None
                        and current_active_count is not None
                    ):
                        warnings.append(
                            bc_coverage_warning(
                                schedule_version_id,
                                work_date,
                                current_start,
                                current_end,
                                current_missing,
                                current_extra,
                                current_required,
                                current_actual,
                                current_active_count,
                                current_target_segment_id,
                            )
                        )
                    current_start = slot_start
                    current_missing = missing
                    current_extra = extra
                    current_required = required_codes
                    current_actual = actual_counts
                    current_active_count = len(active_segments)
                    current_target_segment_id = active_segments[0].id if active_segments else None
                current_end = slot_end

            if (
                current_start is not None
                and current_end is not None
                and current_missing is not None
                and current_extra is not None
                and current_required is not None
                and current_actual is not None
                and current_active_count is not None
            ):
                warnings.append(
                    bc_coverage_warning(
                        schedule_version_id,
                        work_date,
                        current_start,
                        current_end,
                        current_missing,
                        current_extra,
                        current_required,
                        current_actual,
                        current_active_count,
                        current_target_segment_id,
                    )
                )

        return warnings

    def _deposit_warnings(
        self,
        schedule_version_id: UUID,
        requirements: list[ShiftRequirement],
        shifts: list[WorkShift],
        segments: list[ShiftSegment],
        skill_definitions: list[SkillDefinition],
        staff_skills: list[StaffSkill],
        store: Store | None,
    ) -> list[ScheduleWarning]:
        deposit_requirements = [
            requirement for requirement in requirements if requirement.requirement_type == "TASK"
        ]
        deposit_skill_ids = {skill.id for skill in skill_definitions if skill.code == "M"}
        if not deposit_requirements or not deposit_skill_ids:
            return []
        staff_with_deposit = {
            skill.staff_member_id
            for skill in staff_skills
            if skill.skill_definition_id in deposit_skill_ids
        }
        shifts_by_id = {shift.id: shift for shift in shifts}
        warnings = []
        for requirement in deposit_requirements:
            invalid_segments = invalid_deposit_segments(
                requirement.task_type_id,
                shifts_by_id,
                segments,
                store,
            )
            for segment in invalid_segments:
                warnings.append(
                    ScheduleWarning(
                        schedule_version_id=schedule_version_id,
                        work_shift_id=segment.work_shift_id,
                        shift_segment_id=segment.id,
                        warning_type="DEPOSIT_INVALID_TIME",
                        severity="critical",
                        message="入金Mは当日10:00-10:30または前日クローズ30分以外には配置できません。",
                        details={
                            "date": segment.segment_date.isoformat(),
                            "start_time": segment.start_time.isoformat(),
                            "end_time": segment.end_time.isoformat(),
                        },
                    )
                )
            primary_assigned = deposit_assigned(
                requirement.task_type_id,
                requirement.requirement_date,
                time(10, 0),
                time(10, 30),
                shifts_by_id,
                segments,
                staff_with_deposit,
            )
            fallback_date = requirement.requirement_date - timedelta(days=1)
            fallback_end = closing_time_for_date(store, fallback_date)
            fallback_start = add_minutes(fallback_end, -30)
            fallback_assigned = deposit_assigned(
                requirement.task_type_id,
                fallback_date,
                fallback_start,
                fallback_end,
                shifts_by_id,
                segments,
                staff_with_deposit,
            )
            assigned_count = int(primary_assigned) + int(fallback_assigned)
            if assigned_count > 1:
                warnings.append(
                    ScheduleWarning(
                        schedule_version_id=schedule_version_id,
                        work_shift_id=None,
                        shift_segment_id=None,
                        warning_type="DEPOSIT_DUPLICATE",
                        severity="critical",
                        message="入金Mは1日1回のみです。当日または前日救済のどちらか一方にしてください。",
                        details={
                            "date": requirement.requirement_date.isoformat(),
                        },
                    )
                )
            if not primary_assigned and not fallback_assigned:
                warnings.append(
                    ScheduleWarning(
                        schedule_version_id=schedule_version_id,
                        work_shift_id=None,
                        shift_segment_id=None,
                        warning_type="DEPOSIT_COVERAGE",
                        severity="critical",
                        message="入金Mを当日10:00-10:30にも前日クローズ帯にも配置できていません。",
                        details={
                            "date": requirement.requirement_date.isoformat(),
                            "primary_start": time(10, 0).isoformat(),
                            "primary_end": time(10, 30).isoformat(),
                            "fallback_date": fallback_date.isoformat(),
                            "fallback_start": fallback_start.isoformat(),
                            "fallback_end": fallback_end.isoformat(),
                        },
                    )
                )
        return warnings

    def _break_violation_warnings(
        self,
        schedule_version_id: UUID,
        shifts: list[WorkShift],
        segments: list[ShiftSegment],
    ) -> list[ScheduleWarning]:
        warnings = []
        segments_by_shift = group_by_shift(segments)
        for shift in shifts:
            shift_minutes = minutes_between(shift.start_time, shift.end_time)
            required_break_minutes = self._required_break_minutes(shift_minutes)
            if required_break_minutes == 0:
                continue
            shift_segments = segments_by_shift.get(shift.id, [])
            break_minutes = sum(
                minutes_between(segment.start_time, segment.end_time)
                for segment in shift_segments
                if segment.segment_type == "BREAK"
            )
            if break_minutes < required_break_minutes:
                target_segment = shift_segments[0] if shift_segments else None
                warnings.append(
                    ScheduleWarning(
                        schedule_version_id=schedule_version_id,
                        work_shift_id=shift.id,
                        shift_segment_id=target_segment.id if target_segment else None,
                        warning_type="BREAK_VIOLATION",
                        severity="warning",
                        message="休憩時間が不足しています。",
                        details={
                            "break_minutes": break_minutes,
                            "required_break_minutes": required_break_minutes,
                        },
                    )
                )
        return warnings

    def _opening_coverage_warnings(
        self,
        schedule_version_id: UUID,
        shifts: list[WorkShift],
        segments: list[ShiftSegment],
        requirements: list[ShiftRequirement],
        positions: list[Position],
        skill_definitions: list[SkillDefinition],
        staff_skills: list[StaffSkill],
        store: Store | None,
    ) -> list[ScheduleWarning]:
        if store is None:
            return []

        opening_skill_defs = {
            skill.code: skill
            for skill in skill_definitions
            if skill.code in {"B_OPEN", "C_OPEN"}
        }
        if not opening_skill_defs:
            return []

        shifts_by_id = {shift.id: shift for shift in shifts}
        work_dates = sorted(
            {
                requirement.requirement_date
                for requirement in requirements
                if requirement.requirement_type == "WORK"
            }
        )
        positions_by_id = {position.id: position for position in positions}
        staff_skill_ids = {
            (skill.staff_member_id, skill.skill_definition_id) for skill in staff_skills
        }
        warnings = []

        for work_date in work_dates:
            open_time = opening_time_for_date(store, work_date)
            opening_segments = [
                segment
                for segment in segments
                if segment.segment_date == work_date
                and segment.segment_type == "WORK"
                and segment.start_time <= open_time < segment.end_time
                and segment.work_shift_id in shifts_by_id
            ]
            opening_staff_ids = {
                shifts_by_id[segment.work_shift_id].staff_member_id
                for segment in opening_segments
            }
            if len(opening_staff_ids) < len(opening_skill_defs):
                warnings.append(
                    ScheduleWarning(
                        schedule_version_id=schedule_version_id,
                        work_shift_id=None,
                        shift_segment_id=opening_segments[0].id if opening_segments else None,
                        warning_type="OPENING_STAFF_SHORTAGE",
                        severity="critical",
                        message="開店作業に必要な人数が不足しています。",
                        details={
                            "date": work_date.isoformat(),
                            "start_time": open_time.isoformat(),
                            "end_time": add_minutes(open_time, 30).isoformat(),
                            "current_count": len(opening_staff_ids),
                            "min_staff_count": len(opening_skill_defs),
                            "required_skill_codes": sorted(opening_skill_defs),
                        },
                    )
                )

            required_role_positions = {"B_OPEN": "B", "C_OPEN": "C"}
            for skill_code, skill in opening_skill_defs.items():
                position_code = required_role_positions.get(skill_code)
                role_segments = [
                    segment
                    for segment in opening_segments
                    if position_code
                    and positions_by_id.get(segment.position_id)
                    and positions_by_id[segment.position_id].code == position_code
                ]
                skilled_staff_ids = {
                    shifts_by_id[segment.work_shift_id].staff_member_id
                    for segment in role_segments
                    if (
                        shifts_by_id[segment.work_shift_id].staff_member_id,
                        skill.id,
                    )
                    in staff_skill_ids
                }
                if not skilled_staff_ids:
                    warnings.append(
                        ScheduleWarning(
                            schedule_version_id=schedule_version_id,
                            work_shift_id=None,
                            shift_segment_id=(
                                role_segments[0].id
                                if role_segments
                                else opening_segments[0].id
                                if opening_segments
                                else None
                            ),
                            warning_type="OPEN_CLOSE_SKILL_SHORTAGE",
                            severity="critical",
                            message=(
                                f"開店{position_code or ''}担当に必要なスキルが不足しています。"
                            ),
                            details={
                                "date": work_date.isoformat(),
                                "start_time": open_time.isoformat(),
                                "end_time": add_minutes(open_time, 30).isoformat(),
                                "current_count": len(skilled_staff_ids),
                                "min_staff_count": 1,
                                "position_code": position_code,
                                "required_skill_codes": [skill_code],
                            },
                        )
                    )
        return warnings

    def _required_break_minutes(self, shift_minutes: int) -> int:
        if shift_minutes <= 210:
            return 0
        if shift_minutes < 360:
            return 15
        return 45

    def _skill_mismatch_warnings(
        self,
        schedule_version_id: UUID,
        shifts: list[WorkShift],
        segments: list[ShiftSegment],
        skill_definitions: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> list[ScheduleWarning]:
        warnings = []
        shifts_by_id = {shift.id: shift for shift in shifts}
        staff_skill_ids = {
            (skill.staff_member_id, skill.skill_definition_id) for skill in staff_skills
        }

        for segment in segments:
            if segment.segment_type not in {"WORK", "TASK"}:
                continue
            shift = shifts_by_id.get(segment.work_shift_id)
            if shift is None:
                continue
            required_skills = [
                skill
                for skill in skill_definitions
                if skill_matches_segment(skill, segment)
            ]
            if not required_skills:
                continue
            has_skill = any(
                (shift.staff_member_id, skill.id) in staff_skill_ids for skill in required_skills
            )
            if not has_skill:
                is_open_close = is_open_close_label(segment.label)
                warnings.append(
                    ScheduleWarning(
                        schedule_version_id=schedule_version_id,
                        work_shift_id=shift.id,
                        shift_segment_id=segment.id,
                        warning_type=(
                            "OPEN_CLOSE_SKILL_SHORTAGE"
                            if is_open_close
                            else "SKILL_MISMATCH"
                        ),
                        severity="warning",
                        message=(
                            "オープン・クローズ担当に必要なスキルが不足しています。"
                            if is_open_close
                            else "担当業務に必要なスキルが不足しています。"
                        ),
                        details={
                            "staff_member_id": str(shift.staff_member_id),
                            "required_skill_ids": [str(skill.id) for skill in required_skills],
                            "required_skill_codes": [skill.code for skill in required_skills],
                        },
                    )
                )
        return warnings

    def _request_violation_warnings(
        self,
        schedule_version_id: UUID,
        shifts: list[WorkShift],
        requests: list[ShiftRequest],
    ) -> list[ScheduleWarning]:
        unavailable_types = {"unavailable", "off", "ng"}
        warnings = []
        for shift in shifts:
            for request in requests:
                if request.staff_member_id != shift.staff_member_id:
                    continue
                if request.request_date != shift.work_date:
                    continue
                if request.request_type not in unavailable_types:
                    continue
                request_start = request.start_time or shift.start_time
                request_end = request.end_time or shift.end_time
                if overlaps(shift.start_time, shift.end_time, request_start, request_end):
                    warnings.append(
                        ScheduleWarning(
                            schedule_version_id=schedule_version_id,
                            work_shift_id=shift.id,
                            shift_segment_id=None,
                            warning_type="REQUEST_VIOLATION",
                            severity="warning",
                            message="希望シフトと割当が衝突しています。",
                            details={"shift_request_id": str(request.id)},
                        )
                    )
        return warnings


def group_by_shift(segments: list[ShiftSegment]) -> dict[UUID, list[ShiftSegment]]:
    grouped: dict[UUID, list[ShiftSegment]] = {}
    for segment in segments:
        grouped.setdefault(segment.work_shift_id, []).append(segment)
    return grouped


def group_by_segment_date(segments: list[ShiftSegment]) -> dict[date, list[ShiftSegment]]:
    grouped: dict[date, list[ShiftSegment]] = {}
    for segment in segments:
        grouped.setdefault(segment.segment_date, []).append(segment)
    return grouped


def bc_coverage_warning(
    schedule_version_id: UUID,
    work_date: date,
    start_time: time,
    end_time: time,
    missing_positions: tuple[str, ...],
    extra_positions: tuple[str, ...],
    required_positions: tuple[str, ...],
    actual_counts: dict[str, int],
    active_count: int,
    target_segment_id: UUID | None,
) -> ScheduleWarning:
    missing_label = " / ".join(missing_positions) if missing_positions else "なし"
    extra_label = " / ".join(extra_positions) if extra_positions else "なし"
    return ScheduleWarning(
        schedule_version_id=schedule_version_id,
        work_shift_id=None,
        shift_segment_id=target_segment_id,
        warning_type="BC_COVERAGE",
        severity="critical",
        message=(
            f"必要ポジション構成が崩れています。不足: {missing_label} / 余剰: {extra_label}。"
            "人数に応じてBC、BCF、BCFS、またはB(ST)/B(SH)/C/F/Sを確保してください。"
        ),
        details={
            "date": work_date.isoformat(),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "current_count": active_count,
            "min_staff_count": 2,
            "missing_position_codes": list(missing_positions),
            "extra_position_codes": list(extra_positions),
            "actual_position_counts": actual_counts,
            "required_position_codes": list(required_positions),
        },
    )


def required_position_counts_for_active_count(
    active_count: int,
    available_codes: set[str],
) -> Counter[str]:
    if active_count < 2:
        return Counter()
    if active_count == 2:
        preferred = ["B", "C"]
    elif active_count == 3:
        preferred = ["B", "C", "F"]
    elif active_count == 4:
        preferred = ["B", "C", "F", "S"]
    else:
        preferred = ["B", "B", "C", "F", "S"]

    result = [code for code in preferred if code in available_codes]
    fallback_codes = ["S", "F", "B", "C"] if active_count > 5 else ["B", "C", "F", "S"]
    while len(result) < active_count:
        added = False
        for code in fallback_codes:
            if code in available_codes:
                result.append(code)
                added = True
                if len(result) == active_count:
                    break
        if not added:
            break
    return Counter(result[:active_count])


def minutes_between(start_time: time, end_time: time) -> int:
    return time_to_minutes(end_time) - time_to_minutes(start_time)


def time_to_minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def overlaps(start_a: time, end_a: time, start_b: time, end_b: time) -> bool:
    return start_a < end_b and start_b < end_a


def matching_requirement_count(
    requirement: ShiftRequirement,
    segments: list[ShiftSegment],
) -> int:
    matching = [
        segment
        for segment in segments
        if segment.segment_date == requirement.requirement_date
        and overlaps(
            segment.start_time,
            segment.end_time,
            requirement.start_time,
            requirement.end_time,
        )
        and segment.segment_type == requirement.requirement_type
        and (
            requirement.position_id is None
            or segment.position_id == requirement.position_id
        )
        and (
            requirement.task_type_id is None
            or segment.task_type_id == requirement.task_type_id
        )
    ]
    if requirement.position_id is None and requirement.task_type_id is None:
        return len({segment.work_shift_id for segment in matching})
    return len(matching)


def requirement_shortage_windows(
    requirement: ShiftRequirement,
    segments: list[ShiftSegment],
) -> list[tuple[time, time, int]]:
    if requirement.min_staff_count <= 0:
        return []
    start_minute = time_to_minutes(requirement.start_time)
    end_minute = time_to_minutes(requirement.end_time)
    shortage_windows: list[tuple[time, time, int]] = []
    current_start: time | None = None
    current_end: time | None = None
    current_count: int | None = None

    for minute in range(start_minute, end_minute, 15):
        slot_start = add_minutes(time(0, 0), minute)
        slot_end = add_minutes(time(0, 0), min(minute + 15, end_minute))
        matching_count = matching_requirement_count_for_window(
            requirement,
            segments,
            slot_start,
            slot_end,
        )
        if matching_count >= requirement.min_staff_count:
            if current_start is not None and current_end is not None and current_count is not None:
                shortage_windows.append((current_start, current_end, current_count))
            current_start = None
            current_end = None
            current_count = None
            continue
        if current_start is None or current_count != matching_count:
            if current_start is not None and current_end is not None and current_count is not None:
                shortage_windows.append((current_start, current_end, current_count))
            current_start = slot_start
            current_count = matching_count
        current_end = slot_end

    if current_start is not None and current_end is not None and current_count is not None:
        shortage_windows.append((current_start, current_end, current_count))
    return shortage_windows


def matching_requirement_count_for_window(
    requirement: ShiftRequirement,
    segments: list[ShiftSegment],
    start_time: time,
    end_time: time,
) -> int:
    matching = [
        segment
        for segment in segments
        if segment.segment_date == requirement.requirement_date
        and segment.start_time <= start_time
        and end_time <= segment.end_time
        and segment.segment_type == requirement.requirement_type
        and (
            requirement.position_id is None
            or segment.position_id == requirement.position_id
        )
        and (
            requirement.task_type_id is None
            or segment.task_type_id == requirement.task_type_id
        )
    ]
    if requirement.position_id is None and requirement.task_type_id is None:
        return len({segment.work_shift_id for segment in matching})
    return len(matching)


def is_open_close_label(label: str | None) -> bool:
    return bool(label and (label.endswith("_OPEN") or label.endswith("_CLOSE")))


def skill_matches_segment(skill: SkillDefinition, segment: ShiftSegment) -> bool:
    if is_open_close_label(segment.label):
        return skill.code == segment.label and getattr(skill, "skill_category", "") in {
            "opening",
            "closing",
        }
    if segment.segment_type == "TASK":
        return skill.task_type_id == segment.task_type_id and getattr(
            skill,
            "skill_category",
            "task",
        ) == "task"
    return skill.position_id == segment.position_id and getattr(
        skill,
        "skill_category",
        "position",
    ) == "position"


def add_minutes(value: time, minutes: int) -> time:
    total = max(0, min(24 * 60 - 1, time_to_minutes(value) + minutes))
    return time(total // 60, total % 60)


def closing_time_for_date(store: Store | None, target_date) -> time:
    if store is None:
        return time(22, 0)
    business_hours = store.business_hours or {}
    day_type = "holiday" if target_date.weekday() >= 5 else "weekday"
    hours = business_hours.get(day_type)
    if isinstance(hours, dict) and isinstance(hours.get("closing_time"), str):
        return time.fromisoformat(hours["closing_time"])
    if isinstance(hours, dict) and isinstance(hours.get("close"), str):
        return time.fromisoformat(hours["close"])
    weekday_key = target_date.strftime("%A").lower()
    daily_hours = business_hours.get("daily")
    if isinstance(daily_hours, dict):
        day_hours = daily_hours.get(weekday_key)
        if isinstance(day_hours, dict) and isinstance(day_hours.get("close"), str):
                return time.fromisoformat(day_hours["close"])
    return store.closing_time


def opening_time_for_date(store: Store | None, target_date) -> time:
    if store is None:
        return time(9, 0)
    business_hours = store.business_hours or {}
    day_type = "holiday" if target_date.weekday() >= 5 else "weekday"
    hours = business_hours.get(day_type)
    if isinstance(hours, dict) and isinstance(hours.get("opening_time"), str):
        return time.fromisoformat(hours["opening_time"])
    if isinstance(hours, dict) and isinstance(hours.get("open"), str):
        return time.fromisoformat(hours["open"])
    weekday_key = target_date.strftime("%A").lower()
    daily_hours = business_hours.get("daily")
    if isinstance(daily_hours, dict):
        day_hours = daily_hours.get(weekday_key)
        if isinstance(day_hours, dict) and isinstance(day_hours.get("open"), str):
            return time.fromisoformat(day_hours["open"])
    return store.opening_time


def deposit_assigned(
    task_type_id: UUID | None,
    target_date,
    start_time: time,
    end_time: time,
    shifts_by_id: dict[UUID, WorkShift],
    segments: list[ShiftSegment],
    staff_with_deposit: set[UUID],
) -> bool:
    if task_type_id is None:
        return False
    for segment in segments:
        shift = shifts_by_id.get(segment.work_shift_id)
        if shift is None:
            continue
        if (
            segment.segment_type == "TASK"
            and segment.task_type_id == task_type_id
            and segment.segment_date == target_date
            and segment.start_time == start_time
            and segment.end_time == end_time
            and shift.staff_member_id in staff_with_deposit
        ):
            return True
    return False


def invalid_deposit_segments(
    task_type_id: UUID | None,
    shifts_by_id: dict[UUID, WorkShift],
    segments: list[ShiftSegment],
    store: Store | None,
) -> list[ShiftSegment]:
    invalid = []
    for segment in segments:
        if segment.segment_type != "TASK" or segment.task_type_id != task_type_id:
            continue
        shift = shifts_by_id.get(segment.work_shift_id)
        if shift is None:
            invalid.append(segment)
            continue
        is_primary = segment.start_time == time(10, 0) and segment.end_time == time(10, 30)
        close = closing_time_for_date(store, segment.segment_date)
        is_close_rescue = (
            segment.start_time == add_minutes(close, -30)
            and segment.end_time == close
        )
        if not is_primary and not is_close_rescue:
            invalid.append(segment)
    return invalid
