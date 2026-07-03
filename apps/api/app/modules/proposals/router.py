from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.modules.auth.dependencies import ManagerUserDep
from app.modules.optimization.scope import OptimizationRequest
from app.modules.proposals.schemas import OptimizationProposalRead, ProposalActionResult
from app.modules.proposals.service import ProposalService

schedule_version_router = APIRouter(
    prefix="/schedule-versions",
    tags=["optimization-proposals"],
)
proposal_router = APIRouter(
    prefix="/optimization-proposals",
    tags=["optimization-proposals"],
)
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@schedule_version_router.post(
    "/{schedule_version_id}/proposals/generate",
    response_model=OptimizationProposalRead,
)
async def generate_proposal(
    schedule_version_id: UUID,
    payload: OptimizationRequest,
    session: SessionDep,
    user: ManagerUserDep,
) -> OptimizationProposalRead:
    return await ProposalService(session).generate(
        schedule_version_id,
        payload.scope,
        payload.time_limit_seconds,
    )


@schedule_version_router.get(
    "/{schedule_version_id}/proposals",
    response_model=list[OptimizationProposalRead],
)
async def list_proposals(
    schedule_version_id: UUID,
    session: SessionDep,
) -> list[OptimizationProposalRead]:
    return await ProposalService(session).list_proposals(schedule_version_id)


@proposal_router.get("/{proposal_id}", response_model=OptimizationProposalRead)
async def get_proposal(
    proposal_id: UUID,
    session: SessionDep,
) -> OptimizationProposalRead:
    return await ProposalService(session).get_proposal(proposal_id)


@proposal_router.post("/{proposal_id}/apply", response_model=ProposalActionResult)
async def apply_proposal(
    proposal_id: UUID,
    session: SessionDep,
    user: ManagerUserDep,
) -> ProposalActionResult:
    return await ProposalService(session).apply(proposal_id, actor=user)


@proposal_router.post("/{proposal_id}/reject", response_model=ProposalActionResult)
async def reject_proposal(
    proposal_id: UUID,
    session: SessionDep,
    user: ManagerUserDep,
) -> ProposalActionResult:
    return await ProposalService(session).reject(proposal_id)
