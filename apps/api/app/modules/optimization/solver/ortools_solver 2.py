from __future__ import annotations

from uuid import UUID

from app.modules.optimization.scope import OptimizationScopePayload
from app.modules.optimization.solver.base import ScheduleSolver, SolverProposal


class ORToolsSolver(ScheduleSolver):
    async def solve(
        self,
        schedule_version_id: UUID,
        scope: OptimizationScopePayload,
    ) -> SolverProposal:
        raise NotImplementedError("OR-Tools constraints will be implemented in the next phase")
