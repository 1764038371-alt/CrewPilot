from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.optimization.adapter import SolverAdapter
from app.modules.optimization.scope import OptimizationScopePayload
from app.modules.optimization.solver.base import SolverProposal


class OptimizationService:
    def __init__(self, session: AsyncSession, solver_name: str | None = None) -> None:
        self.session = session
        self.solver_name = solver_name or settings.optimization_solver

    async def generate_proposal(
        self,
        schedule_version_id: UUID,
        scope: OptimizationScopePayload,
        time_limit_seconds: float,
    ) -> SolverProposal:
        solver = SolverAdapter(self.session, self.solver_name).solver()
        return await solver.solve(schedule_version_id, scope, time_limit_seconds)
