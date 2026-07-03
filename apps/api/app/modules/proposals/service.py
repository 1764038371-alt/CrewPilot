from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auth.models import User
from app.modules.optimization.scope import OptimizationScopePayload
from app.modules.optimization.service import OptimizationService
from app.modules.proposals.schemas import OptimizationProposalRead, ProposalActionResult
from app.modules.schedule.models import (
    OptimizationProposal,
    OptimizationRun,
    ProposalChange,
)
from app.modules.schedule_editor.commands import ScheduleCommand
from app.modules.schedule_editor.service import ScheduleCommandService
from app.modules.schedule_editor.warnings import WarningService


class ProposalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def generate(
        self,
        schedule_version_id: UUID,
        scope: OptimizationScopePayload,
        time_limit_seconds: float,
    ) -> OptimizationProposalRead:
        await WarningService(self.session).recalculate(schedule_version_id)
        solver_proposal = await OptimizationService(self.session).generate_proposal(
            schedule_version_id,
            scope,
            time_limit_seconds,
        )
        optimization_run = OptimizationRun(
            schedule_version_id=schedule_version_id,
            solver_name=solver_proposal.generated_by,
            status=solver_proposal.metrics.status,
            scope=scope.model_dump(mode="json"),
            solve_time_ms=solver_proposal.metrics.solve_time_ms,
            objective_value=solver_proposal.metrics.objective_value,
            warning_before=solver_proposal.metrics.warning_before,
            warning_after=solver_proposal.metrics.warning_after,
            changed_segments=solver_proposal.metrics.changed_segments,
            changed_work_shifts=solver_proposal.metrics.changed_work_shifts,
            fairness_score=solver_proposal.metrics.fairness_score,
        )
        self.session.add(optimization_run)
        await self.session.flush()
        proposal = OptimizationProposal(
            schedule_version_id=schedule_version_id,
            optimization_run_id=optimization_run.id,
            title=solver_proposal.title,
            summary=solver_proposal.summary,
            summary_metrics=solver_proposal.summary_metrics,
            status="pending",
            generated_by=solver_proposal.generated_by,
        )
        self.session.add(proposal)
        await self.session.flush()

        for index, change in enumerate(solver_proposal.changes):
            self.session.add(
                ProposalChange(
                    proposal_id=proposal.id,
                    change_type=change.change_type,
                    target_type=change.target_type,
                    target_id=change.target_id,
                    command_type=change.command_type,
                    command_payload=change.command_payload,
                    before_value=change.before_value,
                    after_value=change.after_value,
                    explanation=change.explanation,
                    sort_order=index,
                )
            )
        await self.session.commit()
        return await self.get_proposal(proposal.id)

    async def list_proposals(self, schedule_version_id: UUID) -> list[OptimizationProposalRead]:
        result = await self.session.scalars(
            select(OptimizationProposal)
            .options(selectinload(OptimizationProposal.changes))
            .where(OptimizationProposal.schedule_version_id == schedule_version_id)
            .order_by(OptimizationProposal.created_at.desc())
        )
        return [OptimizationProposalRead.model_validate(item) for item in result]

    async def get_proposal(self, proposal_id: UUID) -> OptimizationProposalRead:
        proposal = await self._get_proposal_model(proposal_id)
        return OptimizationProposalRead.model_validate(proposal)

    async def apply(
        self,
        proposal_id: UUID,
        *,
        actor: User | None = None,
    ) -> ProposalActionResult:
        proposal = await self._get_proposal_model(proposal_id)
        if proposal.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Proposal is not pending",
            )

        adapter = TypeAdapter(ScheduleCommand)
        applied_commands = 0
        batch_id = proposal.id
        for change in sorted(proposal.changes, key=lambda item: item.sort_order):
            command = adapter.validate_python(
                {
                    "type": change.command_type,
                    "payload": change.command_payload,
                }
            )
            await ScheduleCommandService(self.session).execute(
                proposal.schedule_version_id,
                command,
                actor=actor,
                source_type="proposal",
                source_id=proposal.id,
                batch_id=batch_id,
                batch_label=f"Proposal Apply: {proposal.title}",
                explanation=change.explanation,
            )
            applied_commands += 1

        proposal.status = "applied"
        proposal.applied_at = datetime.utcnow()
        await self.session.commit()
        return ProposalActionResult(
            proposal_id=proposal.id,
            status=proposal.status,
            applied_commands=applied_commands,
        )

    async def reject(self, proposal_id: UUID) -> ProposalActionResult:
        proposal = await self._get_proposal_model(proposal_id)
        if proposal.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Proposal is not pending",
            )

        proposal.status = "rejected"
        proposal.rejected_at = datetime.utcnow()
        await self.session.commit()
        return ProposalActionResult(proposal_id=proposal.id, status=proposal.status)

    async def _get_proposal_model(self, proposal_id: UUID) -> OptimizationProposal:
        result = await self.session.scalars(
            select(OptimizationProposal)
            .options(selectinload(OptimizationProposal.changes))
            .where(OptimizationProposal.id == proposal_id)
        )
        proposal = result.first()
        if proposal is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proposal not found",
            )
        return proposal
