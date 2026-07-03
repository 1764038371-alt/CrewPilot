from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.modules.schedule.models import ScheduleWarning, ShiftSegment, WorkShift
from app.modules.staff.models import StaffMember
from app.modules.stores.models import SkillDefinition, StaffSkill


class ExplanationFactor(BaseModel):
    key: str
    label: str
    value: str
    impact: str


class RequiredSkillExplanation(BaseModel):
    id: UUID
    code: str
    name: str
    matched: bool


class WarningExplanation(BaseModel):
    id: UUID
    warning_type: str
    severity: str
    message: str


class CandidateStaffExplanation(BaseModel):
    staff_member_id: UUID
    display_name: str
    fit_score: int
    reason: str


class LockStateExplanation(BaseModel):
    is_locked: bool
    lock_scope: Optional[str]
    lock_reason: Optional[str]


class ShiftSegmentExplanationRead(BaseModel):
    target_type: str = "ShiftSegment"
    target_id: UUID
    generated_by: str = "rule_based_dummy"
    assignment_reason: str
    factors: list[ExplanationFactor]
    required_skills: list[RequiredSkillExplanation]
    current_warnings: list[WarningExplanation]
    candidate_staff: list[CandidateStaffExplanation]
    lock_state: LockStateExplanation


router = APIRouter(prefix="/shift-segments", tags=["shift-segment-explanations"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/{shift_segment_id}/explanation", response_model=ShiftSegmentExplanationRead)
async def get_shift_segment_explanation(
    shift_segment_id: UUID,
    session: SessionDep,
) -> ShiftSegmentExplanationRead:
    segment = await session.get(ShiftSegment, shift_segment_id)
    if segment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shift segment not found",
        )
    shift = await session.get(WorkShift, segment.work_shift_id)
    if shift is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Work shift not found",
        )

    required_skills = await _list_required_skills(session, segment)
    staff_skill_ids = await _list_staff_skill_ids(session, shift.staff_member_id)
    warnings = await _list_warnings(session, segment)
    candidates = await _list_candidate_staff(session, segment.store_id, required_skills)

    matched_count = sum(1 for skill in required_skills if skill.id in staff_skill_ids)
    required_skill_reads = [
        RequiredSkillExplanation(
            id=skill.id,
            code=skill.code,
            name=skill.name,
            matched=skill.id in staff_skill_ids,
        )
        for skill in required_skills
    ]
    assignment_reason = (
        "既存の割当をもとに、時間帯・業務種別・必要スキル・ロック状態を評価しています。"
    )
    if required_skills and matched_count == len(required_skills):
        assignment_reason = "必要スキルを満たしているため、この担当は妥当です。"
    elif required_skills:
        assignment_reason = "必要スキルに不足があるため、候補スタッフとの入れ替え検討対象です。"

    return ShiftSegmentExplanationRead(
        target_id=segment.id,
        assignment_reason=assignment_reason,
        factors=[
            ExplanationFactor(
                key="time_range",
                label="時間帯",
                value=f"{segment.start_time.isoformat()}-{segment.end_time.isoformat()}",
                impact="neutral",
            ),
            ExplanationFactor(
                key="assignment_source",
                label="割当元",
                value=segment.assignment_source,
                impact="neutral",
            ),
            ExplanationFactor(
                key="skill_match",
                label="スキル一致",
                value=f"{matched_count}/{len(required_skills)}",
                impact="positive" if matched_count == len(required_skills) else "negative",
            ),
        ],
        required_skills=required_skill_reads,
        current_warnings=[
            WarningExplanation(
                id=warning.id,
                warning_type=warning.warning_type,
                severity=warning.severity,
                message=warning.message,
            )
            for warning in warnings
        ],
        candidate_staff=candidates,
        lock_state=LockStateExplanation(
            is_locked=segment.is_locked,
            lock_scope=segment.lock_scope,
            lock_reason=segment.lock_reason,
        ),
    )


async def _list_required_skills(
    session: AsyncSession,
    segment: ShiftSegment,
) -> list[SkillDefinition]:
    result = await session.scalars(
        select(SkillDefinition)
        .where(SkillDefinition.store_id == segment.store_id)
        .where(SkillDefinition.is_active.is_(True))
        .where(SkillDefinition.position_id == segment.position_id)
        .where(SkillDefinition.task_type_id == segment.task_type_id)
        .order_by(SkillDefinition.code)
    )
    return list(result)


async def _list_staff_skill_ids(session: AsyncSession, staff_member_id: UUID) -> set[UUID]:
    result = await session.scalars(
        select(StaffSkill.skill_definition_id).where(
            StaffSkill.staff_member_id == staff_member_id
        )
    )
    return set(result)


async def _list_warnings(
    session: AsyncSession,
    segment: ShiftSegment,
) -> list[ScheduleWarning]:
    result = await session.scalars(
        select(ScheduleWarning)
        .where(ScheduleWarning.schedule_version_id == segment.schedule_version_id)
        .where(ScheduleWarning.shift_segment_id == segment.id)
        .order_by(ScheduleWarning.warning_type)
    )
    return list(result)


async def _list_candidate_staff(
    session: AsyncSession,
    store_id: UUID,
    required_skills: list[SkillDefinition],
) -> list[CandidateStaffExplanation]:
    staff_members = await session.scalars(
        select(StaffMember)
        .where(StaffMember.store_id == store_id)
        .where(StaffMember.is_active.is_(True))
        .order_by(StaffMember.priority, StaffMember.display_name)
    )
    required_skill_ids = {skill.id for skill in required_skills}
    candidates = []
    for staff_member in staff_members:
        skill_ids = await _list_staff_skill_ids(session, staff_member.id)
        matched = len(required_skill_ids.intersection(skill_ids))
        total = max(len(required_skill_ids), 1)
        fit_score = int((matched / total) * 100)
        candidates.append(
            CandidateStaffExplanation(
                staff_member_id=staff_member.id,
                display_name=staff_member.display_name,
                fit_score=fit_score,
                reason="必要スキルとの一致度によるダミー候補です。",
            )
        )
    return candidates[:5]
