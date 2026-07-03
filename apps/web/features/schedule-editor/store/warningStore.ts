import { create } from "zustand";

type WarningState = {
  activeWarningId: string | null;
  activeWarningSegmentId: string | null;
  setActiveWarning: (warningId: string | null, segmentId?: string | null) => void;
};

export const useWarningStore = create<WarningState>((set) => ({
  activeWarningId: null,
  activeWarningSegmentId: null,
  setActiveWarning: (warningId, segmentId = null) =>
    set({
      activeWarningId: warningId,
      activeWarningSegmentId: segmentId
    })
}));
