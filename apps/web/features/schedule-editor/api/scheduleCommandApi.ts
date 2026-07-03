import { apiPost } from "@/lib/api/client";
import type { ShiftSegment, Uuid, WorkShift } from "../types";

export type WorkShiftDraft = Partial<Pick<WorkShift, "start_time" | "end_time">>;

export type ShiftSegmentDraft = Partial<
  Pick<
    ShiftSegment,
    "segment_type" | "position_id" | "task_type_id" | "is_locked" | "lock_scope" | "lock_reason"
  >
>;

export type ScheduleCommand =
  | {
      type: "CreateWorkShift";
      payload: {
        staff_member_id: Uuid;
        work_date: string;
        start_time: string;
        end_time: string;
        position_id?: Uuid | null;
        task_type_id?: Uuid | null;
        segments?: Array<{
          start_time: string;
          end_time: string;
          segment_type: "WORK" | "BREAK" | "TASK";
          position_id?: Uuid | null;
          task_type_id?: Uuid | null;
        }>;
      };
    }
  | {
      type: "RestoreWorkShift";
      payload: {
        snapshot: Record<string, unknown>;
      };
    }
  | {
      type: "DeleteWorkShift";
      payload: {
        work_shift_id: Uuid;
      };
    }
  | {
      type: "RestoreShiftSegment";
      payload: {
        snapshot: Record<string, unknown>;
      };
    }
  | {
      type: "DeleteShiftSegment";
      payload: {
        segment_id: Uuid;
      };
    }
  | {
      type: "AssignStaff";
      payload: {
        work_shift_id: Uuid;
        staff_member_id: Uuid;
      };
    }
  | {
      type: "CreateTaskSegment";
      payload: {
        work_shift_id: Uuid;
        start_time: string;
        end_time: string;
        task_type_id: Uuid;
      };
    }
  | {
      type: "CreateWorkSegment";
      payload: {
        work_shift_id: Uuid;
        start_time: string;
        end_time: string;
        position_id: Uuid;
      };
    }
  | {
      type: "MoveTaskSegment";
      payload: {
        segment_id: Uuid;
        start_time: string;
        end_time: string;
      };
    }
  | {
      type: "SplitSegment";
      payload: {
        segment_id: Uuid;
        split_time: string;
      };
    }
  | {
      type: "MergeSegment";
      payload: {
        first_segment_id: Uuid;
        second_segment_id: Uuid;
      };
    }
  | {
      type: "ResizeWorkShift";
      payload: {
        work_shift_id: Uuid;
        start_time: string;
        end_time: string;
      };
    }
  | {
      type: "ResizeSegment";
      payload: {
        segment_id: Uuid;
        start_time?: string;
        end_time?: string;
      };
    }
  | {
      type: "UpdateSegmentPosition";
      payload: {
        segment_id: Uuid;
        position_id: Uuid;
      };
    }
  | {
      type: "UpdateSegmentTask";
      payload: {
        segment_id: Uuid;
        task_type_id: Uuid;
      };
    }
  | {
      type: "UpdateSegmentBreak";
      payload: {
        segment_id: Uuid;
      };
    }
  | {
      type: "InsertBreak";
      payload: {
        work_shift_id: Uuid;
        start_time: string;
        end_time: string;
      };
    }
  | {
      type: "LockSegment";
      payload: {
        segment_id: Uuid;
        lock_scope?: string;
        lock_reason?: string | null;
      };
    }
  | {
      type: "UnlockSegment";
      payload: {
        segment_id: Uuid;
      };
    };

export type ScheduleCommandResult = {
  schedule_version_id: Uuid;
  revision: number;
  command_type: string;
  warnings_count: number;
};

export function executeScheduleCommand(
  scheduleVersionId: Uuid,
  command: ScheduleCommand,
  options?: {
    batchId?: Uuid;
    batchLabel?: string;
  }
): Promise<ScheduleCommandResult> {
  const headers: Record<string, string> = {};
  if (options?.batchId) {
    headers["X-CrewPilot-Batch-Id"] = options.batchId;
  }
  if (options?.batchLabel) {
    headers["X-CrewPilot-Batch-Label"] = options.batchLabel;
  }
  return apiPost<ScheduleCommandResult>(
    `/api/schedule-versions/${scheduleVersionId}/commands`,
    command,
    { headers }
  );
}

export function undoScheduleCommand(scheduleVersionId: Uuid): Promise<ScheduleCommandResult> {
  return apiPost<ScheduleCommandResult>(`/api/schedule-versions/${scheduleVersionId}/undo`, {});
}

export function redoScheduleCommand(scheduleVersionId: Uuid): Promise<ScheduleCommandResult> {
  return apiPost<ScheduleCommandResult>(`/api/schedule-versions/${scheduleVersionId}/redo`, {});
}
