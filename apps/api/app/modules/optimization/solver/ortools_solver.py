from __future__ import annotations

import time as monotonic_time
from collections import Counter
from dataclasses import dataclass
from datetime import date, time, timedelta
from functools import lru_cache
from typing import Optional
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from ortools.sat.python import cp_model
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.optimization.scope import OptimizationScopePayload
from app.modules.optimization.solver.base import (
    ScheduleSolver,
    SolverChange,
    SolverMetrics,
    SolverProposal,
)
from app.modules.planning.models import ShiftRequest, ShiftRequirement
from app.modules.schedule.models import ScheduleVersion, ScheduleWarning, ShiftSegment, WorkShift
from app.modules.schedule_editor.warnings import overlaps
from app.modules.staff.models import StaffMember
from app.modules.stores.models import Position, SkillDefinition, StaffSkill, Store, TaskType

MIN_POSITION_BLOCK_MINUTES = 60
IDEAL_POSITION_BLOCK_MINUTES = 120
SOFT_MAX_POSITION_BLOCK_MINUTES = 150
HARD_MAX_POSITION_BLOCK_MINUTES = 180


@dataclass(frozen=True)
class PositionChoice:
    position_id: UUID
    is_current: bool
    resolves_skill_mismatch: bool
    natural_score: int = 0


@dataclass(frozen=True)
class SegmentDecision:
    segment: ShiftSegment
    shift: WorkShift
    choices: list[PositionChoice]


class ORToolsSolver(ScheduleSolver):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def solve(
        self,
        schedule_version_id: UUID,
        scope: OptimizationScopePayload,
        time_limit_seconds: float,
    ) -> SolverProposal:
        started_at = monotonic_time.perf_counter()
        schedule_version = await self.session.get(ScheduleVersion, schedule_version_id)
        if schedule_version is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Schedule version not found",
            )

        shifts = await self._list_shifts(schedule_version_id)
        segments = await self._list_segments(schedule_version_id)
        requirements = await self._list_requirements(schedule_version.planning_period_id)
        requests = await self._list_requests(schedule_version.planning_period_id)
        warnings_before = await self._list_warnings(schedule_version_id)
        positions = await self._list_positions(schedule_version.store_id)
        task_types = await self._list_task_types(schedule_version.store_id)
        staff_members = await self._list_staff_members(schedule_version.store_id)
        skills = await self._list_skill_definitions(schedule_version.store_id)
        staff_skills = await self._list_staff_skills()
        store = await self.session.get(Store, schedule_version.store_id)
        fairness_before = fairness_score(shifts)
        request_generation_changes = self._build_request_schedule_generation_changes(
            scope=scope,
            shifts=shifts,
            requests=requests,
            staff_members=staff_members,
            positions=positions,
            skills=skills,
            staff_skills=staff_skills,
            task_types=task_types,
        )
        if request_generation_changes:
            before_counts = warning_counts(warnings_before)
            adjusted_warning_after = dict(before_counts)
            adjusted_warning_after["STAFF_SHORTAGE"] = 0
            adjusted_warning_after["REQUEST_VIOLATION"] = 0
            fairness_after = max(
                0,
                fairness_before - count_staff_changes(request_generation_changes),
            )
            summary_metrics = proposal_summary_metrics(
                request_generation_changes,
                before_counts,
                adjusted_warning_after,
                fairness_before,
                fairness_after,
            )
            return SolverProposal(
                title="AI提案: 希望シフトから原案作成",
                summary=(
                    "希望時間を基準に勤務を作り直し、各時間帯でBC、"
                    "4人でBCFS、5人でBBCFSを揃える原案を作成しました。"
                ),
                generated_by="ortools",
                changes=request_generation_changes,
                metrics=SolverMetrics(
                    status="completed",
                    solve_time_ms=elapsed_ms(started_at),
                    objective_value=None,
                    warning_before=before_counts,
                    warning_after=adjusted_warning_after,
                    changed_segments=len(
                        {
                            change.target_id
                            for change in request_generation_changes
                            if change.target_id
                        }
                    ),
                    changed_work_shifts=count_work_shift_changes(request_generation_changes),
                    fairness_score=fairness_after,
                ),
                summary_metrics=summary_metrics,
            )

        decisions = self._build_decisions(
            scope=scope,
            shifts=shifts,
            segments=segments,
            warnings=warnings_before,
            positions=positions,
            requests=requests,
            skills=skills,
            staff_skills=staff_skills,
        )
        position_updates: dict[UUID, UUID] = {}
        objective_value: Optional[int] = None
        status_value = "completed"
        if decisions:
            model = cp_model.CpModel()
            variables: dict[tuple[UUID, UUID], cp_model.IntVar] = {}
            selected_position_by_segment: dict[UUID, dict[UUID, cp_model.IntVar]] = {}
            changed_flags: list[cp_model.IntVar] = []

            for decision in decisions:
                selected_position_by_segment[decision.segment.id] = {}
                choice_vars = []
                for choice in decision.choices:
                    variable = model.NewBoolVar(
                        f"segment_{decision.segment.id}_position_{choice.position_id}"
                    )
                    variables[(decision.segment.id, choice.position_id)] = variable
                    selected_position_by_segment[decision.segment.id][choice.position_id] = variable
                    choice_vars.append(variable)
                    if not choice.is_current:
                        changed_flags.append(variable)
                model.AddExactlyOne(choice_vars)

            shortage_terms: list[cp_model.IntVar] = []
            natural_score_terms = []
            for requirement in requirements:
                if requirement.requirement_type != "WORK" or requirement.position_id is None:
                    continue
                covering_terms = []
                fixed_count = 0
                for segment in segments:
                    if not self._segment_matches_requirement_window(segment, requirement):
                        continue
                    if segment.segment_type != "WORK":
                        continue
                    variable = selected_position_by_segment.get(segment.id, {}).get(
                        requirement.position_id
                    )
                    if variable is not None:
                        covering_terms.append(variable)
                        continue
                    if segment.position_id == requirement.position_id:
                        fixed_count += 1

                shortage = model.NewIntVar(
                    0,
                    requirement.min_staff_count,
                    f"shortage_{requirement.id}",
                )
                model.Add(
                    shortage >= requirement.min_staff_count - fixed_count - sum(covering_terms)
                )
                shortage_terms.append(shortage)

            for decision in decisions:
                for choice in decision.choices:
                    variable = variables[(decision.segment.id, choice.position_id)]
                    if choice.natural_score:
                        natural_score_terms.append(variable * choice.natural_score)

            model.Minimize(
                (sum(shortage_terms) * 100)
                + (sum(changed_flags) * 4)
                + sum(natural_score_terms)
            )
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = time_limit_seconds
            solver.parameters.num_search_workers = 8
            result_status = solver.Solve(model)
            status_value = self._status_from_result(result_status)
            if result_status in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
                objective_value = int(solver.ObjectiveValue())
                for decision in decisions:
                    for choice in decision.choices:
                        variable = variables[(decision.segment.id, choice.position_id)]
                        if solver.BooleanValue(variable):
                            if choice.position_id != decision.segment.position_id:
                                position_updates[decision.segment.id] = choice.position_id
                            break

        warnings_after = self._simulate_warning_counts(
            shifts=shifts,
            segments=segments,
            requirements=requirements,
            requests=requests,
            skills=skills,
            staff_skills=staff_skills,
            proposed_positions=position_updates,
        )
        before_counts = warning_counts(warnings_before)
        changes = self._build_changes(
            decisions=decisions,
            proposed_positions=position_updates,
            before_counts=before_counts,
            after_counts=warnings_after,
        )
        changes.extend(
            self._build_phase2_changes(
                scope=scope,
                shifts=shifts,
                segments=segments,
                requirements=requirements,
                requests=requests,
                warnings=warnings_before,
                staff_members=staff_members,
                skills=skills,
                staff_skills=staff_skills,
                task_types=task_types,
                store=store,
            )
        )
        adjusted_warning_after = dict(warnings_after)
        adjusted_warning_after["STAFF_SHORTAGE"] = max(
            0,
            adjusted_warning_after.get("STAFF_SHORTAGE", 0)
            - count_changes(changes, "create_work_shift"),
        )
        adjusted_warning_after["BREAK_VIOLATION"] = max(
            0,
            adjusted_warning_after.get("BREAK_VIOLATION", 0)
            - count_changes(changes, "create_break"),
        )
        adjusted_warning_after["SKILL_MISMATCH"] = max(
            0,
            adjusted_warning_after.get("SKILL_MISMATCH", 0)
            - count_changes(changes, "assign_staff")
            - count_changes(changes, "swap_staff"),
        )
        adjusted_warning_after["OPEN_CLOSE_SKILL_SHORTAGE"] = max(
            0,
            adjusted_warning_after.get("OPEN_CLOSE_SKILL_SHORTAGE", 0)
            - count_changes(changes, "assign_staff")
            - count_changes(changes, "swap_staff"),
        )
        deposit_change_count = count_changes(changes, "create_task_segment") + count_changes(
            changes,
            "create_work_shift",
            lambda change: change.command_payload.get("task_type_id") is not None,
        ) + count_changes(changes, "move_task_segment")
        adjusted_warning_after["DEPOSIT_COVERAGE"] = max(
            0,
            adjusted_warning_after.get("DEPOSIT_COVERAGE", 0) - deposit_change_count,
        )
        adjusted_warning_after["STAFF_SHORTAGE"] = max(
            0,
            adjusted_warning_after.get("STAFF_SHORTAGE", 0) - deposit_change_count,
        )
        fairness_after = max(0, fairness_before - count_staff_changes(changes))
        summary_metrics = proposal_summary_metrics(
            changes,
            before_counts,
            adjusted_warning_after,
            fairness_before,
            fairness_after,
        )
        return SolverProposal(
            title="AI提案: OR-Tools最適化案",
            summary=(
                f"OR-Toolsが{scope.type.value}スコープで"
                f"{len(changes)}件のCommand候補を作成しました。"
            ),
            generated_by="ortools",
            changes=changes,
            metrics=SolverMetrics(
                status=status_value,
                solve_time_ms=elapsed_ms(started_at),
                objective_value=objective_value,
                warning_before=before_counts,
                warning_after=adjusted_warning_after,
                changed_segments=len({change.target_id for change in changes if change.target_id}),
                changed_work_shifts=count_work_shift_changes(changes),
                fairness_score=fairness_after,
            ),
            summary_metrics=summary_metrics,
        )

    def _build_decisions(
        self,
        *,
        scope: OptimizationScopePayload,
        shifts: list[WorkShift],
        segments: list[ShiftSegment],
        warnings: list[ScheduleWarning],
        positions: list[Position],
        requests: list[ShiftRequest],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> list[SegmentDecision]:
        shifts_by_id = {shift.id: shift for shift in shifts}
        decisions = []
        scoped_segment_ids = self._scoped_segment_ids(scope, warnings)
        for segment in segments:
            shift = shifts_by_id.get(segment.work_shift_id)
            if shift is None:
                continue
            if not self._segment_in_scope(segment, shift, scope, scoped_segment_ids):
                continue
            if segment.segment_type != "WORK" or segment.position_id is None:
                continue
            if is_open_close_label(segment.label):
                continue
            if segment.is_locked or shift.is_locked:
                continue
            if self._has_blocking_request(shift, segment, requests):
                continue

            choices = []
            for position in positions:
                if self._staff_can_cover_position(
                    shift.staff_member_id,
                    position.id,
                    skills,
                    staff_skills,
                ):
                    choices.append(
                        PositionChoice(
                            position_id=position.id,
                            is_current=position.id == segment.position_id,
                            resolves_skill_mismatch=self._position_resolves_skill_mismatch(
                                shift.staff_member_id,
                                segment.position_id,
                                position.id,
                                skills,
                                staff_skills,
                            ),
                            natural_score=natural_position_score(segment, position, segments),
                        )
                    )
            if choices:
                decisions.append(SegmentDecision(segment=segment, shift=shift, choices=choices))
        return decisions

    def _build_changes(
        self,
        *,
        decisions: list[SegmentDecision],
        proposed_positions: dict[UUID, UUID],
        before_counts: dict,
        after_counts: dict,
    ) -> list[SolverChange]:
        decisions_by_segment_id = {decision.segment.id: decision for decision in decisions}
        changes = []
        for segment_id, position_id in proposed_positions.items():
            decision = decisions_by_segment_id[segment_id]
            reasons = ["ロック制約を維持"]
            if after_counts.get("STAFF_SHORTAGE", 0) < before_counts.get("STAFF_SHORTAGE", 0):
                reasons.append("必要人数不足を解消")
            if after_counts.get("SKILL_MISMATCH", 0) < before_counts.get("SKILL_MISMATCH", 0):
                reasons.append("スキル不足を解消")
            if after_counts.get("REQUEST_VIOLATION", 0) < before_counts.get("REQUEST_VIOLATION", 0):
                reasons.append("希望違反を減少")
            changes.append(
                SolverChange(
                    change_type="UPDATE_SEGMENT_POSITION",
                    target_type="ShiftSegment",
                    target_id=decision.segment.id,
                    command_type="UpdateSegmentPosition",
                    command_payload={
                        "segment_id": str(decision.segment.id),
                        "position_id": str(position_id),
                    },
                    before_value=segment_snapshot(decision.segment),
                    after_value={
                        **segment_snapshot(decision.segment),
                        "segment_type": "WORK",
                        "position_id": str(position_id),
                        "task_type_id": None,
                    },
                    explanation={
                        "summary": "制約違反を減らすため、担当ポジションを変更します。",
                        "reasons": reasons,
                        "warning_before": before_counts,
                        "warning_after": after_counts,
                    },
                )
            )
        return changes

    def _build_phase2_changes(
        self,
        *,
        scope: OptimizationScopePayload,
        shifts: list[WorkShift],
        segments: list[ShiftSegment],
        requirements: list[ShiftRequirement],
        requests: list[ShiftRequest],
        warnings: list[ScheduleWarning],
        staff_members: list[StaffMember],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
        task_types: list[TaskType],
        store: Store | None,
    ) -> list[SolverChange]:
        changes: list[SolverChange] = []
        changes.extend(
            self._build_deposit_task_changes(
                scope,
                shifts,
                segments,
                requirements,
                requests,
                staff_members,
                skills,
                staff_skills,
                task_types,
                store,
            )
        )
        changes.extend(
            self._build_create_work_shift_changes(
                scope,
                shifts,
                segments,
                requirements,
                requests,
                staff_members,
                skills,
                staff_skills,
            )
        )
        changes.extend(
            self._build_staff_assignment_changes(
                scope,
                shifts,
                segments,
                requests,
                warnings,
                staff_members,
                skills,
                staff_skills,
            )
        )
        changes.extend(self._build_break_changes(scope, shifts, segments, warnings))
        return changes

    def _build_request_schedule_generation_changes(
        self,
        *,
        scope: OptimizationScopePayload,
        shifts: list[WorkShift],
        requests: list[ShiftRequest],
        staff_members: list[StaffMember],
        positions: list[Position],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
        task_types: list[TaskType],
    ) -> list[SolverChange]:
        target_date = scope_date(scope)
        if target_date is None:
            return []

        request_rows = [
            request
            for request in requests
            if request.request_date == target_date
            and request.request_type in {"available", "preferred", "ok"}
            and request.start_time is not None
            and request.end_time is not None
            and request.start_time < request.end_time
        ]
        if not request_rows:
            return []

        staff_by_id = {staff_member.id: staff_member for staff_member in staff_members}
        request_rows = [
            request
            for request in request_rows
            if request.staff_member_id in staff_by_id
            and getattr(staff_by_id[request.staff_member_id], "is_active", True)
        ]
        if not request_rows:
            return []

        positions_by_code = {position.code: position for position in positions}
        if "C" not in positions_by_code:
            return []

        segments_by_staff = self._plan_request_based_segments(
            target_date=target_date,
            request_rows=request_rows,
            positions_by_code=positions_by_code,
            skills=skills,
            staff_skills=staff_skills,
            task_types=task_types,
            staff_by_id=staff_by_id,
        )
        if not segments_by_staff:
            return []

        changes: list[SolverChange] = []
        for shift in shifts:
            if shift.work_date != target_date or shift.is_locked:
                continue
            changes.append(
                SolverChange(
                    change_type="delete_work_shift",
                    target_type="WorkShift",
                    target_id=shift.id,
                    command_type="DeleteWorkShift",
                    command_payload={"work_shift_id": str(shift.id)},
                    before_value=work_shift_snapshot(shift),
                    after_value=None,
                    explanation={
                        "summary": (
                            "希望シフトから原案を作り直すため、"
                            "既存の未ロック勤務を置き換えます。"
                        ),
                        "resolved_warnings": ["STAFF_SHORTAGE", "REQUEST_VIOLATION"],
                        "active_constraints": ["ロック済み勤務は保持", "希望時間を優先"],
                        "reasons": ["既存ブロックの崩れを引き継がない"],
                    },
                )
            )

        for request in sorted(request_rows, key=lambda item: (item.start_time, item.end_time)):
            planned_segments = segments_by_staff.get(request.staff_member_id, [])
            if not planned_segments:
                continue
            staff_member = staff_by_id[request.staff_member_id]
            payload_segments = [
                {
                    "start_time": segment["start_time"].isoformat(),
                    "end_time": segment["end_time"].isoformat(),
                    "segment_type": segment["segment_type"],
                    "position_id": str(segment["position_id"])
                    if segment.get("position_id") is not None
                    else None,
                    "task_type_id": str(segment["task_type_id"])
                    if segment.get("task_type_id") is not None
                    else None,
                    "label": segment.get("label"),
                }
                for segment in planned_segments
            ]
            first_work_position_id = next(
                (
                    segment["position_id"]
                    for segment in planned_segments
                    if segment["segment_type"] == "WORK" and segment.get("position_id") is not None
                ),
                None,
            )
            after_value = {
                "staff_member_id": str(staff_member.id),
                "work_date": target_date.isoformat(),
                "start_time": request.start_time.isoformat(),
                "end_time": request.end_time.isoformat(),
                "segments": payload_segments,
            }
            changes.append(
                SolverChange(
                    change_type="create_work_shift",
                    target_type="WorkShift",
                    target_id=None,
                    command_type="CreateWorkShift",
                    command_payload={
                        **after_value,
                        "position_id": str(first_work_position_id)
                        if first_work_position_id
                        else None,
                    },
                    before_value=None,
                    after_value=after_value,
                    explanation={
                        "summary": (
                            f"{staff_member.display_name}を希望時間"
                            f"{request.start_time.strftime('%H:%M')}-"
                            f"{request.end_time.strftime('%H:%M')}で勤務化します。"
                        ),
                        "resolved_warnings": ["STAFF_SHORTAGE", "REQUEST_VIOLATION"],
                        "active_constraints": [
                            "希望勤務時間内",
                            "最低BC配置",
                            "4人はBCFS配置",
                            "5人以上はBBCFS配置",
                            "2時間前後のポジションローテーション",
                            "Mは当日10:00-10:30のみ",
                        ],
                        "reasons": [
                            "店長が入力した希望時間を勤務時間として採用",
                            "時間帯ごとの必要ポジションを満たすよう分割",
                            "短すぎる交代を避け、2時間前後のまとまりでローテーション",
                        ],
                    },
                )
            )
        return changes

    def _plan_request_based_segments(
        self,
        *,
        target_date: date,
        request_rows: list[ShiftRequest],
        positions_by_code: dict[str, Position],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
        task_types: list[TaskType],
        staff_by_id: dict[UUID, StaffMember],
    ) -> dict[UUID, list[dict]]:
        fixed_boundaries = {
            minute
            for request in request_rows
            for minute in (
                time_to_minutes(request.start_time),
                time_to_minutes(request.end_time),
            )
        }
        has_deposit_task = any(task_type.code == "M" for task_type in task_types)
        if has_deposit_task and any(
            request.start_time <= time(10, 0) and time(10, 30) <= request.end_time
            for request in request_rows
        ):
            fixed_boundaries.update({time_to_minutes(time(10, 0)), time_to_minutes(time(10, 30))})
        earliest = min(time_to_minutes(request.start_time) for request in request_rows)
        latest = max(time_to_minutes(request.end_time) for request in request_rows)
        boundaries = set(fixed_boundaries)
        cursor = round_to_quarter_hour(earliest + 120)
        while cursor < latest:
            boundaries.add(cursor)
            cursor += 120
        boundaries = sorted(boundaries)
        if len(boundaries) < 2:
            return {}

        intervals = [
            (
                add_minutes(time(0, 0), boundaries[index]),
                add_minutes(time(0, 0), boundaries[index + 1]),
            )
            for index in range(len(boundaries) - 1)
            if boundaries[index] < boundaries[index + 1]
        ]
        planned: dict[UUID, list[dict]] = {request.staff_member_id: [] for request in request_rows}
        interval_rows = []
        for start_time, end_time in intervals:
            active_requests = sorted(
                [
                    request
                    for request in request_rows
                    if request.start_time <= start_time and end_time <= request.end_time
                ],
                key=lambda item: (
                    staff_by_id[item.staff_member_id].employee_number or "",
                    staff_by_id[item.staff_member_id].display_name,
                    str(item.staff_member_id),
                ),
            )
            if active_requests:
                interval_rows.append((start_time, end_time, active_requests))

        interval_assignments = self._assign_positions_across_intervals(
            interval_rows,
            positions_by_code,
            skills,
            staff_skills,
        )

        for start_time, end_time, active_requests in interval_rows:
            assignments = interval_assignments.get((start_time, end_time), {})
            active_staff_count = len(active_requests)
            b_assignment_index = 0
            for request in active_requests:
                position_code = assignments.get(request.staff_member_id)
                if position_code is None or position_code not in positions_by_code:
                    continue
                position = positions_by_code[position_code]
                label = None
                if position_code == "B" and active_staff_count >= 5:
                    label = "ST" if b_assignment_index == 0 else "SH"
                    b_assignment_index += 1
                planned[request.staff_member_id].append(
                    {
                        "start_time": start_time,
                        "end_time": end_time,
                        "segment_type": "WORK",
                        "position_code": position_code,
                        "position_id": position.id,
                        "task_type_id": None,
                        "label": label,
                    }
                )

        self._insert_break_segments(
            planned,
            request_rows,
            positions_by_code,
            skills,
            staff_skills,
        )
        self._insert_deposit_segment(
            planned,
            target_date,
            request_rows,
            skills,
            staff_skills,
            task_types,
        )
        for segments in planned.values():
            self._absorb_short_work_segments(segments)
        self._ensure_break_coverage_positions(
            planned,
            positions_by_code,
            skills,
            staff_skills,
        )
        for staff_member_id, segments in planned.items():
            self._split_overlong_work_segments(
                staff_member_id,
                segments,
                positions_by_code,
                skills,
                staff_skills,
            )
        for segments in planned.values():
            self._absorb_short_work_segments(segments)
        self._ensure_break_coverage_positions(
            planned,
            positions_by_code,
            skills,
            staff_skills,
        )
        for staff_member_id, segments in planned.items():
            self._split_overlong_work_segments(
                staff_member_id,
                segments,
                positions_by_code,
                skills,
                staff_skills,
            )
        for segments in planned.values():
            self._smooth_short_work_fragments(segments)
        self._ensure_break_coverage_positions(
            planned,
            positions_by_code,
            skills,
            staff_skills,
        )
        for segments in planned.values():
            self._smooth_short_work_fragments(
                segments,
                skip_break_adjacent=True,
                require_same_work_neighbors=True,
            )
        self._enforce_exact_position_mix(
            planned,
            positions_by_code,
            skills,
            staff_skills,
        )
        self._sync_planned_position_codes(planned, positions_by_code)
        self._normalize_b_lane_labels(planned)
        for segments in planned.values():
            self._merge_adjacent_planned_segments(segments)
        return planned

    def _assign_positions_across_intervals(
        self,
        interval_rows: list[tuple[time, time, list[ShiftRequest]]],
        positions_by_code: dict[str, Position],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> dict[tuple[time, time], dict[UUID, str]]:
        if not interval_rows:
            return {}

        paths: list[tuple[int, dict[UUID, str], dict[UUID, int], list[dict[UUID, str]]]] = [
            (0, {}, {}, [])
        ]
        beam_width = 240

        for start_time, end_time, active_requests in interval_rows:
            start_minute = time_to_minutes(start_time)
            candidates = self._assignment_candidates_for_interval(
                active_requests,
                positions_by_code,
                skills,
                staff_skills,
            )
            if not candidates:
                candidates = self._fallback_assignment_candidates_for_interval(
                    active_requests,
                    positions_by_code,
                    skills,
                    staff_skills,
                )
            if not candidates:
                candidates = [{}]
            next_paths: list[
                tuple[int, dict[UUID, str], dict[UUID, int], list[dict[UUID, str]]]
            ] = []
            for score, previous_codes, previous_started, history in paths:
                for candidate in candidates:
                    transition_score, next_started = self._assignment_transition_score(
                        candidate,
                        previous_codes,
                        previous_started,
                        start_minute,
                        time_to_minutes(end_time),
                    )
                    next_paths.append(
                        (
                            score + transition_score,
                            {**previous_codes, **candidate},
                            next_started,
                            [*history, candidate],
                        )
                    )
            paths = sorted(next_paths, key=lambda item: item[0])[:beam_width]

        best = min(paths, key=lambda item: item[0])
        assignments_by_interval: dict[tuple[time, time], dict[UUID, str]] = {}
        for index, (start_time, end_time, _) in enumerate(interval_rows):
            assignments_by_interval[(start_time, end_time)] = best[3][index]
        return assignments_by_interval

    def _assignment_candidates_for_interval(
        self,
        active_requests: list[ShiftRequest],
        positions_by_code: dict[str, Position],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> list[dict[UUID, str]]:
        required_codes = target_position_codes(len(active_requests), positions_by_code)
        required_counts = Counter(required_codes)
        candidates: list[dict[UUID, str]] = []
        staff_ids = [request.staff_member_id for request in active_requests]

        max_candidates = 50_000

        def search(index: int, remaining: Counter[str], assignment: dict[UUID, str]) -> None:
            if len(candidates) >= max_candidates:
                return
            if index == len(staff_ids):
                candidates.append(dict(assignment))
                return
            staff_member_id = staff_ids[index]
            for position_code in sorted(remaining, key=position_priority_index):
                if remaining[position_code] <= 0:
                    continue
                position = positions_by_code.get(position_code)
                if position is None or not self._staff_can_cover_position(
                    staff_member_id,
                    position.id,
                    skills,
                    staff_skills,
                ):
                    continue
                assignment[staff_member_id] = position_code
                remaining[position_code] -= 1
                search(index + 1, remaining, assignment)
                remaining[position_code] += 1
                assignment.pop(staff_member_id, None)

        search(0, required_counts, {})
        return candidates

    def _fallback_assignment_candidates_for_interval(
        self,
        active_requests: list[ShiftRequest],
        positions_by_code: dict[str, Position],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> list[dict[UUID, str]]:
        assignment: dict[UUID, str] = {}
        for request in active_requests:
            for position_code in ["B", "C", "F", "S"]:
                position = positions_by_code.get(position_code)
                if position is None:
                    continue
                if self._staff_can_cover_position(
                    request.staff_member_id,
                    position.id,
                    skills,
                    staff_skills,
                ):
                    assignment[request.staff_member_id] = position_code
                    break
        return [assignment] if assignment else []

    def _assignment_transition_score(
        self,
        candidate: dict[UUID, str],
        previous_codes: dict[UUID, str],
        previous_started: dict[UUID, int],
        interval_start_minute: int,
        interval_end_minute: int,
    ) -> tuple[int, dict[UUID, int]]:
        score = 0
        next_started = dict(previous_started)
        changed_staff_count = 0
        interval_minutes = interval_end_minute - interval_start_minute
        for staff_member_id, position_code in candidate.items():
            previous_code = previous_codes.get(staff_member_id)
            started_minute = previous_started.get(staff_member_id, interval_start_minute)
            elapsed = interval_start_minute - started_minute
            if previous_code == position_code:
                projected_elapsed = interval_end_minute - started_minute
                score += same_position_duration_penalty(position_code, projected_elapsed)
                continue
            if previous_code is None:
                next_started[staff_member_id] = interval_start_minute
                continue
            changed_staff_count += 1
            score += position_change_penalty(elapsed)
            if interval_minutes < MIN_POSITION_BLOCK_MINUTES:
                score += short_interval_change_penalty(interval_minutes)
            next_started[staff_member_id] = interval_start_minute
        if changed_staff_count > 1:
            score += (changed_staff_count - 1) * 1_500
        return score, next_started

    def _assign_interval_positions(
        self,
        active_requests: list[ShiftRequest],
        positions_by_code: dict[str, Position],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
        last_position_by_staff: dict[UUID, str],
        position_started_minute_by_staff: dict[UUID, int],
        interval_start_minute: int,
    ) -> dict[UUID, str]:
        active_requests = [
            request
            for request in active_requests
        ]
        required_codes = target_position_codes(len(active_requests), positions_by_code)
        assignments: dict[UUID, str] = {}
        remaining_required_codes = list(required_codes)

        for request in active_requests:
            previous_code = last_position_by_staff.get(request.staff_member_id)
            if (
                previous_code in remaining_required_codes
                and self._should_keep_position(
                    request.staff_member_id,
                    position_started_minute_by_staff,
                    interval_start_minute,
                )
                and self._staff_can_cover_position(
                    request.staff_member_id,
                    positions_by_code[previous_code].id,
                    skills,
                    staff_skills,
                )
            ):
                assignments[request.staff_member_id] = previous_code
                remaining_required_codes.remove(previous_code)

        for position_code in remaining_required_codes:
            staff_member_id = self._choose_staff_for_position(
                active_requests,
                position_code,
                positions_by_code,
                skills,
                staff_skills,
                assignments,
                last_position_by_staff,
                position_started_minute_by_staff,
                interval_start_minute,
            )
            if staff_member_id is not None:
                assignments[staff_member_id] = position_code

        fallback_codes = ["B", "C", "F", "S"]
        for request in active_requests:
            if request.staff_member_id in assignments:
                continue
            previous_code = last_position_by_staff.get(request.staff_member_id)
            if (
                previous_code in fallback_codes
                and previous_code in positions_by_code
                and self._should_keep_position(
                    request.staff_member_id,
                    position_started_minute_by_staff,
                    interval_start_minute,
                )
                and self._staff_can_cover_position(
                    request.staff_member_id,
                    positions_by_code[previous_code].id,
                    skills,
                    staff_skills,
                )
            ):
                assignments[request.staff_member_id] = previous_code
                continue
            for position_code in fallback_codes:
                if position_code not in positions_by_code:
                    continue
                if not self._staff_can_cover_position(
                    request.staff_member_id,
                    positions_by_code[position_code].id,
                    skills,
                    staff_skills,
                ):
                    continue
                assignments[request.staff_member_id] = position_code
                break
            if request.staff_member_id not in assignments:
                for position_code in fallback_codes:
                    if position_code in positions_by_code and self._staff_can_cover_position(
                        request.staff_member_id,
                        positions_by_code[position_code].id,
                        skills,
                        staff_skills,
                    ):
                        assignments[request.staff_member_id] = position_code
                        break
        return assignments

    def _should_keep_position(
        self,
        staff_member_id: UUID,
        position_started_minute_by_staff: dict[UUID, int],
        interval_start_minute: int,
    ) -> bool:
        started_minute = position_started_minute_by_staff.get(staff_member_id)
        if started_minute is None:
            return False
        return interval_start_minute - started_minute < 120

    def _choose_staff_for_position(
        self,
        active_requests: list[ShiftRequest],
        position_code: str,
        positions_by_code: dict[str, Position],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
        assignments: dict[UUID, str],
        last_position_by_staff: dict[UUID, str],
        position_started_minute_by_staff: dict[UUID, int],
        interval_start_minute: int,
    ) -> UUID | None:
        position = positions_by_code.get(position_code)
        if position is None:
            return None
        candidates = [
            request.staff_member_id
            for request in active_requests
            if request.staff_member_id not in assignments
            and self._staff_can_cover_position(
                request.staff_member_id,
                position.id,
                skills,
                staff_skills,
            )
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda staff_member_id: rotation_candidate_score(
                staff_member_id,
                position_code,
                last_position_by_staff,
                position_started_minute_by_staff,
                interval_start_minute,
            ),
        )

    def _insert_break_segments(
        self,
        planned: dict[UUID, list[dict]],
        request_rows: list[ShiftRequest],
        positions_by_code: dict[str, Position],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> None:
        for request in sorted(
            request_rows,
            key=lambda item: (
                minutes_between(item.start_time, item.end_time),
                item.start_time,
            ),
            reverse=True,
        ):
            shift_minutes = minutes_between(request.start_time, request.end_time)
            break_plan = self._break_plan_for_shift(shift_minutes)
            if not break_plan:
                continue
            shift_start_minute = time_to_minutes(request.start_time)
            for break_minutes, preferred_ratio in break_plan:
                preferred_center = shift_start_minute + round(shift_minutes * preferred_ratio)
                break_window = self._choose_break_window(
                    planned,
                    request,
                    break_minutes,
                    preferred_center,
                    positions_by_code,
                    skills,
                    staff_skills,
                )
                if break_window is None:
                    continue
                self._replace_with_special_segment(
                    planned[request.staff_member_id],
                    break_window[0],
                    break_window[1],
                    {
                        "segment_type": "BREAK",
                        "position_id": None,
                        "task_type_id": None,
                    },
                )

    def _break_plan_for_shift(self, shift_minutes: int) -> list[tuple[int, float]]:
        if shift_minutes <= 210:
            return []
        if shift_minutes < 360:
            return [(15, 0.5)]
        return [(15, 0.35), (30, 0.65)]

    def _choose_break_window(
        self,
        planned: dict[UUID, list[dict]],
        request: ShiftRequest,
        break_minutes: int,
        preferred_center: int,
        positions_by_code: dict[str, Position],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> tuple[time, time] | None:
        work_segments = [
            segment
            for segment in planned[request.staff_member_id]
            if segment["segment_type"] == "WORK"
            and minutes_between(segment["start_time"], segment["end_time"]) >= break_minutes + 60
        ]
        if not work_segments:
            return None
        candidates: list[tuple[int, time, time]] = []
        for segment in work_segments:
            start_minute = time_to_minutes(segment["start_time"])
            latest_start = time_to_minutes(segment["end_time"]) - break_minutes
            cursor = round((start_minute + (latest_start - start_minute) // 2) / 15) * 15
            preferred_start = round((preferred_center - break_minutes // 2) / 15) * 15
            candidate_starts = [
                preferred_start,
                preferred_start - 30,
                preferred_start + 30,
                cursor,
                cursor - 30,
                cursor + 30,
                start_minute,
                latest_start,
            ]
            for candidate_start in candidate_starts:
                candidate_start = max(start_minute, min(latest_start, candidate_start))
                candidate_start = round(candidate_start / 15) * 15
                candidate_end = candidate_start + break_minutes
                segment_end = time_to_minutes(segment["end_time"])
                if candidate_start < start_minute or candidate_end > segment_end:
                    continue
                break_start = add_minutes(time(0, 0), candidate_start)
                break_end = add_minutes(time(0, 0), candidate_end)
                if self._break_too_close_to_existing(
                    planned[request.staff_member_id],
                    break_start,
                    break_end,
                ):
                    continue
                if self._break_overlaps_another_staff(
                    planned,
                    request.staff_member_id,
                    break_start,
                    break_end,
                ):
                    continue
                if not self._break_keeps_minimum_position_coverage(
                    planned,
                    request.staff_member_id,
                    break_start,
                    break_end,
                    positions_by_code,
                    skills,
                    staff_skills,
                ):
                    continue
                score = self._break_window_score(
                    planned,
                    request.staff_member_id,
                    break_start,
                    break_end,
                    preferred_center,
                )
                score += work_fragment_penalty_after_special_segment(
                    segment,
                    break_start,
                    break_end,
                )
                candidates.append((score, break_start, break_end))
        if not candidates:
            return None
        _, break_start, break_end = min(candidates, key=lambda item: item[0])
        return break_start, break_end

    def _break_too_close_to_existing(
        self,
        segments: list[dict],
        break_start: time,
        break_end: time,
    ) -> bool:
        minimum_gap_minutes = 60
        start_minute = time_to_minutes(break_start)
        end_minute = time_to_minutes(break_end)
        for segment in segments:
            if segment["segment_type"] != "BREAK":
                continue
            existing_start = time_to_minutes(segment["start_time"])
            existing_end = time_to_minutes(segment["end_time"])
            gap = min(abs(start_minute - existing_end), abs(existing_start - end_minute))
            if gap < minimum_gap_minutes:
                return True
        return False

    def _break_overlaps_another_staff(
        self,
        planned: dict[UUID, list[dict]],
        staff_member_id: UUID,
        break_start: time,
        break_end: time,
    ) -> bool:
        return any(
            current_staff_id != staff_member_id
            and segment["segment_type"] == "BREAK"
            and overlaps(segment["start_time"], segment["end_time"], break_start, break_end)
            for current_staff_id, segments in planned.items()
            for segment in segments
        )

    def _break_keeps_minimum_position_coverage(
        self,
        planned: dict[UUID, list[dict]],
        staff_member_id: UUID,
        break_start: time,
        break_end: time,
        positions_by_code: dict[str, Position],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> bool:
        if "B" not in positions_by_code or "C" not in positions_by_code:
            return True
        start_minute = time_to_minutes(break_start)
        end_minute = time_to_minutes(break_end)
        for minute in range(start_minute, end_minute, 15):
            current_time = add_minutes(time(0, 0), minute)
            active_staff_ids: list[UUID] = []
            for current_staff_id, segments in planned.items():
                if current_staff_id == staff_member_id:
                    continue
                for segment in segments:
                    if not (segment["start_time"] <= current_time < segment["end_time"]):
                        continue
                    if segment["segment_type"] != "WORK":
                        continue
                    active_staff_ids.append(current_staff_id)
                    break
            if len(active_staff_ids) < 2:
                return False
            if not self._remaining_staff_can_cover_required_positions(
                active_staff_ids,
                ["B", "C"],
                positions_by_code,
                skills,
                staff_skills,
            ):
                return False
        return True

    def _remaining_staff_can_cover_required_positions(
        self,
        staff_ids: list[UUID],
        required_codes: list[str],
        positions_by_code: dict[str, Position],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> bool:
        assigned_staff_ids: set[UUID] = set()
        for required_code in required_codes:
            position = positions_by_code[required_code]
            candidate = next(
                (
                    staff_id
                    for staff_id in staff_ids
                    if staff_id not in assigned_staff_ids
                    and self._staff_can_cover_position(
                        staff_id,
                        position.id,
                        skills,
                        staff_skills,
                    )
                ),
                None,
            )
            if candidate is None:
                return False
            assigned_staff_ids.add(candidate)
        return True

    def _break_window_score(
        self,
        planned: dict[UUID, list[dict]],
        staff_member_id: UUID,
        break_start: time,
        break_end: time,
        preferred_center: int,
    ) -> int:
        start_minute = time_to_minutes(break_start)
        end_minute = time_to_minutes(break_end)
        score = abs(((start_minute + end_minute) // 2) - preferred_center)
        for minute in range(start_minute, end_minute, 15):
            current_time = add_minutes(time(0, 0), minute)
            active_positions = set()
            simultaneous_breaks = 0
            for current_staff_id, segments in planned.items():
                for segment in segments:
                    if not (segment["start_time"] <= current_time < segment["end_time"]):
                        continue
                    if current_staff_id == staff_member_id:
                        simultaneous_breaks += 1
                        continue
                    if segment["segment_type"] == "BREAK":
                        simultaneous_breaks += 1
                    elif segment["segment_type"] == "WORK":
                        position_code = segment.get("position_code")
                        if position_code:
                            active_positions.add(position_code)
            score += simultaneous_breaks * 500
            if "B" not in active_positions:
                score += 1000
            if "C" not in active_positions:
                score += 1000
        return score

    def _insert_deposit_segment(
        self,
        planned: dict[UUID, list[dict]],
        target_date: date,
        request_rows: list[ShiftRequest],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
        task_types: list[TaskType],
    ) -> None:
        _ = target_date
        m_task_type = next((task_type for task_type in task_types if task_type.code == "M"), None)
        if m_task_type is None:
            return
        deposit_start = time(10, 0)
        deposit_end = time(10, 30)
        candidates = [
            request.staff_member_id
            for request in request_rows
            if request.start_time <= deposit_start
            and deposit_end <= request.end_time
            and self._staff_can_cover_target(
                request.staff_member_id,
                None,
                m_task_type.id,
                skills,
                staff_skills,
            )
        ]
        if not candidates:
            return
        selected_staff_id = min(
            candidates,
            key=lambda staff_member_id: deposit_candidate_coverage_cost(
                planned,
                staff_member_id,
                deposit_start,
                deposit_end,
            ),
        )
        self._replace_with_special_segment(
            planned[selected_staff_id],
            deposit_start,
            deposit_end,
            {
                "segment_type": "TASK",
                "position_id": None,
                "task_type_id": m_task_type.id,
            },
        )

    def _replace_with_special_segment(
        self,
        segments: list[dict],
        special_start: time,
        special_end: time,
        special_payload: dict,
    ) -> None:
        replacement: list[dict] = []
        inserted = False
        for segment in segments:
            if (
                segment["segment_type"] != "WORK"
                or not overlaps(
                    segment["start_time"],
                    segment["end_time"],
                    special_start,
                    special_end,
                )
            ):
                replacement.append(segment)
                continue
            if segment["start_time"] < special_start:
                replacement.append({**segment, "end_time": special_start})
            replacement.append(
                {
                    "start_time": special_start,
                    "end_time": special_end,
                    **special_payload,
                }
            )
            inserted = True
            if special_end < segment["end_time"]:
                replacement.append({**segment, "start_time": special_end})
        if inserted:
            segments[:] = sorted(replacement, key=lambda item: item["start_time"])

    def _ensure_break_coverage_positions(
        self,
        planned: dict[UUID, list[dict]],
        positions_by_code: dict[str, Position],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> None:
        if "B" not in positions_by_code or "C" not in positions_by_code:
            return
        all_minutes = [
            minute
            for segments in planned.values()
            for segment in segments
            for minute in (
                time_to_minutes(segment["start_time"]),
                time_to_minutes(segment["end_time"]),
            )
        ]
        if not all_minutes:
            return
        replacement_windows: dict[tuple[UUID, int], list[tuple[time, time, Position, str]]] = {}
        segments_by_key: dict[tuple[UUID, int], dict] = {}

        for minute in range(min(all_minutes), max(all_minutes), 15):
            start_time = add_minutes(time(0, 0), minute)
            end_time = add_minutes(time(0, 0), minute + 15)
            active_work = self._active_work_segments(planned, start_time, end_time)
            assignments = self._balanced_position_assignments(
                active_work,
                positions_by_code,
                skills,
                staff_skills,
            )
            for index, (staff_member_id, segment) in enumerate(active_work):
                position_code = assignments.get(index)
                if not position_code or position_code == segment.get("position_code"):
                    continue
                key = (staff_member_id, id(segment))
                segments_by_key[key] = segment
                window_start, window_end = coverage_reassignment_window(
                    segment,
                    start_time,
                    end_time,
                )
                replacement_windows.setdefault(key, []).append(
                    (
                        window_start,
                        window_end,
                        positions_by_code[position_code],
                        position_code,
                    )
                )

        for (staff_member_id, segment_key), windows in replacement_windows.items():
            target_segment = segments_by_key[(staff_member_id, segment_key)]
            self._replace_work_position_windows(
                planned[staff_member_id],
                target_segment,
                windows,
            )

    def _balanced_position_assignments(
        self,
        active_work: list[tuple[UUID, dict]],
        positions_by_code: dict[str, Position],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> dict[int, str]:
        if len(active_work) < 2:
            return {}
        required_codes = target_position_codes(len(active_work), positions_by_code)
        required_counts = Counter(required_codes)
        active_counts = Counter(
            segment.get("position_code")
            for _, segment in active_work
            if segment.get("position_code")
        )
        relevant_codes = set(required_counts) | {
            code for code in active_counts if code in {"B", "C", "F", "S"}
        }
        if all(active_counts[code] == required_counts[code] for code in relevant_codes):
            return {}

        position_slots = sorted(
            required_codes,
            key=lambda code: (
                self._candidate_count_for_position(
                    active_work,
                    positions_by_code[code],
                    skills,
                    staff_skills,
                ),
                position_priority_index(code),
            ),
        )
        result = self._best_position_assignment(
            active_work,
            position_slots,
            positions_by_code,
            skills,
            staff_skills,
            required_counts,
            active_counts,
        )
        return result or {}

    def _candidate_count_for_position(
        self,
        active_work: list[tuple[UUID, dict]],
        position: Position,
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> int:
        return sum(
            1
            for staff_member_id, _ in active_work
            if self._staff_can_cover_position(
                staff_member_id,
                position.id,
                skills,
                staff_skills,
            )
        )

    def _best_position_assignment(
        self,
        active_work: list[tuple[UUID, dict]],
        position_slots: list[str],
        positions_by_code: dict[str, Position],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
        required_counts: Counter,
        active_counts: Counter,
    ) -> dict[int, str] | None:
        @lru_cache(maxsize=None)
        def search(
            slot_index: int,
            assigned_mask: int,
        ) -> tuple[int, tuple[tuple[int, str], ...]] | None:
            if slot_index == len(position_slots):
                return (0, ())
            position_code = position_slots[slot_index]
            position = positions_by_code[position_code]
            best: tuple[int, tuple[tuple[int, str], ...]] | None = None

            for index, (staff_member_id, segment) in enumerate(active_work):
                if assigned_mask & (1 << index):
                    continue
                if not self._staff_can_cover_position(
                    staff_member_id,
                    position.id,
                    skills,
                    staff_skills,
                ):
                    continue
                next_result = search(slot_index + 1, assigned_mask | (1 << index))
                if next_result is None:
                    continue
                next_score, next_assignment = next_result
                current_score = balanced_assignment_cost(
                    segment,
                    position_code,
                    required_counts,
                    active_counts,
                )
                candidate = (
                    current_score + next_score,
                    ((index, position_code), *next_assignment),
                )
                if best is None or candidate[0] < best[0]:
                    best = candidate
            return best

        result = search(0, 0)
        if result is None:
            return None
        return dict(result[1])

    def _active_work_segments(
        self,
        planned: dict[UUID, list[dict]],
        start_time: time,
        end_time: time,
    ) -> list[tuple[UUID, dict]]:
        return [
            (staff_member_id, segment)
            for staff_member_id, segments in planned.items()
            for segment in segments
            if segment["segment_type"] == "WORK"
            and segment["start_time"] <= start_time
            and end_time <= segment["end_time"]
        ]

    def _enforce_exact_position_mix(
        self,
        planned: dict[UUID, list[dict]],
        positions_by_code: dict[str, Position],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> None:
        boundaries = sorted(
            {
                boundary
                for segments in planned.values()
                for segment in segments
                for boundary in (segment["start_time"], segment["end_time"])
            }
        )
        intervals: list[tuple[time, time, list[tuple[UUID, dict]]]] = []
        for start_time, end_time in zip(boundaries, boundaries[1:]):
            active_work = self._active_work_segments(planned, start_time, end_time)
            if len(active_work) < 2:
                continue
            intervals.append((start_time, end_time, active_work))
        if not intervals:
            return

        paths: list[tuple[int, dict[UUID, str], dict[UUID, int], list[dict[UUID, str]]]] = [
            (0, {}, {}, [])
        ]
        for start_time, end_time, active_work in intervals:
            start_minute = time_to_minutes(start_time)
            candidates = self._exact_mix_candidates_for_active_work(
                active_work,
                positions_by_code,
                skills,
                staff_skills,
            )
            if not candidates:
                candidates = [
                    {
                        staff_member_id: segment.get("position_code")
                        for staff_member_id, segment in active_work
                        if segment.get("position_code") in {"B", "C", "F", "S"}
                    }
                ]
            next_paths: list[
                tuple[int, dict[UUID, str], dict[UUID, int], list[dict[UUID, str]]]
            ] = []
            for score, previous_codes, previous_started, history in paths:
                for candidate in candidates:
                    transition_score, next_started = self._assignment_transition_score(
                        candidate,
                        previous_codes,
                        previous_started,
                        start_minute,
                        time_to_minutes(end_time),
                    )
                    next_paths.append(
                        (
                            score + transition_score,
                            {**previous_codes, **candidate},
                            next_started,
                            [*history, candidate],
                        )
                    )
            paths = sorted(next_paths, key=lambda item: item[0])[:240]

        if not paths:
            return
        best_history = min(paths, key=lambda item: item[0])[3]
        replacement_windows: dict[tuple[UUID, int], list[tuple[time, time, Position, str]]] = {}
        segments_by_key: dict[tuple[UUID, int], dict] = {}
        for (start_time, end_time, active_work), assignment in zip(intervals, best_history):
            for staff_member_id, segment in active_work:
                position_code = assignment.get(staff_member_id)
                if not position_code or position_code == segment.get("position_code"):
                    continue
                position = positions_by_code.get(position_code)
                if position is None:
                    continue
                key = (staff_member_id, id(segment))
                segments_by_key[key] = segment
                replacement_windows.setdefault(key, []).append(
                    (start_time, end_time, position, position_code)
                )

        for (staff_member_id, segment_key), windows in replacement_windows.items():
            target_segment = segments_by_key[(staff_member_id, segment_key)]
            self._replace_work_position_windows(
                planned[staff_member_id],
                target_segment,
                windows,
            )
        for segments in planned.values():
            self._merge_adjacent_planned_segments(segments)

    def _exact_mix_candidates_for_active_work(
        self,
        active_work: list[tuple[UUID, dict]],
        positions_by_code: dict[str, Position],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> list[dict[UUID, str]]:
        required_codes = target_position_codes(len(active_work), positions_by_code)
        required_counts = Counter(required_codes)
        staff_ids = [staff_member_id for staff_member_id, _ in active_work]
        candidates: list[dict[UUID, str]] = []

        def search(index: int, remaining: Counter[str], assignment: dict[UUID, str]) -> None:
            if index == len(staff_ids):
                if all(count == 0 for count in remaining.values()):
                    candidates.append(dict(assignment))
                return
            staff_member_id = staff_ids[index]
            for position_code in sorted(remaining, key=position_priority_index):
                if remaining[position_code] <= 0:
                    continue
                position = positions_by_code.get(position_code)
                if position is None:
                    continue
                if not self._staff_can_cover_position(
                    staff_member_id,
                    position.id,
                    skills,
                    staff_skills,
                ):
                    continue
                assignment[staff_member_id] = position_code
                remaining[position_code] -= 1
                search(index + 1, remaining, assignment)
                remaining[position_code] += 1
                assignment.pop(staff_member_id, None)

        search(0, required_counts, {})
        return candidates

    def _coverage_reassignment_candidate(
        self,
        active_work: list[tuple[UUID, dict]],
        required_code: str,
        required_counts: Counter,
        active_counts: Counter,
        positions_by_code: dict[str, Position],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> tuple[UUID, dict] | None:
        position = positions_by_code[required_code]
        candidates = sorted(
            active_work,
            key=lambda item: coverage_reassignment_donor_score(
                item[1],
                required_counts,
                active_counts,
            ),
        )
        for staff_member_id, segment in candidates:
            if segment.get("position_code") == required_code:
                continue
            if (
                segment.get("position_code") in {"B", "C", "F", "S"}
                and active_counts[segment.get("position_code")]
                <= required_counts[segment.get("position_code")]
            ):
                continue
            if self._staff_can_cover_position(
                staff_member_id,
                position.id,
                skills,
                staff_skills,
            ):
                return staff_member_id, segment
        return None

    def _replace_work_position_segment(
        self,
        segments: list[dict],
        target_segment: dict,
        start_time: time,
        end_time: time,
        position: Position,
        position_code: str,
    ) -> None:
        replacement: list[dict] = []
        for segment in segments:
            if segment is not target_segment:
                replacement.append(segment)
                continue
            if segment["start_time"] < start_time:
                replacement.append({**segment, "end_time": start_time})
            replacement.append(
                {
                    **segment,
                    "start_time": start_time,
                    "end_time": end_time,
                    "position_code": position_code,
                    "position_id": position.id,
                }
            )
            if end_time < segment["end_time"]:
                replacement.append({**segment, "start_time": end_time})
        segments[:] = sorted(replacement, key=lambda item: item["start_time"])

    def _replace_work_position_windows(
        self,
        segments: list[dict],
        target_segment: dict,
        windows: list[tuple[time, time, Position, str]],
    ) -> None:
        merged_windows: list[tuple[time, time, Position, str]] = []
        for start_time, end_time, position, position_code in sorted(
            windows,
            key=lambda item: item[0],
        ):
            previous = merged_windows[-1] if merged_windows else None
            if (
                previous is not None
                and start_time <= previous[1]
                and previous[3] == position_code
                and previous[2].id == position.id
            ):
                merged_windows[-1] = (
                    previous[0],
                    max(previous[1], end_time),
                    position,
                    position_code,
                )
                continue
            merged_windows.append((start_time, end_time, position, position_code))

        replacement: list[dict] = []
        for segment in segments:
            if segment is not target_segment:
                replacement.append(segment)
                continue
            cursor = segment["start_time"]
            for start_time, end_time, position, position_code in merged_windows:
                if start_time < cursor:
                    start_time = cursor
                if end_time <= start_time:
                    continue
                if minutes_between(start_time, end_time) < MIN_POSITION_BLOCK_MINUTES:
                    end_time = min(
                        segment["end_time"],
                        add_minutes(start_time, MIN_POSITION_BLOCK_MINUTES),
                    )
                    if end_time <= start_time:
                        continue
                if cursor < start_time:
                    replacement.append({**segment, "start_time": cursor, "end_time": start_time})
                replacement.append(
                    {
                        **segment,
                        "start_time": start_time,
                        "end_time": end_time,
                        "position_code": position_code,
                        "position_id": position.id,
                    }
                )
                cursor = end_time
            if cursor < segment["end_time"]:
                replacement.append(
                    {
                        **segment,
                        "start_time": cursor,
                        "end_time": segment["end_time"],
                    }
                )
        segments[:] = sorted(replacement, key=lambda item: item["start_time"])

    def _merge_adjacent_planned_segments(self, segments: list[dict]) -> None:
        if not segments:
            return
        merged: list[dict] = []
        for segment in sorted(segments, key=lambda item: item["start_time"]):
            previous = merged[-1] if merged else None
            if (
                previous is not None
                and previous["end_time"] == segment["start_time"]
                and previous["segment_type"] == segment["segment_type"]
                and previous.get("position_id") == segment.get("position_id")
                and previous.get("task_type_id") == segment.get("task_type_id")
                and previous.get("label") == segment.get("label")
            ):
                previous["end_time"] = segment["end_time"]
                continue
            merged.append(segment)
        segments[:] = merged

    def _smooth_short_work_fragments(
        self,
        segments: list[dict],
        *,
        skip_break_adjacent: bool = False,
        require_same_work_neighbors: bool = False,
    ) -> None:
        minimum_minutes = 60
        while True:
            sorted_segments = sorted(segments, key=lambda item: item["start_time"])
            changed = False
            for index, segment in enumerate(sorted_segments):
                if segment["segment_type"] != "WORK":
                    continue
                duration = minutes_between(segment["start_time"], segment["end_time"])
                if duration >= minimum_minutes:
                    continue

                previous_segment = sorted_segments[index - 1] if index > 0 else None
                next_segment = (
                    sorted_segments[index + 1] if index + 1 < len(sorted_segments) else None
                )
                if skip_break_adjacent and (
                    (
                        previous_segment is not None
                        and previous_segment["segment_type"] == "BREAK"
                        and previous_segment["end_time"] == segment["start_time"]
                    )
                    or (
                        next_segment is not None
                        and next_segment["segment_type"] == "BREAK"
                        and segment["end_time"] == next_segment["start_time"]
                    )
                ):
                    continue
                previous_is_work = (
                    previous_segment is not None
                    and previous_segment["segment_type"] == "WORK"
                    and previous_segment["end_time"] == segment["start_time"]
                )
                next_is_work = (
                    next_segment is not None
                    and next_segment["segment_type"] == "WORK"
                    and segment["end_time"] == next_segment["start_time"]
                )
                if require_same_work_neighbors and not (
                    previous_is_work
                    and next_is_work
                    and previous_segment.get("position_id") == next_segment.get("position_id")
                ):
                    continue
                if not previous_is_work and not next_is_work:
                    continue

                merge_to_previous = False
                if previous_is_work and next_is_work:
                    previous_duration = minutes_between(
                        previous_segment["start_time"],
                        previous_segment["end_time"],
                    )
                    next_duration = minutes_between(
                        next_segment["start_time"],
                        next_segment["end_time"],
                    )
                    merge_to_previous = previous_duration >= next_duration
                elif previous_is_work:
                    merge_to_previous = True

                if merge_to_previous and previous_segment is not None:
                    merged_minutes = minutes_between(
                        previous_segment["start_time"],
                        segment["end_time"],
                    )
                    if merged_minutes <= max_work_segment_minutes(previous_segment):
                        previous_segment["end_time"] = segment["end_time"]
                        sorted_segments.pop(index)
                        changed = True
                        break
                elif next_segment is not None:
                    merged_minutes = minutes_between(
                        segment["start_time"],
                        next_segment["end_time"],
                    )
                    if merged_minutes <= max_work_segment_minutes(next_segment):
                        next_segment["start_time"] = segment["start_time"]
                        sorted_segments.pop(index)
                        changed = True
                        break
            segments[:] = sorted(sorted_segments, key=lambda item: item["start_time"])
            if not changed:
                return

    def _sync_planned_position_codes(
        self,
        planned: dict[UUID, list[dict]],
        positions_by_code: dict[str, Position],
    ) -> None:
        code_by_position_id = {
            position.id: code
            for code, position in positions_by_code.items()
        }
        for segments in planned.values():
            for segment in segments:
                if segment["segment_type"] != "WORK":
                    continue
                position_code = code_by_position_id.get(segment.get("position_id"))
                if position_code is not None:
                    segment["position_code"] = position_code

    def _normalize_b_lane_labels(self, planned: dict[UUID, list[dict]]) -> None:
        for segments in planned.values():
            for segment in segments:
                if segment["segment_type"] == "WORK":
                    segment["label"] = None

        for staff_member_id, segments in planned.items():
            replacement: list[dict] = []
            for segment in sorted(segments, key=lambda item: item["start_time"]):
                if segment["segment_type"] != "WORK" or segment.get("position_code") != "B":
                    replacement.append(segment)
                    continue
                replacement.extend(
                    self._split_b_lane_label_segments(planned, staff_member_id, segment)
                )
            planned[staff_member_id] = replacement

    def _split_b_lane_label_segments(
        self,
        planned: dict[UUID, list[dict]],
        staff_member_id: UUID,
        segment: dict,
    ) -> list[dict]:
        pieces: list[dict] = []
        start_minute = time_to_minutes(segment["start_time"])
        end_minute = time_to_minutes(segment["end_time"])
        for minute in range(start_minute, end_minute, 15):
            slot_start = add_minutes(time(0, 0), minute)
            slot_end = add_minutes(time(0, 0), min(minute + 15, end_minute))
            label = self._b_lane_label_for_slot(
                planned,
                staff_member_id,
                segment,
                slot_start,
                slot_end,
            )
            piece = {**segment, "start_time": slot_start, "end_time": slot_end, "label": label}
            previous = pieces[-1] if pieces else None
            if previous is not None and previous.get("label") == label:
                previous["end_time"] = slot_end
            else:
                pieces.append(piece)
        return pieces

    def _b_lane_label_for_slot(
        self,
        planned: dict[UUID, list[dict]],
        staff_member_id: UUID,
        segment: dict,
        start_time: time,
        end_time: time,
    ) -> str | None:
        active_work = self._active_work_segments(planned, start_time, end_time)
        if len(active_work) < 5:
            return None
        active_b = [
            (active_staff_id, active_segment)
            for active_staff_id, active_segment in active_work
            if active_segment.get("position_code") == "B"
        ]
        if len(active_b) < 2:
            return None
        active_b.sort(key=lambda item: str(item[0]))
        for index, (active_staff_id, active_segment) in enumerate(active_b):
            if active_staff_id == staff_member_id and active_segment is segment:
                return "ST" if index == 0 else "SH"
        return None

    def _absorb_short_work_segments(self, segments: list[dict]) -> None:
        minimum_minutes = 60
        while True:
            sorted_segments = sorted(segments, key=lambda item: item["start_time"])
            changed = False
            for index, segment in enumerate(sorted_segments):
                if segment["segment_type"] != "WORK":
                    continue
                if minutes_between(segment["start_time"], segment["end_time"]) >= minimum_minutes:
                    continue
                previous_segment = sorted_segments[index - 1] if index > 0 else None
                next_segment = (
                    sorted_segments[index + 1] if index + 1 < len(sorted_segments) else None
                )
                previous_is_adjacent_work = (
                    previous_segment is not None
                    and previous_segment["segment_type"] == "WORK"
                    and previous_segment["end_time"] == segment["start_time"]
                )
                next_is_adjacent_work = (
                    next_segment is not None
                    and next_segment["segment_type"] == "WORK"
                    and segment["end_time"] == next_segment["start_time"]
                )
                if previous_is_adjacent_work:
                    merged_minutes = minutes_between(
                        previous_segment["start_time"],
                        segment["end_time"],
                    )
                    if merged_minutes <= max_work_segment_minutes(previous_segment):
                        previous_segment["end_time"] = segment["end_time"]
                        sorted_segments.pop(index)
                        changed = True
                        break
                if next_is_adjacent_work:
                    merged_minutes = minutes_between(
                        segment["start_time"],
                        next_segment["end_time"],
                    )
                    if merged_minutes <= max_work_segment_minutes(next_segment):
                        next_segment["start_time"] = segment["start_time"]
                        sorted_segments.pop(index)
                        changed = True
                        break
            segments[:] = sorted(sorted_segments, key=lambda item: item["start_time"])
            if not changed:
                return

    def _split_overlong_work_segments(
        self,
        staff_member_id: UUID,
        segments: list[dict],
        positions_by_code: dict[str, Position],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> None:
        replacement: list[dict] = []
        changed = False
        for segment in sorted(segments, key=lambda item: item["start_time"]):
            if (
                segment["segment_type"] != "WORK"
                or minutes_between(segment["start_time"], segment["end_time"])
                <= SOFT_MAX_POSITION_BLOCK_MINUTES
            ):
                replacement.append(segment)
                continue

            alternate_position = self._alternate_position_for_overlong_segment(
                staff_member_id,
                segment,
                positions_by_code,
                skills,
                staff_skills,
            )
            if alternate_position is None:
                replacement.append(segment)
                continue

            split_minute = min(
                time_to_minutes(segment["start_time"]) + IDEAL_POSITION_BLOCK_MINUTES,
                time_to_minutes(segment["end_time"]) - MIN_POSITION_BLOCK_MINUTES,
            )
            if split_minute <= time_to_minutes(segment["start_time"]):
                replacement.append(segment)
                continue

            split_time = add_minutes(time(0, 0), split_minute)
            replacement.append({**segment, "end_time": split_time})
            replacement.append(
                {
                    **segment,
                    "start_time": split_time,
                    "position_id": alternate_position.id,
                    "position_code": alternate_position.code,
                    "label": None,
                }
            )
            changed = True
        if changed:
            segments[:] = sorted(replacement, key=lambda item: item["start_time"])

    def _alternate_position_for_overlong_segment(
        self,
        staff_member_id: UUID,
        segment: dict,
        positions_by_code: dict[str, Position],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> Position | None:
        current_code = segment.get("position_code")
        preferred_codes_by_current = {
            "C": ["B", "F", "S"],
            "B": ["C", "F", "S"],
            "F": ["C", "B", "S"],
            "S": ["F", "C", "B"],
        }
        for position_code in preferred_codes_by_current.get(
            current_code,
            ["C", "B", "F", "S"],
        ):
            position = positions_by_code.get(position_code)
            if position is None or position_code == current_code:
                continue
            if self._staff_can_cover_position(
                staff_member_id,
                position.id,
                skills,
                staff_skills,
            ):
                return position
        return None

    def _build_deposit_task_changes(
        self,
        scope: OptimizationScopePayload,
        shifts: list[WorkShift],
        segments: list[ShiftSegment],
        requirements: list[ShiftRequirement],
        requests: list[ShiftRequest],
        staff_members: list[StaffMember],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
        task_types: list[TaskType],
        store: Store | None,
    ) -> list[SolverChange]:
        m_task_type_ids = {task_type.id for task_type in task_types if task_type.code == "M"}
        if not m_task_type_ids:
            m_task_type_ids = {
                skill.task_type_id
                for skill in skills
                if skill.code == "M" and skill.task_type_id
            }
        deposit_requirements = [
            requirement
            for requirement in requirements
            if requirement.requirement_type == "TASK"
            and requirement.task_type_id in m_task_type_ids
            and self._requirement_in_scope(requirement, scope)
        ]
        if not deposit_requirements:
            return []

        changes: list[SolverChange] = []
        virtual_shifts = list(shifts)
        virtual_segments = list(segments)
        seen_dates: set[date] = set()
        for requirement in sorted(
            deposit_requirements,
            key=lambda item: (item.requirement_date, item.start_time),
        ):
            if requirement.requirement_date in seen_dates:
                continue
            seen_dates.add(requirement.requirement_date)
            primary_start = time(10, 0)
            primary_end = time(10, 30)
            if self._deposit_requirement_satisfied(
                requirement,
                virtual_shifts,
                virtual_segments,
                skills,
                staff_skills,
                store,
            ):
                continue

            existing_deposit = self._find_existing_deposit_for_date(
                requirement.task_type_id,
                requirement.requirement_date,
                virtual_shifts,
                virtual_segments,
                skills,
                staff_skills,
            )
            if existing_deposit is not None:
                existing_shift = existing_deposit["shift"]
                existing_segment = existing_deposit["segment"]
                if (
                    not existing_segment.is_locked
                    and not existing_shift.is_locked
                    and existing_shift.start_time <= primary_start
                    and primary_end <= existing_shift.end_time
                ):
                    change = self._deposit_move_change(
                        requirement=requirement,
                        segment=existing_segment,
                        shift=existing_shift,
                        primary_start=primary_start,
                        primary_end=primary_end,
                    )
                    changes.append(change)
                    self._append_virtual_deposit_assignment(
                        change,
                        virtual_shifts,
                        virtual_segments,
                    )
                continue

            candidate = self._find_deposit_candidate(
                target_date=requirement.requirement_date,
                start_time=primary_start,
                end_time=primary_end,
                task_type_id=requirement.task_type_id,
                shifts=virtual_shifts,
                segments=virtual_segments,
                requests=requests,
                staff_members=staff_members,
                skills=skills,
                staff_skills=staff_skills,
            )
            placement = "same_day"
            fallback_window = None
            if candidate is None:
                fallback_date = requirement.requirement_date - timedelta(days=1)
                close_time = closing_time_for_date(store, fallback_date) if store else time(22, 0)
                fallback_start = add_minutes(close_time, -30)
                fallback_window = (fallback_date, fallback_start, close_time)
                candidate = self._find_deposit_candidate(
                    target_date=fallback_date,
                    start_time=fallback_start,
                    end_time=close_time,
                    task_type_id=requirement.task_type_id,
                    shifts=virtual_shifts,
                    segments=virtual_segments,
                    requests=requests,
                    staff_members=staff_members,
                    skills=skills,
                    staff_skills=staff_skills,
                )
                placement = "previous_day_close"

            if candidate is None:
                continue

            change = self._deposit_change_for_candidate(
                requirement=requirement,
                candidate=candidate,
                placement=placement,
                fallback_window=fallback_window,
                shifts=virtual_shifts,
                primary_start=primary_start,
                primary_end=primary_end,
            )
            changes.append(change)
            self._append_virtual_deposit_assignment(
                change,
                virtual_shifts,
                virtual_segments,
            )
        return changes

    def _build_create_work_shift_changes(
        self,
        scope: OptimizationScopePayload,
        shifts: list[WorkShift],
        segments: list[ShiftSegment],
        requirements: list[ShiftRequirement],
        requests: list[ShiftRequest],
        staff_members: list[StaffMember],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> list[SolverChange]:
        changes = []
        for requirement in requirements:
            if requirement.requirement_type != "WORK" or requirement.position_id is None:
                continue
            if not self._requirement_in_scope(requirement, scope):
                continue
            current_count = sum(
                1
                for segment in segments
                if self._segment_matches_requirement_window(segment, requirement)
                and segment.segment_type == "WORK"
                and segment.position_id == requirement.position_id
            )
            shortage = requirement.min_staff_count - current_count
            if shortage <= 0:
                continue
            candidates = self._candidate_staff_for_requirement(
                requirement,
                shifts,
                requests,
                staff_members,
                skills,
                staff_skills,
            )
            for staff_member in candidates[:shortage]:
                after_value = {
                    "staff_member_id": str(staff_member.id),
                    "work_date": requirement.requirement_date.isoformat(),
                    "start_time": requirement.start_time.isoformat(),
                    "end_time": requirement.end_time.isoformat(),
                    "position_id": str(requirement.position_id),
                }
                changes.append(
                    SolverChange(
                        change_type="create_work_shift",
                        target_type="WorkShift",
                        target_id=None,
                        command_type="CreateWorkShift",
                        command_payload=after_value,
                        before_value=None,
                        after_value=after_value,
                        explanation={
                            "summary": f"{staff_member.display_name}を不足時間帯へ追加します。",
                            "resolved_warnings": ["STAFF_SHORTAGE"],
                            "active_constraints": ["希望勤務内", "スキル確認", "重複勤務禁止"],
                            "candidate_comparison": [
                                {
                                    "staff_member_id": str(candidate.id),
                                    "display_name": candidate.display_name,
                                    "score": self._staff_load_minutes(candidate.id, shifts),
                                }
                                for candidate in candidates[:3]
                            ],
                            "reasons": [
                                "不足人数解消",
                                "希望勤務内",
                                "必要スキル保持",
                                "他候補より勤務時間偏りが小さい",
                            ],
                        },
                    )
                )
        return changes

    def _build_staff_assignment_changes(
        self,
        scope: OptimizationScopePayload,
        shifts: list[WorkShift],
        segments: list[ShiftSegment],
        requests: list[ShiftRequest],
        warnings: list[ScheduleWarning],
        staff_members: list[StaffMember],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> list[SolverChange]:
        changes = []
        shifts_by_id = {shift.id: shift for shift in shifts}
        segments_by_id = {segment.id: segment for segment in segments}
        for warning in warnings:
            if (
                warning.warning_type not in {"SKILL_MISMATCH", "OPEN_CLOSE_SKILL_SHORTAGE"}
                or warning.shift_segment_id is None
            ):
                continue
            segment = segments_by_id.get(warning.shift_segment_id)
            if segment is None:
                continue
            shift = shifts_by_id.get(segment.work_shift_id)
            if shift is None or shift.is_locked or segment.is_locked:
                continue
            if not self._segment_in_scope(segment, shift, scope, None):
                continue
            candidates = self._candidate_staff_for_shift(
                shift,
                segments,
                shifts,
                requests,
                staff_members,
                skills,
                staff_skills,
            )
            if candidates:
                candidate = candidates[0]
                changes.append(
                    SolverChange(
                        change_type="assign_staff",
                        target_type="WorkShift",
                        target_id=shift.id,
                        command_type="AssignStaff",
                        command_payload={
                            "work_shift_id": str(shift.id),
                            "staff_member_id": str(candidate.id),
                        },
                        before_value=work_shift_snapshot(shift),
                        after_value={
                            **work_shift_snapshot(shift),
                            "staff_member_id": str(candidate.id),
                        },
                        explanation={
                            "summary": f"{candidate.display_name}へ担当者を変更します。",
                            "resolved_warnings": [warning.warning_type],
                            "active_constraints": ["スキル確認", "希望勤務内", "重複勤務禁止"],
                            "candidate_comparison": [
                                {
                                    "staff_member_id": str(item.id),
                                    "display_name": item.display_name,
                                    "score": self._staff_load_minutes(item.id, shifts),
                                }
                                for item in candidates[:3]
                            ],
                            "reasons": [
                                "必要スキル保持",
                                "希望勤務内",
                                "他候補より違反数が少ない",
                            ],
                        },
                    )
                )
                continue
            swap = self._find_staff_swap(shift, segments, shifts, skills, staff_skills)
            if swap is not None:
                changes.append(
                    SolverChange(
                        change_type="swap_staff",
                        target_type="WorkShift",
                        target_id=shift.id,
                        command_type="SwapStaff",
                        command_payload={
                            "first_work_shift_id": str(shift.id),
                            "second_work_shift_id": str(swap.id),
                        },
                        before_value={
                            "first": work_shift_snapshot(shift),
                            "second": work_shift_snapshot(swap),
                        },
                        after_value={
                            "first_staff_member_id": str(swap.staff_member_id),
                            "second_staff_member_id": str(shift.staff_member_id),
                        },
                        explanation={
                            "summary": "スタッフを入れ替えてスキル違反を減らします。",
                            "resolved_warnings": ["SKILL_MISMATCH"],
                            "active_constraints": ["ロック維持", "スキル確認"],
                            "reasons": ["スキル不足を解消", "ロック制約を維持"],
                        },
                    )
                )
        return changes

    def _build_break_changes(
        self,
        scope: OptimizationScopePayload,
        shifts: list[WorkShift],
        segments: list[ShiftSegment],
        warnings: list[ScheduleWarning],
    ) -> list[SolverChange]:
        changes = []
        segments_by_shift: dict[UUID, list[ShiftSegment]] = {}
        for segment in segments:
            segments_by_shift.setdefault(segment.work_shift_id, []).append(segment)
        for warning in warnings:
            if warning.warning_type != "BREAK_VIOLATION" or warning.work_shift_id is None:
                continue
            shift = next((item for item in shifts if item.id == warning.work_shift_id), None)
            if shift is None or shift.is_locked:
                continue
            shift_segments = segments_by_shift.get(shift.id, [])
            if not any(
                self._segment_in_scope(segment, shift, scope, None)
                for segment in shift_segments
            ):
                continue
            work_segment = max(
                (
                    segment
                    for segment in shift_segments
                    if segment.segment_type == "WORK"
                    and not segment.is_locked
                    and minutes_between(segment.start_time, segment.end_time) >= 60
                ),
                key=lambda item: minutes_between(item.start_time, item.end_time),
                default=None,
            )
            if work_segment is None:
                continue
            existing_break_minutes = sum(
                minutes_between(segment.start_time, segment.end_time)
                for segment in shift_segments
                if segment.segment_type == "BREAK"
            )
            missing_break_minutes = max(
                0,
                self._required_break_minutes(minutes_between(shift.start_time, shift.end_time))
                - existing_break_minutes,
            )
            if missing_break_minutes == 0:
                continue
            break_durations = (
                [15, 30]
                if missing_break_minutes >= 45
                else [15 if missing_break_minutes <= 15 else 30]
            )
            offset = 60
            for break_minutes in break_durations:
                break_start = add_minutes(work_segment.start_time, offset)
                break_end = add_minutes(break_start, break_minutes)
                if break_end > work_segment.end_time:
                    break_end = work_segment.end_time
                    break_start = add_minutes(break_end, -break_minutes)
                after_value = {
                    "work_shift_id": str(shift.id),
                    "start_time": break_start.isoformat(),
                    "end_time": break_end.isoformat(),
                }
                changes.append(
                    SolverChange(
                        change_type="create_break",
                        target_type="ShiftSegment",
                        target_id=None,
                        command_type="CreateBreak",
                        command_payload=after_value,
                        before_value=None,
                        after_value={**after_value, "segment_type": "BREAK"},
                        explanation={
                            "summary": f"勤務時間に応じた{break_minutes}分休憩を追加します。",
                            "resolved_warnings": ["BREAK_VIOLATION"],
                            "active_constraints": ["ロック維持", "勤務時間内"],
                            "reasons": ["休憩不足を解消", "ロック制約を維持"],
                        },
                    )
                )
                offset += break_minutes + 60
        return changes

    def _empty_proposal(
        self,
        *,
        scope: OptimizationScopePayload,
        started_at: float,
        warnings_before: list[ScheduleWarning],
        status_value: str,
        summary: str,
    ) -> SolverProposal:
        before_counts = warning_counts(warnings_before)
        return SolverProposal(
            title="AI提案: OR-Tools最適化案",
            summary=summary,
            generated_by="ortools",
            changes=[],
            metrics=SolverMetrics(
                status=status_value,
                solve_time_ms=elapsed_ms(started_at),
                objective_value=None,
                warning_before=before_counts,
                warning_after=before_counts,
                changed_segments=0,
                changed_work_shifts=0,
            ),
        )

    def _simulate_warning_counts(
        self,
        *,
        shifts: list[WorkShift],
        segments: list[ShiftSegment],
        requirements: list[ShiftRequirement],
        requests: list[ShiftRequest],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
        proposed_positions: dict[UUID, UUID],
    ) -> dict:
        counts = {
            "STAFF_SHORTAGE": 0,
            "BREAK_VIOLATION": 0,
            "SKILL_MISMATCH": 0,
            "REQUEST_VIOLATION": 0,
        }
        shifts_by_id = {shift.id: shift for shift in shifts}
        for requirement in requirements:
            matching_count = 0
            for segment in segments:
                if segment.segment_type != requirement.requirement_type:
                    continue
                if not self._segment_matches_requirement_window(segment, requirement):
                    continue
                position_id = proposed_positions.get(segment.id, segment.position_id)
                if (
                    position_id == requirement.position_id
                    and segment.task_type_id == requirement.task_type_id
                ):
                    matching_count += 1
            if matching_count < requirement.min_staff_count:
                counts["STAFF_SHORTAGE"] += 1

        for shift in shifts:
            shift_minutes = minutes_between(shift.start_time, shift.end_time)
            required_break_minutes = self._required_break_minutes(shift_minutes)
            if required_break_minutes == 0:
                continue
            break_minutes = sum(
                minutes_between(segment.start_time, segment.end_time)
                for segment in segments
                if segment.work_shift_id == shift.id and segment.segment_type == "BREAK"
            )
            if break_minutes < required_break_minutes:
                counts["BREAK_VIOLATION"] += 1

        for segment in segments:
            if segment.segment_type not in {"WORK", "TASK"}:
                continue
            shift = shifts_by_id.get(segment.work_shift_id)
            if shift is None:
                continue
            position_id = proposed_positions.get(segment.id, segment.position_id)
            if is_open_close_label(segment.label):
                required_skills = [
                    skill for skill in skills if skill.code == segment.label and skill.is_active
                ]
                can_cover = self._staff_has_any_skill(
                    shift.staff_member_id,
                    required_skills,
                    staff_skills,
                )
            else:
                can_cover = self._staff_can_cover_target(
                    shift.staff_member_id,
                    position_id,
                    segment.task_type_id,
                    skills,
                    staff_skills,
                )
            if not can_cover:
                warning_type = (
                    "OPEN_CLOSE_SKILL_SHORTAGE"
                    if is_open_close_label(segment.label)
                    else "SKILL_MISMATCH"
                )
                counts[warning_type] = counts.get(warning_type, 0) + 1

        for shift in shifts:
            for request in requests:
                if request.staff_member_id != shift.staff_member_id:
                    continue
                if request.request_date != shift.work_date:
                    continue
                if request.request_type not in {"unavailable", "off", "ng"}:
                    continue
                request_start = request.start_time or shift.start_time
                request_end = request.end_time or shift.end_time
                if overlaps(shift.start_time, shift.end_time, request_start, request_end):
                    counts["REQUEST_VIOLATION"] += 1
        return counts

    def _required_break_minutes(self, shift_minutes: int) -> int:
        if shift_minutes <= 210:
            return 0
        if shift_minutes < 360:
            return 15
        return 45

    def _segment_in_scope(
        self,
        segment: ShiftSegment,
        shift: WorkShift,
        scope: OptimizationScopePayload,
        scoped_segment_ids: set[UUID] | None,
    ) -> bool:
        if scoped_segment_ids is not None:
            return segment.id in scoped_segment_ids
        if scope.type.value == "full":
            return True
        if scope.type.value == "date":
            return segment.segment_date == scope.date
        if scope.type.value == "time_range":
            return (
                segment.segment_date == scope.date
                and overlaps(segment.start_time, segment.end_time, scope.start_time, scope.end_time)
            )
        if scope.type.value == "staff":
            return shift.staff_member_id == scope.staff_member_id and (
                scope.date is None or segment.segment_date == scope.date
            )
        if scope.type.value == "warning":
            return True
        return False

    def _scoped_segment_ids(
        self,
        scope: OptimizationScopePayload,
        warnings: list[ScheduleWarning],
    ) -> set[UUID] | None:
        if scope.type.value != "warning":
            return None
        return {
            warning.shift_segment_id
            for warning in warnings
            if warning.id == scope.warning_id and warning.shift_segment_id is not None
        }

    def _segment_matches_requirement_window(
        self,
        segment: ShiftSegment,
        requirement: ShiftRequirement,
    ) -> bool:
        return segment.segment_date == requirement.requirement_date and overlaps(
            segment.start_time,
            segment.end_time,
            requirement.start_time,
            requirement.end_time,
        )

    def _has_blocking_request(
        self,
        shift: WorkShift,
        segment: ShiftSegment,
        requests: list[ShiftRequest],
    ) -> bool:
        positive_requests = []
        for request in requests:
            if request.staff_member_id != shift.staff_member_id:
                continue
            if request.request_date != segment.segment_date:
                continue
            request_start = request.start_time or shift.start_time
            request_end = request.end_time or shift.end_time
            if request.request_type in {"unavailable", "off", "ng"} and overlaps(
                segment.start_time,
                segment.end_time,
                request_start,
                request_end,
            ):
                return True
            if request.request_type in {"available", "preferred", "ok"}:
                positive_requests.append((request_start, request_end))
        if not positive_requests:
            return False
        return not any(
            request_start <= segment.start_time and segment.end_time <= request_end
            for request_start, request_end in positive_requests
        )

    def _staff_can_cover_position(
        self,
        staff_member_id: UUID,
        position_id: UUID,
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> bool:
        return self._staff_can_cover_target(
            staff_member_id,
            position_id,
            None,
            skills,
            staff_skills,
        )

    def _staff_can_cover_target(
        self,
        staff_member_id: UUID,
        position_id: Optional[UUID],
        task_type_id: Optional[UUID],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> bool:
        required_skills = required_skills_for_target(position_id, task_type_id, skills)
        if not required_skills:
            return True
        staff_skill_ids = {
            staff_skill.skill_definition_id
            for staff_skill in staff_skills
            if staff_skill.staff_member_id == staff_member_id
        }
        return any(skill.id in staff_skill_ids for skill in required_skills)

    def _staff_has_any_skill(
        self,
        staff_member_id: UUID,
        required_skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> bool:
        if not required_skills:
            return True
        staff_skill_ids = {
            staff_skill.skill_definition_id
            for staff_skill in staff_skills
            if staff_skill.staff_member_id == staff_member_id
        }
        return any(skill.id in staff_skill_ids for skill in required_skills)

    def _position_resolves_skill_mismatch(
        self,
        staff_member_id: UUID,
        current_position_id: UUID,
        proposed_position_id: UUID,
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> bool:
        return not self._staff_can_cover_position(
            staff_member_id,
            current_position_id,
            skills,
            staff_skills,
        ) and self._staff_can_cover_position(
            staff_member_id,
            proposed_position_id,
            skills,
            staff_skills,
        )

    def _candidate_staff_for_requirement(
        self,
        requirement: ShiftRequirement,
        shifts: list[WorkShift],
        requests: list[ShiftRequest],
        staff_members: list[StaffMember],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> list[StaffMember]:
        candidates = [
            staff_member
            for staff_member in staff_members
            if self._staff_can_cover_target(
                staff_member.id,
                requirement.position_id,
                requirement.task_type_id,
                skills,
                staff_skills,
            )
            and self._staff_has_no_overlap(
                staff_member.id,
                requirement.requirement_date,
                requirement.start_time,
                requirement.end_time,
                shifts,
            )
            and self._request_allows_window(
                staff_member.id,
                requirement.requirement_date,
                requirement.start_time,
                requirement.end_time,
                requests,
            )
        ]
        return sorted(candidates, key=lambda item: self._staff_load_minutes(item.id, shifts))

    def _find_deposit_candidate(
        self,
        *,
        target_date: date,
        start_time: time,
        end_time: time,
        task_type_id: UUID,
        shifts: list[WorkShift],
        segments: list[ShiftSegment],
        requests: list[ShiftRequest],
        staff_members: list[StaffMember],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> dict | None:
        eligible_staff = [
            staff_member
            for staff_member in staff_members
            if self._staff_can_cover_target(
                staff_member.id,
                None,
                task_type_id,
                skills,
                staff_skills,
            )
            and self._request_allows_window(
                staff_member.id,
                target_date,
                start_time,
                end_time,
                requests,
            )
        ]
        existing_shift_candidates = []
        for shift in shifts:
            if shift.work_date != target_date or shift.is_locked:
                continue
            if not shift.start_time <= start_time < end_time <= shift.end_time:
                continue
            staff_member = next(
                (item for item in eligible_staff if item.id == shift.staff_member_id),
                None,
            )
            if staff_member is None:
                continue
            if self._has_locked_overlap(shift.id, start_time, end_time, segments):
                continue
            existing_shift_candidates.append(
                {
                    "kind": "existing_shift",
                    "shift": shift,
                    "staff_member": staff_member,
                    "target_date": target_date,
                    "start_time": start_time,
                    "end_time": end_time,
                    "task_type_id": task_type_id,
                }
            )
        if existing_shift_candidates:
            return sorted(
                existing_shift_candidates,
                key=lambda item: self._staff_load_minutes(item["staff_member"].id, shifts),
            )[0]

        create_shift_candidates = [
            {
                "kind": "new_shift",
                "staff_member": staff_member,
                "target_date": target_date,
                "start_time": start_time,
                "end_time": end_time,
                "task_type_id": task_type_id,
            }
            for staff_member in eligible_staff
            if self._staff_has_no_overlap(
                staff_member.id,
                target_date,
                start_time,
                end_time,
                shifts,
            )
        ]
        if not create_shift_candidates:
            return None
        return sorted(
            create_shift_candidates,
            key=lambda item: self._staff_load_minutes(item["staff_member"].id, shifts),
        )[0]

    def _deposit_change_for_candidate(
        self,
        *,
        requirement: ShiftRequirement,
        candidate: dict,
        placement: str,
        fallback_window: tuple[date, time, time] | None,
        shifts: list[WorkShift],
        primary_start: time,
        primary_end: time,
    ) -> SolverChange:
        staff_member = candidate["staff_member"]
        start_time = candidate["start_time"]
        end_time = candidate["end_time"]
        target_date = candidate["target_date"]
        reasons = [
            "M可能スキル保持",
            "希望勤務内",
            "ロック制約を維持",
        ]
        active_constraints = [
            "M可能者のみ",
            "勤務希望内",
            "勤務重複禁止",
            "当日10:00-10:30優先",
        ]
        if placement == "same_day":
            summary = "当日10:00-10:30に入金Mを配置します。"
            reasons.append("当日10:00-10:30で配置可能")
        else:
            summary = "当日10:00-10:30に配置できないため、前日クローズ帯へ入金Mを配置します。"
            reasons.extend(
                [
                    "当日10:00-10:30にM可能者を配置できない",
                    "前日クローズ30分で救済配置可能",
                ]
            )
            active_constraints.append("前日クローズ救済")

        explanation = {
            "summary": summary,
            "resolved_warnings": ["DEPOSIT_COVERAGE", "STAFF_SHORTAGE"],
            "active_constraints": active_constraints,
            "reasons": reasons,
            "deposit_rule": {
                "primary_window": {
                    "date": requirement.requirement_date.isoformat(),
                    "start_time": primary_start.isoformat(),
                    "end_time": primary_end.isoformat(),
                },
                "placement": placement,
                "fallback_window": fallback_window_snapshot(fallback_window),
            },
            "candidate_comparison": [
                {
                    "staff_member_id": str(staff_member.id),
                    "display_name": staff_member.display_name,
                    "score": self._staff_load_minutes(staff_member.id, shifts),
                    "selected": True,
                    "reasons": ["M可能", "希望勤務内"],
                }
            ],
        }
        after_value = {
            "staff_member_id": str(staff_member.id),
            "work_date": target_date.isoformat(),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "task_type_id": str(candidate["task_type_id"]),
            "placement": placement,
        }
        if candidate["kind"] == "existing_shift":
            shift = candidate["shift"]
            return SolverChange(
                change_type="create_task_segment",
                target_type="ShiftSegment",
                target_id=None,
                command_type="CreateTaskSegment",
                command_payload={
                    "work_shift_id": str(shift.id),
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "task_type_id": str(candidate["task_type_id"]),
                },
                before_value=None,
                after_value={
                    **after_value,
                    "work_shift_id": str(shift.id),
                    "segment_type": "TASK",
                },
                explanation=explanation,
            )
        return SolverChange(
            change_type="create_work_shift",
            target_type="WorkShift",
            target_id=None,
            command_type="CreateWorkShift",
            command_payload={
                "staff_member_id": str(staff_member.id),
                "work_date": target_date.isoformat(),
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "task_type_id": str(candidate["task_type_id"]),
            },
            before_value=None,
            after_value={**after_value, "segment_type": "TASK"},
            explanation=explanation,
        )

    def _deposit_move_change(
        self,
        *,
        requirement: ShiftRequirement,
        segment: ShiftSegment,
        shift: WorkShift,
        primary_start: time,
        primary_end: time,
    ) -> SolverChange:
        explanation = {
            "summary": "入金Mを正しい当日10:00-10:30へ移動します。",
            "resolved_warnings": ["DEPOSIT_COVERAGE"],
            "active_constraints": ["Mは1日1回のみ", "当日10:00-10:30固定", "M可能者のみ"],
            "reasons": [
                "既存のMが仕様外の時間帯にある",
                "同じ従業員が当日10:00-10:30に勤務中",
                "2回目のMを追加せず既存Mを移動",
            ],
            "deposit_rule": {
                "primary_window": {
                    "date": requirement.requirement_date.isoformat(),
                    "start_time": primary_start.isoformat(),
                    "end_time": primary_end.isoformat(),
                },
                "placement": "same_day",
                "moved_from": {
                    "date": segment.segment_date.isoformat(),
                    "start_time": segment.start_time.isoformat(),
                    "end_time": segment.end_time.isoformat(),
                },
                "fallback_window": None,
            },
        }
        return SolverChange(
            change_type="move_task_segment",
            target_type="ShiftSegment",
            target_id=segment.id,
            command_type="MoveTaskSegment",
            command_payload={
                "segment_id": str(segment.id),
                "start_time": primary_start.isoformat(),
                "end_time": primary_end.isoformat(),
            },
            before_value=segment_snapshot(segment),
            after_value={
                **segment_snapshot(segment),
                "start_time": primary_start.isoformat(),
                "end_time": primary_end.isoformat(),
                "staff_member_id": str(shift.staff_member_id),
            },
            explanation=explanation,
        )

    def _append_virtual_deposit_assignment(
        self,
        change: SolverChange,
        shifts: list[WorkShift],
        segments: list[ShiftSegment],
    ) -> None:
        payload = change.command_payload
        if change.command_type == "MoveTaskSegment":
            original = next(
                (item for item in segments if str(item.id) == payload["segment_id"]),
                None,
            )
            if original is None:
                return
            segments.append(
                virtual_segment(
                    work_shift_id=original.work_shift_id,
                    segment_date=original.segment_date,
                    start_time=time.fromisoformat(payload["start_time"]),
                    end_time=time.fromisoformat(payload["end_time"]),
                    task_type_id=original.task_type_id,
                )
            )
            return
        if change.command_type == "CreateTaskSegment":
            shift = next(
                (item for item in shifts if str(item.id) == payload["work_shift_id"]),
                None,
            )
            if shift is None:
                return
            segments.append(
                virtual_segment(
                    work_shift_id=shift.id,
                    segment_date=shift.work_date,
                    start_time=time.fromisoformat(payload["start_time"]),
                    end_time=time.fromisoformat(payload["end_time"]),
                    task_type_id=UUID(payload["task_type_id"]),
                )
            )
            return
        if change.command_type == "CreateWorkShift":
            virtual_shift = virtual_work_shift(
                staff_member_id=UUID(payload["staff_member_id"]),
                work_date=date.fromisoformat(payload["work_date"]),
                start_time=time.fromisoformat(payload["start_time"]),
                end_time=time.fromisoformat(payload["end_time"]),
            )
            shifts.append(virtual_shift)
            segments.append(
                virtual_segment(
                    work_shift_id=virtual_shift.id,
                    segment_date=virtual_shift.work_date,
                    start_time=virtual_shift.start_time,
                    end_time=virtual_shift.end_time,
                    task_type_id=UUID(payload["task_type_id"]),
                )
            )

    def _candidate_staff_for_shift(
        self,
        shift: WorkShift,
        segments: list[ShiftSegment],
        shifts: list[WorkShift],
        requests: list[ShiftRequest],
        staff_members: list[StaffMember],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> list[StaffMember]:
        target_segments = [segment for segment in segments if segment.work_shift_id == shift.id]
        candidates = [
            staff_member
            for staff_member in staff_members
            if staff_member.id != shift.staff_member_id
            and self._staff_has_no_overlap(
                staff_member.id,
                shift.work_date,
                shift.start_time,
                shift.end_time,
                shifts,
            )
            and self._request_allows_window(
                staff_member.id,
                shift.work_date,
                shift.start_time,
                shift.end_time,
                requests,
            )
            and self._staff_can_cover_segments(
                staff_member.id,
                target_segments,
                skills,
                staff_skills,
            )
        ]
        return sorted(candidates, key=lambda item: self._staff_load_minutes(item.id, shifts))

    def _find_staff_swap(
        self,
        target_shift: WorkShift,
        segments: list[ShiftSegment],
        shifts: list[WorkShift],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> WorkShift | None:
        target_segments = [
            segment for segment in segments if segment.work_shift_id == target_shift.id
        ]
        for candidate_shift in shifts:
            if candidate_shift.id == target_shift.id or candidate_shift.is_locked:
                continue
            candidate_segments = [
                segment for segment in segments if segment.work_shift_id == candidate_shift.id
            ]
            if self._staff_can_cover_segments(
                candidate_shift.staff_member_id,
                target_segments,
                skills,
                staff_skills,
            ) and self._staff_can_cover_segments(
                target_shift.staff_member_id,
                candidate_segments,
                skills,
                staff_skills,
            ):
                return candidate_shift
        return None

    def _staff_can_cover_segments(
        self,
        staff_member_id: UUID,
        segments: list[ShiftSegment],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> bool:
        return all(
            segment.segment_type not in {"WORK", "TASK"}
            or self._staff_can_cover_segment(
                staff_member_id,
                segment,
                skills,
                staff_skills,
            )
            for segment in segments
        )

    def _staff_can_cover_segment(
        self,
        staff_member_id: UUID,
        segment: ShiftSegment,
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> bool:
        required_skills = required_skills_for_segment(segment, skills)
        if not required_skills:
            return True
        staff_skill_ids = {
            staff_skill.skill_definition_id
            for staff_skill in staff_skills
            if staff_skill.staff_member_id == staff_member_id
        }
        return any(skill.id in staff_skill_ids for skill in required_skills)

    def _has_deposit_assignment(
        self,
        *,
        task_type_id: UUID,
        target_date: date,
        start_time: time,
        end_time: time,
        shifts: list[WorkShift],
        segments: list[ShiftSegment],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> bool:
        shifts_by_id = {shift.id: shift for shift in shifts}
        for segment in segments:
            if segment.segment_type != "TASK":
                continue
            if segment.task_type_id != task_type_id:
                continue
            if segment.segment_date != target_date:
                continue
            if segment.start_time != start_time or segment.end_time != end_time:
                continue
            shift = shifts_by_id.get(segment.work_shift_id)
            if shift is None:
                continue
            if self._staff_can_cover_target(
                shift.staff_member_id,
                None,
                task_type_id,
                skills,
                staff_skills,
            ):
                return True
        return False

    def _find_existing_deposit_for_date(
        self,
        task_type_id: UUID,
        target_date: date,
        shifts: list[WorkShift],
        segments: list[ShiftSegment],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
    ) -> dict | None:
        shifts_by_id = {shift.id: shift for shift in shifts}
        for segment in segments:
            if segment.segment_type != "TASK":
                continue
            if segment.task_type_id != task_type_id:
                continue
            if segment.segment_date != target_date:
                continue
            shift = shifts_by_id.get(segment.work_shift_id)
            if shift is None:
                continue
            if not self._staff_can_cover_target(
                shift.staff_member_id,
                None,
                task_type_id,
                skills,
                staff_skills,
            ):
                continue
            if segment.start_time == time(10, 0) and segment.end_time == time(10, 30):
                continue
            return {"segment": segment, "shift": shift}
        return None

    def _deposit_requirement_satisfied(
        self,
        requirement: ShiftRequirement,
        shifts: list[WorkShift],
        segments: list[ShiftSegment],
        skills: list[SkillDefinition],
        staff_skills: list[StaffSkill],
        store: Store | None,
    ) -> bool:
        if self._has_deposit_assignment(
            task_type_id=requirement.task_type_id,
            target_date=requirement.requirement_date,
            start_time=time(10, 0),
            end_time=time(10, 30),
            shifts=shifts,
            segments=segments,
            skills=skills,
            staff_skills=staff_skills,
        ):
            return True
        fallback_date = requirement.requirement_date - timedelta(days=1)
        fallback_end = closing_time_for_date(store, fallback_date)
        fallback_start = add_minutes(fallback_end, -30)
        return self._has_deposit_assignment(
            task_type_id=requirement.task_type_id,
            target_date=fallback_date,
            start_time=fallback_start,
            end_time=fallback_end,
            shifts=shifts,
            segments=segments,
            skills=skills,
            staff_skills=staff_skills,
        )

    def _has_locked_overlap(
        self,
        work_shift_id: UUID,
        start_time: time,
        end_time: time,
        segments: list[ShiftSegment],
    ) -> bool:
        return any(
            segment.work_shift_id == work_shift_id
            and segment.is_locked
            and overlaps(segment.start_time, segment.end_time, start_time, end_time)
            for segment in segments
        )

    def _staff_has_no_overlap(
        self,
        staff_member_id: UUID,
        work_date,
        start_time: time,
        end_time: time,
        shifts: list[WorkShift],
    ) -> bool:
        return not any(
            shift.staff_member_id == staff_member_id
            and shift.work_date == work_date
            and overlaps(shift.start_time, shift.end_time, start_time, end_time)
            for shift in shifts
        )

    def _request_allows_window(
        self,
        staff_member_id: UUID,
        work_date,
        start_time: time,
        end_time: time,
        requests: list[ShiftRequest],
    ) -> bool:
        positive_requests = []
        for request in requests:
            if request.staff_member_id != staff_member_id or request.request_date != work_date:
                continue
            request_start = request.start_time or start_time
            request_end = request.end_time or end_time
            if request.request_type in {"unavailable", "off", "ng"} and overlaps(
                start_time,
                end_time,
                request_start,
                request_end,
            ):
                return False
            if request.request_type in {"available", "preferred", "ok"}:
                positive_requests.append((request_start, request_end))
        if not positive_requests:
            return True
        return any(
            request_start <= start_time and end_time <= request_end
            for request_start, request_end in positive_requests
        )

    def _staff_load_minutes(self, staff_member_id: UUID, shifts: list[WorkShift]) -> int:
        return sum(
            minutes_between(shift.start_time, shift.end_time)
            for shift in shifts
            if shift.staff_member_id == staff_member_id
        )

    def _requirement_in_scope(
        self,
        requirement: ShiftRequirement,
        scope: OptimizationScopePayload,
    ) -> bool:
        if scope.type.value == "full":
            return True
        if scope.type.value == "date":
            return requirement.requirement_date == scope.date
        if scope.type.value == "time_range":
            return requirement.requirement_date == scope.date and overlaps(
                requirement.start_time,
                requirement.end_time,
                scope.start_time,
                scope.end_time,
            )
        if scope.type.value in {"staff", "warning"}:
            return True
        return False

    def _status_from_result(self, result_status: int) -> str:
        if result_status == cp_model.OPTIMAL:
            return "completed"
        if result_status == cp_model.FEASIBLE:
            return "partial"
        return "partial"

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

    async def _list_warnings(self, schedule_version_id: UUID) -> list[ScheduleWarning]:
        result = await self.session.scalars(
            select(ScheduleWarning).where(
                ScheduleWarning.schedule_version_id == schedule_version_id
            )
        )
        return list(result)

    async def _list_positions(self, store_id: UUID) -> list[Position]:
        result = await self.session.scalars(
            select(Position)
            .where(Position.store_id == store_id)
            .where(Position.is_active.is_(True))
            .order_by(Position.priority)
        )
        return list(result)

    async def _list_task_types(self, store_id: UUID) -> list[TaskType]:
        result = await self.session.scalars(
            select(TaskType)
            .where(TaskType.store_id == store_id)
            .where(TaskType.is_active.is_(True))
        )
        return list(result)

    async def _list_staff_members(self, store_id: UUID) -> list[StaffMember]:
        result = await self.session.scalars(
            select(StaffMember)
            .where(StaffMember.store_id == store_id)
            .where(StaffMember.is_active.is_(True))
            .order_by(StaffMember.priority)
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


def warning_counts(warnings: list[ScheduleWarning]) -> dict:
    counts = {
        "STAFF_SHORTAGE": 0,
        "BREAK_VIOLATION": 0,
        "SKILL_MISMATCH": 0,
        "REQUEST_VIOLATION": 0,
        "OPEN_CLOSE_SKILL_SHORTAGE": 0,
        "DEPOSIT_COVERAGE": 0,
    }
    for warning in warnings:
        counts[warning.warning_type] = counts.get(warning.warning_type, 0) + 1
    return counts


def segment_snapshot(segment: ShiftSegment) -> dict:
    return {
        "id": str(segment.id),
        "segment_type": segment.segment_type,
        "position_id": str(segment.position_id) if segment.position_id else None,
        "task_type_id": str(segment.task_type_id) if segment.task_type_id else None,
        "start_time": segment.start_time.isoformat(),
        "end_time": segment.end_time.isoformat(),
        "is_locked": segment.is_locked,
    }


def is_open_close_label(label: str | None) -> bool:
    return bool(label and (label.endswith("_OPEN") or label.endswith("_CLOSE")))


def required_skills_for_target(
    position_id: Optional[UUID],
    task_type_id: Optional[UUID],
    skills: list[SkillDefinition],
) -> list[SkillDefinition]:
    if task_type_id is not None:
        return [
            skill
            for skill in skills
            if skill.task_type_id == task_type_id
            and getattr(skill, "skill_category", "task") == "task"
        ]
    if position_id is not None:
        return [
            skill
            for skill in skills
            if skill.position_id == position_id
            and getattr(skill, "skill_category", "position") == "position"
        ]
    return []


def required_skills_for_segment(
    segment: ShiftSegment,
    skills: list[SkillDefinition],
) -> list[SkillDefinition]:
    if is_open_close_label(segment.label):
        return [
            skill
            for skill in skills
            if skill.code == segment.label and getattr(skill, "is_active", True)
        ]
    return required_skills_for_target(segment.position_id, segment.task_type_id, skills)


def work_shift_snapshot(work_shift: WorkShift) -> dict:
    return {
        "id": str(work_shift.id),
        "staff_member_id": str(work_shift.staff_member_id),
        "work_date": work_shift.work_date.isoformat(),
        "start_time": work_shift.start_time.isoformat(),
        "end_time": work_shift.end_time.isoformat(),
        "is_locked": work_shift.is_locked,
    }


def minutes_between(start_time: time, end_time: time) -> int:
    return time_to_minutes(end_time) - time_to_minutes(start_time)


def time_to_minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def elapsed_ms(started_at: float) -> int:
    return int((monotonic_time.perf_counter() - started_at) * 1000)


def add_minutes(value: time, minutes: int) -> time:
    total = max(0, min(24 * 60 - 1, time_to_minutes(value) + minutes))
    return time(total // 60, total % 60)


def round_to_quarter_hour(minute: int) -> int:
    return ((minute + 7) // 15) * 15


def max_work_segment_minutes(segment: dict) -> int:
    if segment.get("position_code") == "S":
        return 120
    return 180


def coverage_reassignment_window(
    segment: dict,
    start_time: time,
    end_time: time,
) -> tuple[time, time]:
    minimum_minutes = 60
    segment_end = time_to_minutes(segment["end_time"])
    start_minute = max(time_to_minutes(segment["start_time"]), time_to_minutes(start_time))
    window_end = min(segment_end, start_minute + minimum_minutes)
    if window_end - start_minute < minimum_minutes:
        start_minute = max(time_to_minutes(segment["start_time"]), window_end - minimum_minutes)
    return add_minutes(time(0, 0), start_minute), add_minutes(time(0, 0), window_end)


def coverage_reassignment_donor_score(
    segment: dict,
    required_counts: Counter,
    active_counts: Counter,
) -> tuple[int, int, int]:
    position_code = segment.get("position_code")
    surplus = active_counts[position_code] - required_counts[position_code]
    if position_code not in {"B", "C", "F", "S"}:
        return (0, 0, 0)
    if surplus <= 0:
        return (100, 0, 0)
    donor_priority = {
        "S": 0,
        "F": 1,
        "C": 2,
        "B": 2,
    }.get(position_code, 3)
    duration = minutes_between(segment["start_time"], segment["end_time"])
    return (0, donor_priority, -duration)


def balanced_assignment_score(
    segment: dict,
    target_code: str,
    required_counts: Counter,
    active_counts: Counter,
) -> tuple[int, int, int, int]:
    current_code = segment.get("position_code")
    if current_code == target_code:
        return (0, 0, 0, 0)
    current_surplus = active_counts[current_code] - required_counts[current_code]
    target_shortage = required_counts[target_code] - active_counts[target_code]
    donor_priority = {
        "S": 0,
        "F": 1,
        "B": 2,
        "C": 3,
    }.get(current_code, 4)
    duration = minutes_between(segment["start_time"], segment["end_time"])
    return (
        0 if target_shortage > 0 else 1,
        0 if current_surplus > 0 else 1,
        donor_priority,
        -duration,
    )


def balanced_assignment_cost(
    segment: dict,
    target_code: str,
    required_counts: Counter,
    active_counts: Counter,
) -> int:
    current_code = segment.get("position_code")
    if current_code == target_code:
        return 0

    current_surplus = active_counts[current_code] - required_counts[current_code]
    target_shortage = required_counts[target_code] - active_counts[target_code]
    cost = 0
    if target_shortage <= 0:
        cost += 10_000
    if current_surplus <= 0:
        cost += 1_000
    cost += position_priority_index(current_code) * 100
    cost += max(0, 150 - minutes_between(segment["start_time"], segment["end_time"]))
    return cost


def position_priority_index(position_code: str | None) -> int:
    return {
        "C": 0,
        "B": 1,
        "F": 2,
        "S": 3,
    }.get(position_code or "", 4)


def rotation_candidate_score(
    staff_member_id: UUID,
    target_code: str,
    last_position_by_staff: dict[UUID, str],
    position_started_minute_by_staff: dict[UUID, int],
    interval_start_minute: int,
) -> tuple[int, int]:
    previous_code = last_position_by_staff.get(staff_member_id)
    started_minute = position_started_minute_by_staff.get(staff_member_id)
    if previous_code is None or started_minute is None:
        return (0, 0)

    elapsed = interval_start_minute - started_minute
    if previous_code == target_code:
        if elapsed >= 150:
            return (80, -elapsed)
        if elapsed >= 90:
            return (20, -elapsed)
        return (0, -elapsed)

    if elapsed < 90:
        return (30, elapsed)
    return (0, elapsed)


def same_position_duration_penalty(position_code: str, projected_elapsed: int) -> int:
    if projected_elapsed <= SOFT_MAX_POSITION_BLOCK_MINUTES:
        return 0
    over_soft_blocks = (projected_elapsed - SOFT_MAX_POSITION_BLOCK_MINUTES + 14) // 15
    multiplier = 450 if position_code == "C" else 300
    penalty = over_soft_blocks * over_soft_blocks * multiplier
    if projected_elapsed > HARD_MAX_POSITION_BLOCK_MINUTES:
        over_hard_blocks = (projected_elapsed - HARD_MAX_POSITION_BLOCK_MINUTES + 14) // 15
        hard_multiplier = 8_000 if position_code == "C" else 5_000
        penalty += over_hard_blocks * hard_multiplier
    return penalty


def position_change_penalty(elapsed: int) -> int:
    if elapsed < MIN_POSITION_BLOCK_MINUTES:
        return 200_000
    if elapsed < 90:
        return 25_000
    if elapsed < IDEAL_POSITION_BLOCK_MINUTES:
        return 250
    if elapsed <= SOFT_MAX_POSITION_BLOCK_MINUTES:
        return 0
    return 50


def short_interval_change_penalty(interval_minutes: int) -> int:
    if interval_minutes <= 15:
        return 80_000
    if interval_minutes <= 30:
        return 40_000
    return 15_000


def work_fragment_penalty_after_special_segment(
    segment: dict,
    special_start: time,
    special_end: time,
) -> int:
    minimum_work_minutes = 60
    segment_start = time_to_minutes(segment["start_time"])
    segment_end = time_to_minutes(segment["end_time"])
    special_start_minute = time_to_minutes(special_start)
    special_end_minute = time_to_minutes(special_end)
    left_minutes = special_start_minute - segment_start
    right_minutes = segment_end - special_end_minute
    penalty = 0
    for fragment_minutes in (left_minutes, right_minutes):
        if 0 < fragment_minutes < minimum_work_minutes:
            penalty += (minimum_work_minutes - fragment_minutes) * 100
    return penalty


def deposit_candidate_coverage_cost(
    planned: dict[UUID, list[dict]],
    staff_member_id: UUID,
    deposit_start: time,
    deposit_end: time,
) -> int:
    active_codes_after_deposit = set()
    removed_code = None
    for current_staff_id, segments in planned.items():
        for segment in segments:
            if segment["segment_type"] != "WORK":
                continue
            if not (
                segment["start_time"] <= deposit_start
                and deposit_end <= segment["end_time"]
            ):
                continue
            position_code = segment.get("position_code")
            if current_staff_id == staff_member_id:
                removed_code = position_code
                continue
            if position_code:
                active_codes_after_deposit.add(position_code)

    cost = 0
    if "B" not in active_codes_after_deposit:
        cost += 1000
    if "C" not in active_codes_after_deposit:
        cost += 1000
    if removed_code in {"B", "C"}:
        cost += 100
    return cost


def scope_date(scope: OptimizationScopePayload) -> date | None:
    if scope.type.value in {"date", "time_range"}:
        return scope.date
    if scope.type.value == "staff":
        return scope.date
    return None


def closing_time_for_date(store: Store | None, target_date: date) -> time:
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


def fallback_window_snapshot(window: tuple[date, time, time] | None) -> dict | None:
    if window is None:
        return None
    target_date, start_time, end_time = window
    return {
        "date": target_date.isoformat(),
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
    }


def virtual_work_shift(
    *,
    staff_member_id: UUID,
    work_date: date,
    start_time: time,
    end_time: time,
):
    return type(
        "VirtualWorkShift",
        (),
        {
            "id": uuid4(),
            "staff_member_id": staff_member_id,
            "work_date": work_date,
            "start_time": start_time,
            "end_time": end_time,
            "is_locked": False,
        },
    )()


def virtual_segment(
    *,
    work_shift_id: UUID,
    segment_date: date,
    start_time: time,
    end_time: time,
    task_type_id: UUID,
):
    return type(
        "VirtualShiftSegment",
        (),
        {
            "id": uuid4(),
            "work_shift_id": work_shift_id,
            "segment_date": segment_date,
            "start_time": start_time,
            "end_time": end_time,
            "segment_type": "TASK",
            "position_id": None,
            "task_type_id": task_type_id,
            "is_locked": False,
        },
    )()


def fairness_score(shifts: list[WorkShift]) -> int:
    if not shifts:
        return 0
    minutes_by_staff: dict[UUID, int] = {}
    days_by_staff: dict[UUID, set] = {}
    opening_by_staff: dict[UUID, int] = {}
    closing_by_staff: dict[UUID, int] = {}
    for shift in shifts:
        minutes_by_staff[shift.staff_member_id] = minutes_by_staff.get(shift.staff_member_id, 0) + (
            minutes_between(shift.start_time, shift.end_time)
        )
        days_by_staff.setdefault(shift.staff_member_id, set()).add(shift.work_date)
        if shift.start_time <= time(10, 0):
            opening_by_staff[shift.staff_member_id] = (
                opening_by_staff.get(shift.staff_member_id, 0) + 1
            )
        if shift.end_time >= time(17, 0):
            closing_by_staff[shift.staff_member_id] = (
                closing_by_staff.get(shift.staff_member_id, 0) + 1
            )
    staff_ids = (
        set(minutes_by_staff)
        | set(days_by_staff)
        | set(opening_by_staff)
        | set(closing_by_staff)
    )
    return (
        spread([minutes_by_staff.get(staff_id, 0) for staff_id in staff_ids])
        + spread([len(days_by_staff.get(staff_id, set())) for staff_id in staff_ids]) * 60
        + spread([opening_by_staff.get(staff_id, 0) for staff_id in staff_ids]) * 30
        + spread([closing_by_staff.get(staff_id, 0) for staff_id in staff_ids]) * 30
    )


def spread(values: list[int]) -> int:
    if not values:
        return 0
    return max(values) - min(values)


def natural_position_score(
    segment: ShiftSegment,
    position: Position,
    all_segments: list[ShiftSegment],
) -> int:
    score = 0
    position_code = getattr(position, "code", "")
    start_minutes = time_to_minutes(segment.start_time)
    end_minutes = time_to_minutes(segment.end_time)

    if overlaps(segment.start_time, segment.end_time, time(11, 0), time(14, 0)):
        score += 0 if position_code in {"C", "B"} else 2

    adjacent_segments = [
        item
        for item in all_segments
        if item.work_shift_id == segment.work_shift_id
        and item.id != segment.id
        and item.segment_type == "WORK"
        and (
            time_to_minutes(item.end_time) == start_minutes
            or time_to_minutes(item.start_time) == end_minutes
        )
    ]
    if any(item.position_id == position.id for item in adjacent_segments):
        score += 2

    break_neighbors = [
        item
        for item in all_segments
        if item.work_shift_id == segment.work_shift_id
        and item.segment_type == "BREAK"
        and (
            time_to_minutes(item.end_time) == start_minutes
            or time_to_minutes(item.start_time) == end_minutes
        )
    ]
    if break_neighbors and segment.position_id == position.id:
        score += 1

    return score


def target_position_codes(
    active_staff_count: int,
    positions_by_code: dict[str, Position],
) -> list[str]:
    if active_staff_count <= 1:
        preferred = ["C", "B", "F", "S"]
    elif active_staff_count == 2:
        preferred = ["B", "C"]
    elif active_staff_count == 3:
        preferred = ["B", "C", "F"]
    elif active_staff_count == 4:
        preferred = ["B", "C", "F", "S"]
    else:
        preferred = ["B", "B", "C", "F", "S"]

    result: list[str] = []
    for code in preferred:
        if code in positions_by_code:
            result.append(code)
    fallback_codes = ["B", "C", "F", "S"]
    while len(result) < active_staff_count:
        added = False
        for code in fallback_codes:
            if code in positions_by_code:
                result.append(code)
                added = True
                if len(result) == active_staff_count:
                    break
        if not added:
            break
    return result[:active_staff_count]


def count_changes(changes: list[SolverChange], change_type: str, predicate=None) -> int:
    return sum(
        1
        for change in changes
        if change.change_type == change_type and (predicate is None or predicate(change))
    )


def count_staff_changes(changes: list[SolverChange]) -> int:
    return sum(
        1
        for change in changes
        if change.change_type in {"create_work_shift", "assign_staff", "swap_staff"}
    )


def count_work_shift_changes(changes: list[SolverChange]) -> int:
    return sum(
        1
        for change in changes
        if change.change_type
        in {
            "create_work_shift",
            "update_work_shift",
            "delete_work_shift",
            "assign_staff",
            "swap_staff",
        }
    )


def proposal_summary_metrics(
    changes: list[SolverChange],
    warning_before: dict,
    warning_after: dict,
    fairness_before: int,
    fairness_after: int,
) -> dict:
    before_total = sum(int(value) for value in warning_before.values())
    after_total = sum(int(value) for value in warning_after.values())
    target_staff_ids = set()
    for change in changes:
        payload = change.command_payload
        staff_member_id = payload.get("staff_member_id")
        if isinstance(staff_member_id, str):
            target_staff_ids.add(staff_member_id)
    return {
        "created_work_shifts": count_changes(changes, "create_work_shift"),
        "created_task_segments": count_changes(changes, "create_task_segment"),
        "moved_task_segments": count_changes(changes, "move_task_segment"),
        "deposit_rescue_count": count_changes(
            changes,
            "create_task_segment",
            lambda change: (change.explanation or {})
            .get("deposit_rule", {})
            .get("placement")
            == "previous_day_close",
        )
        + count_changes(
            changes,
            "create_work_shift",
            lambda change: (change.explanation or {})
            .get("deposit_rule", {})
            .get("placement")
            == "previous_day_close",
        ),
        "deleted_work_shifts": count_changes(changes, "delete_work_shift"),
        "updated_work_shifts": count_work_shift_changes(changes),
        "resolved_warnings": max(0, before_total - after_total),
        "new_warnings": max(0, after_total - before_total),
        "fairness_delta": fairness_before - fairness_after,
        "target_staff_count": len(target_staff_ids),
    }
