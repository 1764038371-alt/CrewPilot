import { create } from "zustand";

export type WorkspaceSelection =
  | {
      type: "workShift";
      id: string;
    }
  | {
      type: "shiftSegment";
      id: string;
    };

export type WorkspaceClipboard =
  | {
      type: "workShift";
      value: Record<string, unknown>;
    }
  | {
      type: "shiftSegment";
      value: Record<string, unknown>;
    };

type SelectionState = {
  selection: WorkspaceSelection | null;
  clipboard: WorkspaceClipboard | null;
  hoveredSegmentId: string | null;
  scrollTargetSegmentId: string | null;
  selectWorkShift: (id: string) => void;
  selectShiftSegment: (id: string) => void;
  setClipboard: (clipboard: WorkspaceClipboard | null) => void;
  clearSelection: () => void;
  setHoveredSegment: (id: string | null) => void;
  requestSegmentScroll: (id: string | null) => void;
};

export const useSelectionStore = create<SelectionState>((set) => ({
  selection: null,
  clipboard: null,
  hoveredSegmentId: null,
  scrollTargetSegmentId: null,
  selectWorkShift: (id) => set({ selection: { type: "workShift", id } }),
  selectShiftSegment: (id) => set({ selection: { type: "shiftSegment", id } }),
  setClipboard: (clipboard) => set({ clipboard }),
  clearSelection: () => set({ selection: null }),
  setHoveredSegment: (id) => set({ hoveredSegmentId: id }),
  requestSegmentScroll: (id) => set({ scrollTargetSegmentId: id })
}));
