from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.optimization.solver.base import ScheduleSolver
from app.modules.optimization.solver.dummy_solver import DummySolver
from app.modules.optimization.solver.ortools_solver import ORToolsSolver


class SolverAdapter:
    def __init__(self, session: AsyncSession, solver_name: str = "dummy") -> None:
        self.session = session
        self.solver_name = solver_name

    def solver(self) -> ScheduleSolver:
        if self.solver_name == "ortools":
            return ORToolsSolver(self.session)
        return DummySolver(self.session)
