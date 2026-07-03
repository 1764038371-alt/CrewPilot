import { create } from "zustand";
import type { ScheduleCommand, ShiftSegmentDraft, WorkShiftDraft } from "../api/scheduleCommandApi";

export type DraftSaveStatus = "saved" | "unsaved" | "saving" | "failed";

type DraftFieldAction =
  | {
      type: "workShiftDraft";
      id: string;
      previous?: WorkShiftDraft;
      next: WorkShiftDraft;
    }
  | {
      type: "shiftSegmentDraft";
      id: string;
      previous?: ShiftSegmentDraft;
      next: ShiftSegmentDraft;
    };

type EditingState = {
  workShiftDrafts: Record<string, WorkShiftDraft>;
  shiftSegmentDrafts: Record<string, ShiftSegmentDraft>;
  pendingCommands: ScheduleCommand[];
  redoCommands: ScheduleCommand[];
  draftFieldHistory: DraftFieldAction[];
  draftFieldRedoStack: DraftFieldAction[];
  saveStatus: DraftSaveStatus;
  saveError: string | null;
  updateWorkShiftDraft: (id: string, patch: WorkShiftDraft) => void;
  updateShiftSegmentDraft: (id: string, patch: ShiftSegmentDraft) => void;
  clearWorkShiftDraft: (id: string) => void;
  clearShiftSegmentDraft: (id: string) => void;
  queueCommand: (command: ScheduleCommand) => void;
  undoDraftCommand: () => void;
  redoDraftCommand: () => void;
  clearDrafts: () => void;
  setSaveStatus: (status: DraftSaveStatus, error?: string | null) => void;
};

export const useEditingStore = create<EditingState>((set) => ({
  workShiftDrafts: {},
  shiftSegmentDrafts: {},
  pendingCommands: [],
  redoCommands: [],
  draftFieldHistory: [],
  draftFieldRedoStack: [],
  saveStatus: "saved",
  saveError: null,
  updateWorkShiftDraft: (id, patch) =>
    set((state) => {
      const previous = state.workShiftDrafts[id];
      const next = {
        ...previous,
        ...patch
      };
      return {
        workShiftDrafts: {
          ...state.workShiftDrafts,
          [id]: next
        },
        draftFieldHistory: [
          ...state.draftFieldHistory,
          {
            type: "workShiftDraft",
            id,
            previous,
            next
          }
        ],
        draftFieldRedoStack: [],
        saveStatus: "unsaved",
        saveError: null
      };
    }),
  updateShiftSegmentDraft: (id, patch) =>
    set((state) => {
      const previous = state.shiftSegmentDrafts[id];
      const next = {
        ...previous,
        ...patch
      };
      return {
        shiftSegmentDrafts: {
          ...state.shiftSegmentDrafts,
          [id]: next
        },
        draftFieldHistory: [
          ...state.draftFieldHistory,
          {
            type: "shiftSegmentDraft",
            id,
            previous,
            next
          }
        ],
        draftFieldRedoStack: [],
        saveStatus: "unsaved",
        saveError: null
      };
    }),
  clearWorkShiftDraft: (id) =>
    set((state) => {
      const remaining = { ...state.workShiftDrafts };
      delete remaining[id];
      return {
        workShiftDrafts: remaining,
        draftFieldHistory: state.draftFieldHistory.filter(
          (action) => action.type !== "workShiftDraft" || action.id !== id
        ),
        draftFieldRedoStack: state.draftFieldRedoStack.filter(
          (action) => action.type !== "workShiftDraft" || action.id !== id
        )
      };
    }),
  clearShiftSegmentDraft: (id) =>
    set((state) => {
      const remaining = { ...state.shiftSegmentDrafts };
      delete remaining[id];
      return {
        shiftSegmentDrafts: remaining,
        draftFieldHistory: state.draftFieldHistory.filter(
          (action) => action.type !== "shiftSegmentDraft" || action.id !== id
        ),
        draftFieldRedoStack: state.draftFieldRedoStack.filter(
          (action) => action.type !== "shiftSegmentDraft" || action.id !== id
        )
      };
    }),
  queueCommand: (command) =>
    set((state) => ({
      pendingCommands: [...state.pendingCommands, command],
      redoCommands: [],
      saveStatus: "unsaved",
      saveError: null
    })),
  undoDraftCommand: () =>
    set((state) => {
      const command = state.pendingCommands.at(-1);
      if (command) {
        return {
          pendingCommands: state.pendingCommands.slice(0, -1),
          redoCommands: [command, ...state.redoCommands],
          saveStatus:
            state.pendingCommands.length <= 1 &&
            Object.keys(state.workShiftDrafts).length === 0 &&
            Object.keys(state.shiftSegmentDrafts).length === 0
              ? "saved"
              : "unsaved",
          saveError: null
        };
      }
      const action = state.draftFieldHistory.at(-1);
      if (!action) {
        return {};
      }
      return {
        ...applyDraftFieldAction(state, action, "undo"),
        draftFieldHistory: state.draftFieldHistory.slice(0, -1),
        draftFieldRedoStack: [action, ...state.draftFieldRedoStack],
        saveStatus: hasUnsavedState({
          pendingCommands: state.pendingCommands,
          shiftSegmentDrafts: state.shiftSegmentDrafts,
          workShiftDrafts: state.workShiftDrafts,
          ...applyDraftFieldAction(state, action, "undo")
        })
          ? "unsaved"
          : "saved",
        saveError: null
      };
    }),
  redoDraftCommand: () =>
    set((state) => {
      const command = state.redoCommands[0];
      if (command) {
        return {
          pendingCommands: [...state.pendingCommands, command],
          redoCommands: state.redoCommands.slice(1),
          saveStatus: "unsaved",
          saveError: null
        };
      }
      const action = state.draftFieldRedoStack[0];
      if (!action) {
        return {};
      }
      return {
        ...applyDraftFieldAction(state, action, "redo"),
        draftFieldHistory: [...state.draftFieldHistory, action],
        draftFieldRedoStack: state.draftFieldRedoStack.slice(1),
        saveStatus: "unsaved",
        saveError: null
      };
    }),
  clearDrafts: () =>
    set({
      workShiftDrafts: {},
      shiftSegmentDrafts: {},
      pendingCommands: [],
      redoCommands: [],
      draftFieldHistory: [],
      draftFieldRedoStack: [],
      saveStatus: "saved",
      saveError: null
    }),
  setSaveStatus: (status, error = null) =>
    set({
      saveStatus: status,
      saveError: error
    })
}));

function applyDraftFieldAction(
  state: EditingState,
  action: DraftFieldAction,
  direction: "redo" | "undo"
) {
  if (action.type === "workShiftDraft") {
    const value = direction === "redo" ? action.next : action.previous;
    const workShiftDrafts = { ...state.workShiftDrafts };
    if (value && Object.keys(value).length > 0) {
      workShiftDrafts[action.id] = value;
    } else {
      delete workShiftDrafts[action.id];
    }
    return { workShiftDrafts };
  }
  const value = direction === "redo" ? action.next : action.previous;
  const shiftSegmentDrafts = { ...state.shiftSegmentDrafts };
  if (value && Object.keys(value).length > 0) {
    shiftSegmentDrafts[action.id] = value;
  } else {
    delete shiftSegmentDrafts[action.id];
  }
  return { shiftSegmentDrafts };
}

function hasUnsavedState(
  state: Pick<EditingState, "pendingCommands" | "shiftSegmentDrafts" | "workShiftDrafts">
) {
  return getUnsavedDraftCount(state) > 0;
}

export function hasDraftValue(draft: Record<string, unknown> | undefined) {
  return Boolean(draft && Object.keys(draft).length > 0);
}

export function getUnsavedDraftCount(state: Pick<EditingState, "pendingCommands" | "shiftSegmentDrafts" | "workShiftDrafts">) {
  return (
    state.pendingCommands.length +
    Object.keys(state.workShiftDrafts).length +
    Object.keys(state.shiftSegmentDrafts).length
  );
}
