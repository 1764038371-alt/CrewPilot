from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from app.modules.optimization.scope import OptimizationScopePayload


@dataclass
class SolverChange:
    change_type: str
    target_type: str
    target_id: Optional[UUID]
    command_type: str
    command_payload: dict
    before_value: Optional[dict]
    after_value: Optional[dict]
    explanation: Optional[dict] = None


@dataclass
class SolverMetrics:
    status: str
    solve_time_ms: int
    objective_value: Optional[int]
    warning_before: dict
    warning_after: dict
    changed_segments: int
    changed_work_shifts: int
    fairness_score: Optional[int] = None


@dataclass
class SolverProposal:
    title: str
    summary: str
    generated_by: str
    changes: list[SolverChange]
    metrics: SolverMetrics
    summary_metrics: Optional[dict] = None


class ScheduleSolver:
    async def solve(
        self,
        schedule_version_id: UUID,
        scope: OptimizationScopePayload,
        time_limit_seconds: float,
    ) -> SolverProposal:
        raise NotImplementedError
