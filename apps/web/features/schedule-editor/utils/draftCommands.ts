import type { ScheduleCommand, ShiftSegmentDraft, WorkShiftDraft } from "../api/scheduleCommandApi";
import type { ShiftSegment, WorkShift, WorkspaceData } from "../types";

export function buildDraftCommands({
  pendingCommands,
  shiftSegmentDrafts,
  workspace,
  workShiftDrafts
}: {
  pendingCommands: ScheduleCommand[];
  shiftSegmentDrafts: Record<string, ShiftSegmentDraft>;
  workspace?: WorkspaceData;
  workShiftDrafts: Record<string, WorkShiftDraft>;
}) {
  const commands = [...pendingCommands];
  if (!workspace) {
    return commands;
  }

  for (const [workShiftId, draft] of Object.entries(workShiftDrafts)) {
    const shift = workspace.work_shifts.find((item) => item.id === workShiftId);
    if (!shift || !hasObjectKeys(draft)) {
      continue;
    }
    commands.push(buildWorkShiftDraftCommand(shift, draft));
  }

  for (const [segmentId, draft] of Object.entries(shiftSegmentDrafts)) {
    const segment = workspace.shift_segments.find((item) => item.id === segmentId);
    if (!segment || !hasObjectKeys(draft)) {
      continue;
    }
    const command = buildSegmentDraftCommand(segment, draft);
    if (command) {
      commands.push(command);
    }
  }

  return commands;
}

export function buildWorkShiftDraftCommand(
  shift: WorkShift,
  draft: WorkShiftDraft
): ScheduleCommand {
  return {
    type: "ResizeWorkShift",
    payload: {
      work_shift_id: shift.id,
      start_time: draft.start_time ?? shift.start_time,
      end_time: draft.end_time ?? shift.end_time
    }
  };
}

export function buildSegmentDraftCommand(
  segment: ShiftSegment,
  draft: ShiftSegmentDraft
): ScheduleCommand | null {
  if (typeof draft.is_locked === "boolean" && draft.is_locked !== segment.is_locked) {
    return draft.is_locked
      ? {
          type: "LockSegment",
          payload: {
            segment_id: segment.id,
            lock_scope: draft.lock_scope ?? "full",
            lock_reason: draft.lock_reason ?? null
          }
        }
      : {
          type: "UnlockSegment",
          payload: {
            segment_id: segment.id
          }
        };
  }

  if (draft.segment_type === "TASK" || segment.segment_type === "TASK") {
    const taskTypeId = draft.task_type_id ?? segment.task_type_id;
    return taskTypeId
      ? {
          type: "UpdateSegmentTask",
          payload: {
            segment_id: segment.id,
            task_type_id: taskTypeId
          }
        }
      : null;
  }

  if (draft.segment_type === "BREAK") {
    return {
      type: "UpdateSegmentBreak",
      payload: {
        segment_id: segment.id
      }
    };
  }

  const positionId = draft.position_id ?? segment.position_id;
  return positionId
    ? {
        type: "UpdateSegmentPosition",
        payload: {
          segment_id: segment.id,
          position_id: positionId
        }
      }
    : null;
}

function hasObjectKeys(value: object | undefined) {
  return Boolean(value && Object.keys(value).length > 0);
}
