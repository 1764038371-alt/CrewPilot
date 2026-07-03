import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import {
  redoScheduleCommand,
  undoScheduleCommand,
  type ScheduleCommand
} from "../api/scheduleCommandApi";
import { useEditingStore } from "../store/editingStore";
import { useSelectionStore, type WorkspaceClipboard } from "../store/selectionStore";
import type { WorkspaceData } from "../types";

type UseWorkspaceShortcutsArgs = {
  disabled?: boolean;
  onSave: () => void;
  workspace?: WorkspaceData;
};

export function useWorkspaceShortcuts({ disabled = false, onSave, workspace }: UseWorkspaceShortcutsArgs) {
  const queryClient = useQueryClient();
  const scheduleVersionId = workspace?.current_schedule_version?.id;
  const selection = useSelectionStore((state) => state.selection);
  const clipboard = useSelectionStore((state) => state.clipboard);
  const setClipboard = useSelectionStore((state) => state.setClipboard);
  const clearSelection = useSelectionStore((state) => state.clearSelection);
  const pendingCommands = useEditingStore((state) => state.pendingCommands);
  const redoCommands = useEditingStore((state) => state.redoCommands);
  const draftFieldHistory = useEditingStore((state) => state.draftFieldHistory);
  const draftFieldRedoStack = useEditingStore((state) => state.draftFieldRedoStack);
  const queueCommand = useEditingStore((state) => state.queueCommand);
  const undoDraftCommand = useEditingStore((state) => state.undoDraftCommand);
  const redoDraftCommand = useEditingStore((state) => state.redoDraftCommand);

  const invalidateWorkspace = () => {
    void queryClient.invalidateQueries({ queryKey: ["workspace"] });
    void queryClient.invalidateQueries({ queryKey: ["schedule-change-logs"] });
    void queryClient.invalidateQueries({ queryKey: ["optimization-proposals"] });
  };

  const undoMutation = useMutation({
    mutationFn: () => undoScheduleCommand(scheduleVersionId ?? ""),
    onSuccess: invalidateWorkspace
  });
  const redoMutation = useMutation({
    mutationFn: () => redoScheduleCommand(scheduleVersionId ?? ""),
    onSuccess: invalidateWorkspace
  });

  const runUndo = () => {
    if (pendingCommands.length > 0 || draftFieldHistory.length > 0) {
      undoDraftCommand();
      return;
    }
    if (scheduleVersionId && !undoMutation.isPending) {
      undoMutation.mutate();
    }
  };
  const runRedo = () => {
    if (redoCommands.length > 0 || draftFieldRedoStack.length > 0) {
      redoDraftCommand();
      return;
    }
    if (scheduleVersionId && !redoMutation.isPending) {
      redoMutation.mutate();
    }
  };
  const runSave = () => {
    onSave();
  };
  const runDelete = () => {
    const command = buildDeleteCommand(workspace, selection);
    if (!command) {
      return;
    }
    const label = selection?.type === "workShift" ? "勤務" : "セグメント";
    if (window.confirm(`選択中の${label}を削除しますか？`)) {
      queueCommand(command);
      clearSelection();
    }
  };
  const runCopy = () => {
    const nextClipboard = buildClipboard(workspace, selection);
    if (nextClipboard) {
      setClipboard(nextClipboard);
    }
  };
  const runPaste = () => {
    const command = buildPasteCommand(workspace, selection, clipboard);
    if (command) {
      queueCommand(command);
    }
  };

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (shouldIgnoreWorkspaceShortcut(event)) {
        return;
      }
      if (disabled) {
        if (event.key === "Escape") {
          event.preventDefault();
          clearSelection();
        }
        return;
      }
      const isModifier = event.metaKey || event.ctrlKey;
      const key = event.key.toLowerCase();
      if (isModifier && key === "z") {
        event.preventDefault();
        if (event.shiftKey) {
          runRedo();
          return;
        }
        runUndo();
        return;
      }
      if (isModifier && key === "s") {
        event.preventDefault();
        runSave();
        return;
      }
      if (isModifier && key === "c") {
        event.preventDefault();
        runCopy();
        return;
      }
      if (isModifier && key === "v") {
        event.preventDefault();
        runPaste();
        return;
      }
      if (event.key === "Delete" || event.key === "Backspace") {
        event.preventDefault();
        runDelete();
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        clearSelection();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  });

  return {
    redoPending: redoMutation.isPending,
    runRedo,
    runUndo,
    undoPending: undoMutation.isPending
  };
}

function shouldIgnoreWorkspaceShortcut(event: KeyboardEvent) {
  if (document.querySelector('[role="dialog"], dialog[open], [data-modal-open="true"]')) {
    return true;
  }
  const target = event.target;
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  const tagName = target.tagName.toLowerCase();
  return (
    target.isContentEditable ||
    tagName === "input" ||
    tagName === "textarea" ||
    tagName === "select"
  );
}

function buildDeleteCommand(
  workspace: WorkspaceData | undefined,
  selection: ReturnType<typeof useSelectionStore.getState>["selection"]
): ScheduleCommand | null {
  if (!workspace || !selection) {
    return null;
  }
  if (selection.type === "workShift") {
    return {
      type: "DeleteWorkShift",
      payload: {
        work_shift_id: selection.id
      }
    };
  }
  return {
    type: "DeleteShiftSegment",
    payload: {
      segment_id: selection.id
    }
  };
}

function buildClipboard(
  workspace: WorkspaceData | undefined,
  selection: ReturnType<typeof useSelectionStore.getState>["selection"]
): WorkspaceClipboard | null {
  if (!workspace || !selection) {
    return null;
  }
  if (selection.type === "workShift") {
    const shift = workspace.work_shifts.find((item) => item.id === selection.id);
    if (!shift) {
      return null;
    }
    return {
      type: "workShift",
      value: {
        ...shift,
        segments: workspace.shift_segments.filter((segment) => segment.work_shift_id === shift.id)
      }
    };
  }
  const segment = workspace.shift_segments.find((item) => item.id === selection.id);
  return segment ? { type: "shiftSegment", value: segment } : null;
}

function buildPasteCommand(
  workspace: WorkspaceData | undefined,
  selection: ReturnType<typeof useSelectionStore.getState>["selection"],
  clipboard: WorkspaceClipboard | null
): ScheduleCommand | null {
  if (!workspace || !clipboard) {
    return null;
  }
  if (clipboard.type === "shiftSegment") {
    const targetShift =
      selection?.type === "workShift"
        ? workspace.work_shifts.find((item) => item.id === selection.id)
        : null;
    if (!targetShift) {
      return null;
    }
    return {
      type: "RestoreShiftSegment",
      payload: {
        snapshot: {
          ...clipboard.value,
          id: crypto.randomUUID(),
          work_shift_id: targetShift.id,
          segment_date: targetShift.work_date
        }
      }
    };
  }
  return {
    type: "RestoreWorkShift",
    payload: {
      snapshot: duplicateWorkShiftSnapshot(clipboard.value)
    }
  };
}

function duplicateWorkShiftSnapshot(value: Record<string, unknown>) {
  const workShiftId = crypto.randomUUID();
  const segments = Array.isArray(value.segments)
    ? value.segments.map((segment) =>
        typeof segment === "object" && segment !== null
          ? {
              ...(segment as Record<string, unknown>),
              id: crypto.randomUUID(),
              work_shift_id: workShiftId
            }
          : segment
      )
    : [];
  return {
    ...value,
    id: workShiftId,
    segments
  };
}
