import { apiGet, apiPost } from "@/lib/api/client";
import type {
  OptimizationProposal,
  OptimizationRequest,
  OptimizationScope,
  ProposalActionResult,
  Uuid
} from "../types";

export function listProposals(scheduleVersionId: Uuid): Promise<OptimizationProposal[]> {
  return apiGet<OptimizationProposal[]>(`/api/schedule-versions/${scheduleVersionId}/proposals`);
}

export function generateProposal(
  scheduleVersionId: Uuid,
  scope: OptimizationScope
): Promise<OptimizationProposal> {
  const payload: OptimizationRequest = {
    scope,
    time_limit_seconds: 5
  };
  return apiPost<OptimizationProposal>(
    `/api/schedule-versions/${scheduleVersionId}/proposals/generate`,
    payload
  );
}

export function applyProposal(proposalId: Uuid): Promise<ProposalActionResult> {
  return apiPost<ProposalActionResult>(`/api/optimization-proposals/${proposalId}/apply`, {});
}

export function rejectProposal(proposalId: Uuid): Promise<ProposalActionResult> {
  return apiPost<ProposalActionResult>(`/api/optimization-proposals/${proposalId}/reject`, {});
}
