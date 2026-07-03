import { Lock, Trash2, Unlock } from "lucide-react";
import type { ScheduleCommand } from "../api/scheduleCommandApi";
import { useEditingStore } from "../store/editingStore";
import { useSelectionStore } from "../store/selectionStore";
import type { ShiftSegment, WorkspaceData } from "../types";
import { positionDisplayLabel } from "../utils/positionLabels";
import { applyDraftCommands, autoMergeCommandsAfterCommand } from "./ShiftGrid";

type QuickEditBarProps = {
  isReadOnly: boolean;
  workspace?: WorkspaceData;
};

type QuickOption = {
  code: string;
  enabled: boolean;
  id?: string;
  isCurrent: boolean;
  label: string;
  reason: string;
  type: "position" | "task" | "break";
};

export function QuickEditBar({ isReadOnly, workspace }: QuickEditBarProps) {
  const selection = useSelectionStore((state) => state.selection);
  const pendingCommands = useEditingStore((state) => state.pendingCommands);
  const queueCommand = useEditingStore((state) => state.queueCommand);
  const workShiftDrafts = useEditingStore((state) => state.workShiftDrafts);

  if (!workspace || selection?.type !== "shiftSegment") {
    return (
      <div className="flex h-11 items-center justify-between border-b bg-white px-3 text-xs text-neutral-500">
        <span>セル未選択</span>
        <span>Draft操作はここに表示されます</span>
      </div>
    );
  }

  const draftWorkspace = applyDraftCommands(workspace, pendingCommands, workShiftDrafts);
  const segment = draftWorkspace.shift_segments.find((item) => item.id === selection.id);
  const shift = segment
    ? draftWorkspace.work_shifts.find((item) => item.id === segment.work_shift_id)
    : undefined;

  if (!segment || !shift) {
    return (
      <div className="flex h-11 items-center border-b bg-white px-3 text-xs text-neutral-500">
        選択中のセルが見つかりません
      </div>
    );
  }

  const staff = draftWorkspace.staff_members.find((item) => item.id === shift.staff_member_id);
  const options = quickOptions(draftWorkspace, shift, segment);
  const canEdit = !isReadOnly && !segment.is_locked;

  const runCommand = (command: ScheduleCommand | null) => {
    if (!command || isReadOnly) {
      return;
    }
    queueCommand(command);
    const affectedSegmentId = autoMergeTargetSegmentId(command);
    if (affectedSegmentId) {
      for (const mergeCommand of autoMergeCommandsAfterCommand(
        workspace,
        pendingCommands,
        workShiftDrafts,
        command,
        affectedSegmentId
      )) {
        queueCommand(mergeCommand);
      }
    }
  };

  return (
    <div className="flex min-h-11 items-center gap-3 overflow-x-auto border-b bg-white px-3 py-2 text-xs">
      <div className="shrink-0 font-medium text-neutral-800">
        {staff?.employee_number ?? staff?.display_name ?? "-"} / {segment.start_time.slice(0, 5)}-{segment.end_time.slice(0, 5)}
      </div>
      <div className="flex items-center gap-1">
        {options.map((option) => (
          <button
            className={quickOptionClassName(option.isCurrent)}
            disabled={!canEdit || !option.enabled || option.isCurrent}
            key={option.code}
            onClick={() => runCommand(commandForOption(segment, option))}
            title={segment.is_locked ? "ロック中は変更できません" : option.reason}
            type="button"
          >
            {option.code === "BREAK" ? "休憩" : option.code}
          </button>
        ))}
      </div>
      <div className="ml-auto flex items-center gap-1">
        <button
          className="inline-flex h-7 items-center gap-1 rounded border px-2 font-medium disabled:cursor-not-allowed disabled:bg-neutral-100 disabled:text-neutral-400"
          disabled={isReadOnly}
          onClick={() =>
            runCommand(
              segment.is_locked
                ? { type: "UnlockSegment", payload: { segment_id: segment.id } }
                : { type: "LockSegment", payload: { segment_id: segment.id, lock_scope: "segment", lock_reason: null } }
            )
          }
          type="button"
        >
          {segment.is_locked ? <Unlock className="h-3.5 w-3.5" /> : <Lock className="h-3.5 w-3.5" />}
          {segment.is_locked ? "解除" : "ロック"}
        </button>
        <button
          className="inline-flex h-7 items-center gap-1 rounded border border-red-200 px-2 font-medium text-red-700 disabled:cursor-not-allowed disabled:bg-neutral-100 disabled:text-neutral-400"
          disabled={!canEdit}
          onClick={() => {
            if (window.confirm("このセルを削除しますか？")) {
              runCommand({ type: "DeleteShiftSegment", payload: { segment_id: segment.id } });
            }
          }}
          type="button"
        >
          <Trash2 className="h-3.5 w-3.5" />
          削除
        </button>
      </div>
    </div>
  );
}

function quickOptionClassName(isCurrent: boolean) {
  return [
    "h-7 min-w-10 rounded border px-2 font-semibold disabled:cursor-not-allowed",
    isCurrent
      ? "border-neutral-950 bg-neutral-950 text-white"
      : "border-neutral-200 bg-white text-neutral-800 hover:border-neutral-400 disabled:bg-neutral-100 disabled:text-neutral-400"
  ].join(" ");
}

function quickOptions(
  workspace: WorkspaceData,
  shift: WorkspaceData["work_shifts"][number],
  segment: ShiftSegment
): QuickOption[] {
  const staffSkillIds = new Set(
    workspace.staff_skills
      .filter((skill) => skill.staff_member_id === shift.staff_member_id)
      .map((skill) => skill.skill_definition_id)
  );

  const positionOptions: QuickOption[] = (["B", "C", "F", "S"] as const).map((code) => {
    const position = workspace.positions.find((item) => item.code === code);
    const skill = workspace.skill_definitions.find(
      (item) => item.code === code && item.skill_category === "position"
    );
    const hasSkill = Boolean(skill && staffSkillIds.has(skill.id));
    return {
      code,
      enabled: Boolean(position && hasSkill),
      id: position?.id,
      isCurrent: segment.segment_type === "WORK" && segment.position_id === position?.id,
      label: positionDisplayLabel(code, position?.name),
      reason: !position ? "ポジション未設定" : hasSkill ? `${positionDisplayLabel(code, position.name)}スキルあり` : `${positionDisplayLabel(code, position?.name)}スキルなし`,
      type: "position"
    };
  });

  const taskM = workspace.task_types.find((item) => item.code === "M");
  const mSkill = workspace.skill_definitions.find(
    (item) => item.code === "M" && item.skill_category === "task"
  );
  const hasM = Boolean(mSkill && staffSkillIds.has(mSkill.id));
  const mTimeValid = isValidDepositManualWindow(workspace, shift, segment);
  const mOption: QuickOption = {
    code: "M",
    enabled: Boolean(taskM && hasM && mTimeValid),
    id: taskM?.id,
    isCurrent: segment.segment_type === "TASK" && segment.task_type_id === taskM?.id,
    label: positionDisplayLabel("M", taskM?.name),
    reason: !taskM
      ? "Mタスク未設定"
      : !hasM
        ? "M / 入金スキルなし"
        : mTimeValid
          ? "M / 入金スキルあり"
          : "M / 入金は10:00-10:30またはクローズ30分のみ",
    type: "task"
  };

  return [
    ...positionOptions,
    mOption,
    {
      code: "BREAK",
      enabled: true,
      isCurrent: segment.segment_type === "BREAK",
      label: "BREAK / 休憩",
      reason: "休憩",
      type: "break"
    }
  ];
}

function commandForOption(segment: ShiftSegment, option: QuickOption): ScheduleCommand | null {
  if (option.isCurrent || !option.enabled) {
    return null;
  }
  if (option.type === "position" && option.id) {
    return {
      type: "UpdateSegmentPosition",
      payload: {
        segment_id: segment.id,
        position_id: option.id
      }
    };
  }
  if (option.type === "task" && option.id) {
    return {
      type: "UpdateSegmentTask",
      payload: {
        segment_id: segment.id,
        task_type_id: option.id
      }
    };
  }
  if (option.type === "break") {
    return {
      type: "UpdateSegmentBreak",
      payload: {
        segment_id: segment.id
      }
    };
  }
  return null;
}

function autoMergeTargetSegmentId(command: ScheduleCommand) {
  if (
    command.type === "UpdateSegmentPosition" ||
    command.type === "UpdateSegmentTask" ||
    command.type === "UpdateSegmentBreak" ||
    command.type === "ResizeSegment"
  ) {
    return command.payload.segment_id;
  }
  return null;
}

function isValidDepositManualWindow(
  workspace: WorkspaceData,
  shift: WorkspaceData["work_shifts"][number],
  segment: ShiftSegment
) {
  if (segment.start_time.slice(0, 5) === "10:00" && segment.end_time.slice(0, 5) === "10:30") {
    return true;
  }
  const close = closingTimeForDate(workspace, shift.work_date);
  const closeMinute = timeToMinutes(close);
  return (
    timeToMinutes(segment.start_time) === closeMinute - 30
    && timeToMinutes(segment.end_time) === closeMinute
  );
}

function closingTimeForDate(workspace: WorkspaceData, workDate: string) {
  const day = new Date(`${workDate}T00:00:00`).getDay();
  const dayType = day === 0 || day === 6 ? "holiday" : "weekday";
  const businessHours = workspace.store.business_hours as
    | Record<string, { close?: string; closing_time?: string }>
    | null;
  return (
    businessHours?.[dayType]?.close
    ?? businessHours?.[dayType]?.closing_time
    ?? workspace.store.closing_time
  );
}

function timeToMinutes(value: string) {
  const [hour = "0", minute = "0"] = value.slice(0, 5).split(":");
  return Number(hour) * 60 + Number(minute);
}
