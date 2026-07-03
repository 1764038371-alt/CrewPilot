from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.optimization.scope import OptimizationScopePayload
from app.modules.optimization.solver.base import (
    ScheduleSolver,
    SolverChange,
    SolverMetrics,
    SolverProposal,
)
from app.modules.schedule.models import ScheduleVersion, ShiftSegment
from app.modules.stores.models import Position


class DummySolver(ScheduleSolver):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def solve(
        self,
        schedule_version_id: UUID,
        scope: OptimizationScopePayload,
        time_limit_seconds: float,
    ) -> SolverProposal:
        schedule_version = await self.session.get(ScheduleVersion, schedule_version_id)
        if schedule_version is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Schedule version not found",
            )

        segment = await self._find_target_segment(schedule_version_id)
        position = await self._find_alternative_position(schedule_version.store_id, segment)
        return SolverProposal(
            title="AI提案: ポジション調整案",
            summary=f"DummySolverによる{scope.type.value}スコープのサンプル提案です。",
            generated_by="dummy_solver",
            changes=[
                SolverChange(
                    change_type="UPDATE_SEGMENT_POSITION",
                    target_type="ShiftSegment",
                    target_id=segment.id,
                    command_type="UpdateSegmentPosition",
                    command_payload={
                        "segment_id": str(segment.id),
                        "position_id": str(position.id),
                    },
                    before_value={
                        "segment_type": segment.segment_type,
                        "position_id": str(segment.position_id) if segment.position_id else None,
                        "task_type_id": str(segment.task_type_id) if segment.task_type_id else None,
                        "start_time": segment.start_time.isoformat(),
                        "end_time": segment.end_time.isoformat(),
                    },
                    after_value={
                        "segment_type": "WORK",
                        "position_id": str(position.id),
                        "task_type_id": None,
                        "start_time": segment.start_time.isoformat(),
                        "end_time": segment.end_time.isoformat(),
                    },
                    explanation={
                        "summary": "DummySolverによるサンプル変更です。",
                        "reasons": ["Solver Interfaceの接続確認"],
                    },
                )
            ],
            metrics=SolverMetrics(
                status="completed",
                solve_time_ms=0,
                objective_value=0,
                warning_before={},
                warning_after={},
                changed_segments=1,
                changed_work_shifts=0,
                fairness_score=0,
            ),
            summary_metrics={
                "created_work_shifts": 0,
                "deleted_work_shifts": 0,
                "updated_work_shifts": 0,
                "resolved_warnings": 0,
                "new_warnings": 0,
                "fairness_delta": 0,
                "target_staff_count": 1,
            },
        )

    async def _find_target_segment(self, schedule_version_id: UUID) -> ShiftSegment:
        result = await self.session.scalars(
            select(ShiftSegment)
            .where(ShiftSegment.schedule_version_id == schedule_version_id)
            .where(ShiftSegment.segment_type == "WORK")
            .where(ShiftSegment.is_locked.is_(False))
            .order_by(ShiftSegment.segment_date, ShiftSegment.start_time)
            .limit(1)
        )
        segment = result.first()
        if segment is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No editable WORK segment found",
            )
        return segment

    async def _find_alternative_position(
        self,
        store_id: UUID,
        segment: ShiftSegment,
    ) -> Position:
        result = await self.session.scalars(
            select(Position)
            .where(Position.store_id == store_id)
            .where(Position.is_active.is_(True))
            .where(Position.id != segment.position_id)
            .order_by(Position.priority)
            .limit(1)
        )
        position = result.first()
        if position is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No alternative position found",
            )
        return position
