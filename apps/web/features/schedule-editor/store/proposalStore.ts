import { create } from "zustand";

type ProposalHighlightMode = "before" | "after" | "add" | "delete" | null;

type ProposalState = {
  activeProposalId: string | null;
  activeProposalSegmentIds: Record<string, ProposalHighlightMode>;
  setActiveProposal: (
    proposalId: string | null,
    segmentHighlights?: Record<string, ProposalHighlightMode>
  ) => void;
};

export const useProposalStore = create<ProposalState>((set) => ({
  activeProposalId: null,
  activeProposalSegmentIds: {},
  setActiveProposal: (proposalId, segmentHighlights = {}) =>
    set({
      activeProposalId: proposalId,
      activeProposalSegmentIds: segmentHighlights
    })
}));
