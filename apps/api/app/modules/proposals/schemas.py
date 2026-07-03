from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProposalChangeRead(BaseModel):
    id: UUID
    proposal_id: UUID
    change_type: str
    target_type: str
    target_id: Optional[UUID]
    command_type: str
    command_payload: dict
    before_value: Optional[dict]
    after_value: Optional[dict]
    explanation: Optional[dict]
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class OptimizationProposalRead(BaseModel):
    id: UUID
    schedule_version_id: UUID
    optimization_run_id: Optional[UUID]
    title: str
    summary: Optional[str]
    summary_metrics: Optional[dict]
    status: str
    generated_by: str
    created_at: datetime
    applied_at: Optional[datetime]
    rejected_at: Optional[datetime]
    changes: list[ProposalChangeRead] = []

    model_config = ConfigDict(from_attributes=True)


class ProposalActionResult(BaseModel):
    proposal_id: UUID
    status: str
    applied_commands: int = 0
