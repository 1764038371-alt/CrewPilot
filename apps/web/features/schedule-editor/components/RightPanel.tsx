import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Download,
  GitMerge,
  History,
  Lock,
  Save,
  Scissors,
  TriangleAlert
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { ApiError } from "@/lib/api/client";
import { getShiftSegmentExplanation } from "../api/explanationApi";
import { listOptimizationRuns, listScheduleChangeLogs } from "../api/historyApi";
import {
  applyProposal,
  generateProposal,
  listProposals,
  rejectProposal
} from "../api/proposalApi";
import {
  type ScheduleCommand,
  type ShiftSegmentDraft,
  type WorkShiftDraft
} from "../api/scheduleCommandApi";
import { hasDraftValue, useEditingStore } from "../store/editingStore";
import { useProposalStore } from "../store/proposalStore";
import { useSelectionStore } from "../store/selectionStore";
import { useWarningStore } from "../store/warningStore";
import { buildSegmentDraftCommand } from "../utils/draftCommands";
import { positionDisplayLabel } from "../utils/positionLabels";
import { applyDraftCommands, autoMergeCommandsAfterCommand } from "./ShiftGrid";
import type {
  OptimizationProposal,
  OptimizationRun,
  ProposalChange,
  ScheduleChangeLog,
  ScheduleWarning,
  ShiftSegmentExplanation,
  ShiftSegment,
  WorkShift,
  WorkspaceData
} from "../types";

type RightPanelProps = {
  activeTab?: PanelTab;
  isReadOnly?: boolean;
  onActiveTabChange?: (tab: PanelTab) => void;
  selectedDate?: string;
  workspace?: WorkspaceData;
};

export type PanelTab = "warnings" | "proposals" | "details" | "lock" | "history";

export function RightPanel({
  activeTab: activeTabProp,
  isReadOnly = false,
  onActiveTabChange,
  selectedDate,
  workspace
}: RightPanelProps) {
  const [localActiveTab, setLocalActiveTab] = useState<PanelTab>("details");
  const activeTab = activeTabProp ?? localActiveTab;
  const setActiveTab = (tab: PanelTab) => {
    setLocalActiveTab(tab);
    onActiveTabChange?.(tab);
  };
  const queryClient = useQueryClient();
  const selection = useSelectionStore((state) => state.selection);
  const selectWorkShift = useSelectionStore((state) => state.selectWorkShift);
  const selectShiftSegment = useSelectionStore((state) => state.selectShiftSegment);
  const requestSegmentScroll = useSelectionStore((state) => state.requestSegmentScroll);
  const workShiftDrafts = useEditingStore((state) => state.workShiftDrafts);
  const shiftSegmentDrafts = useEditingStore((state) => state.shiftSegmentDrafts);
  const pendingCommands = useEditingStore((state) => state.pendingCommands);
  const updateWorkShiftDraft = useEditingStore((state) => state.updateWorkShiftDraft);
  const updateShiftSegmentDraft = useEditingStore((state) => state.updateShiftSegmentDraft);
  const clearWorkShiftDraft = useEditingStore((state) => state.clearWorkShiftDraft);
  const clearShiftSegmentDraft = useEditingStore((state) => state.clearShiftSegmentDraft);
  const queueCommand = useEditingStore((state) => state.queueCommand);
  const saveStatus = useEditingStore((state) => state.saveStatus);
  const setActiveProposal = useProposalStore((state) => state.setActiveProposal);
  const setActiveWarning = useWarningStore((state) => state.setActiveWarning);
  const draftWorkspace = workspace
    ? applyDraftCommands(workspace, pendingCommands, workShiftDrafts)
    : undefined;

  const selectedWorkShift =
    selection?.type === "workShift"
      ? draftWorkspace?.work_shifts.find((item) => item.id === selection.id)
      : undefined;
  const selectedSegment =
    selection?.type === "shiftSegment"
      ? draftWorkspace?.shift_segments.find((item) => item.id === selection.id)
      : undefined;
  const selectedSegmentShift = selectedSegment
    ? draftWorkspace?.work_shifts.find((item) => item.id === selectedSegment.work_shift_id)
    : undefined;
  const nextSegment = selectedSegment
    ? findNextSegment(draftWorkspace?.shift_segments ?? [], selectedSegment)
    : undefined;
  const scheduleVersionId = workspace?.current_schedule_version?.id;

  const proposalsQuery = useQuery({
    queryKey: ["optimization-proposals", scheduleVersionId],
    queryFn: () => listProposals(scheduleVersionId ?? ""),
    enabled: Boolean(scheduleVersionId)
  });
  const historyQuery = useQuery({
    queryKey: ["schedule-change-logs", scheduleVersionId],
    queryFn: () => listScheduleChangeLogs(scheduleVersionId ?? ""),
    enabled: Boolean(scheduleVersionId)
  });
  const optimizationRunsQuery = useQuery({
    queryKey: ["optimization-runs", scheduleVersionId],
    queryFn: () => listOptimizationRuns(scheduleVersionId ?? ""),
    enabled: Boolean(scheduleVersionId)
  });
  const explanationQuery = useQuery({
    queryKey: ["shift-segment-explanation", selectedSegment?.id],
    queryFn: () => getShiftSegmentExplanation(selectedSegment?.id ?? ""),
    enabled: Boolean(selectedSegment?.id)
  });

  const generateMutation = useMutation({
    mutationFn: () => {
      if (!scheduleVersionId) {
        throw new Error("ScheduleVersionがありません。");
      }
      return generateProposal(scheduleVersionId, { type: "full" });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["optimization-proposals"] });
      void queryClient.invalidateQueries({ queryKey: ["optimization-runs"] });
    }
  });

  const applyMutation = useMutation({
    mutationFn: (proposalId: string) => applyProposal(proposalId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["workspace"] });
      void queryClient.invalidateQueries({ queryKey: ["optimization-proposals"] });
      void queryClient.invalidateQueries({ queryKey: ["optimization-runs"] });
      void queryClient.invalidateQueries({ queryKey: ["schedule-change-logs"] });
    }
  });

  const rejectMutation = useMutation({
    mutationFn: (proposalId: string) => rejectProposal(proposalId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["optimization-proposals"] });
    }
  });

  const executeCommand = (command: ScheduleCommand) => {
    if (isReadOnly) {
      return;
    }
    queueCommand(command);
    const affectedSegmentId = autoMergeTargetSegmentId(command);
    if (workspace && affectedSegmentId) {
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
  const mutationError = generateMutation.error ?? applyMutation.error ?? rejectMutation.error;
  const errorMessage = mutationError ? formatCommandError(mutationError) : null;
  const commandPending = saveStatus === "saving";
  const visibleWarnings = filterWarningsByDate(draftWorkspace, selectedDate);
  const criticalWarnings = visibleWarnings.filter((warning) => warning.severity === "critical");

  const selectWarning = (warning: ScheduleWarning) => {
    const isShiftWideBreakShortage =
      warning.warning_type === "BREAK_VIOLATION"
      && typeof warning.details?.required_break_minutes === "number";
    if (isShiftWideBreakShortage && warning.work_shift_id) {
      setActiveWarning(warning.id, null);
      selectWorkShift(warning.work_shift_id);
      setActiveTab("details");
      return;
    }
    setActiveWarning(warning.id, warning.shift_segment_id);
    if (warning.shift_segment_id) {
      selectShiftSegment(warning.shift_segment_id);
      requestSegmentScroll(warning.shift_segment_id);
      setActiveTab("details");
      return;
    }
    if (warning.work_shift_id) {
      selectWorkShift(warning.work_shift_id);
      setActiveTab("details");
    }
  };

  return (
    <aside className="min-h-0 overflow-auto bg-white">
      <div className="space-y-4 p-4">
        <WarningSummary
          criticalWarnings={criticalWarnings}
          onOpenWarnings={() => setActiveTab("warnings")}
          totalCount={visibleWarnings.length}
        />
        <SecondaryNavigation activeTab={activeTab} onSelect={setActiveTab} />
        <PanelGuide activeTab={activeTab} warningsCount={visibleWarnings.length} />
        {errorMessage && (
          <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {errorMessage}
          </div>
        )}
        {activeTab === "details" && (
          <DetailsPanel
            commandPending={commandPending}
            isReadOnly={isReadOnly}
            clearShiftSegmentDraft={clearShiftSegmentDraft}
            clearWorkShiftDraft={clearWorkShiftDraft}
            executeCommand={executeCommand}
            nextSegment={nextSegment}
            segmentExplanation={explanationQuery.data}
            segmentExplanationLoading={explanationQuery.isFetching}
            selectedSegment={selectedSegment}
            selectedSegmentDraft={selectedSegment ? shiftSegmentDrafts[selectedSegment.id] : undefined}
            selectedSegmentShift={selectedSegmentShift}
            selectedWorkShift={selectedWorkShift}
            selectedWorkShiftDraft={
              selectedWorkShift ? workShiftDrafts[selectedWorkShift.id] : undefined
            }
            updateShiftSegmentDraft={updateShiftSegmentDraft}
            updateWorkShiftDraft={updateWorkShiftDraft}
            workspace={draftWorkspace}
          />
        )}
        {activeTab === "warnings" && (
          <WarningsPanel
            onSelectWarning={selectWarning}
            warnings={visibleWarnings}
          />
        )}
        {activeTab === "proposals" && (
          <ProposalPanel
            applyPending={applyMutation.isPending}
            generatePending={generateMutation.isPending}
            onApply={(proposalId) => applyMutation.mutate(proposalId)}
            onGenerate={() => generateMutation.mutate()}
            onReject={(proposalId) => rejectMutation.mutate(proposalId)}
            onSelectProposal={(proposal) =>
              setActiveProposal(proposal.id, proposalHighlights(proposal))
            }
            proposals={proposalsQuery.data ?? []}
            rejectPending={rejectMutation.isPending}
          />
        )}
        {activeTab === "lock" && (
          <LockPanel selectedSegment={selectedSegment} selectedWorkShift={selectedWorkShift} />
        )}
        {activeTab === "history" && (
          <HistoryPanel logs={historyQuery.data ?? []} runs={optimizationRunsQuery.data ?? []} />
        )}
        <details className="rounded border border-neutral-200 p-3">
          <summary className="cursor-pointer text-sm font-medium text-neutral-700">シフト全体の情報</summary>
          <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
            <dt className="text-neutral-500">登録スタッフ</dt>
            <dd className="text-right">{draftWorkspace?.staff_members.length ?? "-"}</dd>
            <dt className="text-neutral-500">勤務</dt>
            <dd className="text-right">{draftWorkspace?.work_shifts.length ?? "-"}</dd>
            <dt className="text-neutral-500">問題</dt>
            <dd className="text-right">{visibleWarnings.length}</dd>
          </dl>
        </details>
      </div>
    </aside>
  );
}

function WarningSummary({
  criticalWarnings,
  onOpenWarnings,
  totalCount
}: {
  criticalWarnings: ScheduleWarning[];
  onOpenWarnings: () => void;
  totalCount: number;
}) {
  if (criticalWarnings.length > 0) {
    return (
      <button
        className="w-full rounded-lg border border-red-300 bg-red-50 p-3 text-left text-red-900 hover:bg-red-100"
        onClick={onOpenWarnings}
        type="button"
      >
        <span className="flex items-center gap-2 font-semibold">
          <TriangleAlert className="h-5 w-5" />
          重大な問題が{criticalWarnings.length}件あります
        </span>
        <span className="mt-1 block text-xs">公開前に確認してください。クリックすると一覧を開きます。</span>
      </button>
    );
  }
  return (
    <button
      className="flex w-full items-center justify-between rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-left text-sm hover:bg-neutral-100"
      onClick={onOpenWarnings}
      type="button"
    >
      <span className="flex items-center gap-2 font-medium text-neutral-800">
        <TriangleAlert className="h-4 w-4 text-amber-600" />
        確認する問題
      </span>
      <span className="rounded-full bg-white px-2 py-0.5 text-xs text-neutral-700">{totalCount}件</span>
    </button>
  );
}

function SecondaryNavigation({
  activeTab,
  onSelect
}: {
  activeTab: PanelTab;
  onSelect: (tab: PanelTab) => void;
}) {
  const items: Array<{ icon: ReactNode; label: string; tab: PanelTab }> = [
    { icon: <TriangleAlert className="h-3.5 w-3.5" />, label: "問題一覧", tab: "warnings" },
    { icon: <Lock className="h-3.5 w-3.5" />, label: "固定", tab: "lock" },
    { icon: <History className="h-3.5 w-3.5" />, label: "履歴", tab: "history" }
  ];
  return (
    <div>
      <p className="mb-1.5 text-[11px] font-medium text-neutral-500">補助機能</p>
      <div className="flex gap-1.5">
        {items.map((item) => (
          <button
            className={
              activeTab === item.tab
                ? "flex items-center gap-1 rounded-md bg-neutral-900 px-2.5 py-1.5 text-xs text-white"
                : "flex items-center gap-1 rounded-md border border-neutral-200 px-2.5 py-1.5 text-xs text-neutral-700 hover:bg-neutral-50"
            }
            key={item.tab}
            onClick={() => onSelect(item.tab)}
            type="button"
          >
            {item.icon}
            {item.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function filterWarningsByDate(workspace?: WorkspaceData, selectedDate?: string) {
  const warnings = workspace?.warnings ?? [];
  if (!workspace || !selectedDate) {
    return warnings;
  }
  return warnings.filter((warning) => warningMatchesSelectedDate(warning, workspace, selectedDate));
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

function warningMatchesSelectedDate(
  warning: ScheduleWarning,
  workspace: WorkspaceData,
  selectedDate: string
) {
  const detailsDate = typeof warning.details?.date === "string" ? warning.details.date : null;
  if (detailsDate) {
    return detailsDate === selectedDate;
  }
  if (warning.shift_segment_id) {
    const segment = workspace.shift_segments.find((item) => item.id === warning.shift_segment_id);
    return segment ? segment.segment_date === selectedDate : true;
  }
  if (warning.work_shift_id) {
    const shift = workspace.work_shifts.find((item) => item.id === warning.work_shift_id);
    return shift ? shift.work_date === selectedDate : true;
  }
  return true;
}

function PanelGuide({ activeTab, warningsCount }: { activeTab: PanelTab; warningsCount: number }) {
  const guide = {
    warnings: {
      title: `直すべき警告 ${warningsCount}件`,
      body: "クリックすると対象のセルや勤務へ移動します。まず警告を減らしてから公開します。"
    },
    proposals: {
      title: "AI提案",
      body: "AIが作った変更案を確認し、納得できるものだけ適用します。適用前にシフトは直接変わりません。"
    },
    details: {
      title: "選択中の詳細",
      body: "セルをクリックすると、割当理由・スキル・ロック状態を確認できます。"
    },
    lock: {
      title: "固定管理",
      body: "動かしたくないセルはロックします。再生成してもロック部分は維持します。"
    },
    history: {
      title: "変更履歴",
      body: "誰がいつ何を変更したかを確認します。Undo/Redoの関係もここで追えます。"
    }
  } satisfies Record<PanelTab, { title: string; body: string }>;
  return (
    <div className="rounded border bg-neutral-50 p-3 text-xs text-neutral-600">
      <div className="font-semibold text-neutral-900">{guide[activeTab].title}</div>
      <p className="mt-1 leading-relaxed">{guide[activeTab].body}</p>
    </div>
  );
}

function DetailsPanel({
  commandPending,
  clearShiftSegmentDraft,
  clearWorkShiftDraft,
  executeCommand,
  isReadOnly,
  nextSegment,
  segmentExplanation,
  segmentExplanationLoading,
  selectedSegment,
  selectedSegmentDraft,
  selectedSegmentShift,
  selectedWorkShift,
  selectedWorkShiftDraft,
  updateShiftSegmentDraft,
  updateWorkShiftDraft,
  workspace
}: {
  commandPending: boolean;
  clearShiftSegmentDraft: (id: string) => void;
  clearWorkShiftDraft: (id: string) => void;
  executeCommand: (command: ScheduleCommand) => void;
  isReadOnly: boolean;
  nextSegment?: ShiftSegment;
  segmentExplanation?: ShiftSegmentExplanation;
  segmentExplanationLoading: boolean;
  selectedSegment?: ShiftSegment;
  selectedSegmentDraft?: ShiftSegmentDraft;
  selectedSegmentShift?: WorkShift;
  selectedWorkShift?: WorkShift;
  selectedWorkShiftDraft?: WorkShiftDraft;
  updateShiftSegmentDraft: (id: string, patch: ShiftSegmentDraft) => void;
  updateWorkShiftDraft: (id: string, patch: WorkShiftDraft) => void;
  workspace?: WorkspaceData;
}) {
  return (
    <section>
      <h2 className="text-sm font-semibold">詳細</h2>
      {!selectedWorkShift && !selectedSegment && (
        <p className="mt-2 text-sm text-neutral-500">勤務またはセグメントを選択</p>
      )}
      {selectedWorkShift && !selectedSegment && (
        <WorkShiftExplanation shift={selectedWorkShift} workspace={workspace} />
      )}
      {selectedSegment && (
        <SegmentExplanation
          explanation={segmentExplanation}
          isLoading={segmentExplanationLoading}
          segment={selectedSegment}
        />
      )}
      {workspace && selectedWorkShift && (
        <WorkShiftEditor
          draft={selectedWorkShiftDraft}
          isReadOnly={isReadOnly}
          isSaving={commandPending || isReadOnly}
          onChange={(patch) => updateWorkShiftDraft(selectedWorkShift.id, patch)}
          onInsertBreak={(startTime, endTime) =>
            executeCommand({
              type: "InsertBreak",
              payload: {
                work_shift_id: selectedWorkShift.id,
                start_time: startTime,
                end_time: endTime
              }
            })
          }
          onSave={() => {
            const draft = selectedWorkShiftDraft ?? {};
            executeCommand({
              type: "ResizeWorkShift",
              payload: {
                work_shift_id: selectedWorkShift.id,
                start_time: draft.start_time ?? selectedWorkShift.start_time,
                end_time: draft.end_time ?? selectedWorkShift.end_time
              }
            });
            clearWorkShiftDraft(selectedWorkShift.id);
          }}
          shift={selectedWorkShift}
          staffName={
            workspace.staff_members.find((item) => item.id === selectedWorkShift.staff_member_id)
              ?.display_name ?? "Unknown"
          }
        />
      )}
      {workspace && selectedSegment && (
        <ShiftSegmentEditor
          draft={selectedSegmentDraft}
          isReadOnly={isReadOnly}
          isSaving={commandPending || isReadOnly}
          nextSegment={nextSegment}
          onChange={(patch) => updateShiftSegmentDraft(selectedSegment.id, patch)}
          onMergeNext={() => {
            if (!nextSegment) {
              return;
            }
            executeCommand({
              type: "MergeSegment",
              payload: {
                first_segment_id: selectedSegment.id,
                second_segment_id: nextSegment.id
              }
            });
          }}
          onSave={() => {
            const command = buildSegmentDraftCommand(selectedSegment, selectedSegmentDraft ?? {});
            if (command) {
              executeCommand(command);
              clearShiftSegmentDraft(selectedSegment.id);
            }
          }}
          onSplit={(splitTime) =>
            executeCommand({
              type: "SplitSegment",
              payload: {
                segment_id: selectedSegment.id,
                split_time: splitTime
              }
            })
          }
          positions={workspace.positions}
          segment={selectedSegment}
          shift={selectedSegmentShift}
          taskTypes={workspace.task_types}
        />
      )}
    </section>
  );
}

function WorkShiftExplanation({
  shift,
  workspace
}: {
  shift: WorkShift;
  workspace?: WorkspaceData;
}) {
  const staff = workspace?.staff_members.find((item) => item.id === shift.staff_member_id);
  const warnings =
    workspace?.warnings.filter((warning) => warning.work_shift_id === shift.id) ?? [];
  return (
    <div className="mt-2 space-y-3 rounded border bg-neutral-50 p-3 text-sm">
      <div>
        <div className="text-xs font-semibold text-neutral-500">割当理由</div>
        <p className="mt-1">
          {staff?.display_name ?? "スタッフ"}の勤務時間と現在のセグメント構成をもとに表示しています。
        </p>
      </div>
      <InfoRows
        rows={[
          ["ロック状態", shift.is_locked ? "固定中" : "未固定"],
          ["現在の警告", `${warnings.length}件`],
          ["候補スタッフ", "田中 / 佐藤 / 鈴木"]
        ]}
      />
    </div>
  );
}

function SegmentExplanation({
  explanation,
  isLoading,
  segment
}: {
  explanation?: ShiftSegmentExplanation;
  isLoading: boolean;
  segment: ShiftSegment;
}) {
  if (isLoading) {
    return <p className="mt-2 rounded border p-3 text-sm text-neutral-500">説明を取得中</p>;
  }
  if (!explanation) {
    return (
      <p className="mt-2 rounded border p-3 text-sm text-neutral-500">
        このセグメントの説明はまだありません。
      </p>
    );
  }

  return (
    <div className="mt-2 space-y-3 rounded border bg-neutral-50 p-3 text-sm">
      <div>
        <div className="text-xs font-semibold text-neutral-500">割当理由</div>
        <p className="mt-1">{explanation.assignment_reason}</p>
      </div>
      <div>
        <div className="text-xs font-semibold text-neutral-500">必要スキル</div>
        <div className="mt-2 flex flex-wrap gap-1">
          {explanation.required_skills.length ? (
            explanation.required_skills.map((skill) => (
              <span
                className={
                  skill.matched
                    ? "rounded bg-emerald-100 px-2 py-1 text-xs text-emerald-800"
                    : "rounded bg-red-100 px-2 py-1 text-xs text-red-800"
                }
                key={skill.id}
              >
                {skill.code}
              </span>
            ))
          ) : (
            <span className="text-neutral-500">必要スキルなし</span>
          )}
        </div>
      </div>
      <InfoRows
        rows={[
          ["現在の警告", `${explanation.current_warnings.length}件`],
          ["ロック状態", explanation.lock_state.is_locked ? "固定中" : "未固定"],
          ["対象", `${segment.start_time.slice(0, 5)}-${segment.end_time.slice(0, 5)}`]
        ]}
      />
      <div>
        <div className="text-xs font-semibold text-neutral-500">候補スタッフ</div>
        <ul className="mt-2 space-y-1">
          {explanation.candidate_staff.map((candidate) => (
            <li className="flex justify-between rounded bg-white px-2 py-1" key={candidate.staff_member_id}>
              <span>{candidate.display_name}</span>
              <span className="text-neutral-500">{candidate.fit_score}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function InfoRows({ rows }: { rows: Array<[string, string]> }) {
  return (
    <dl className="grid grid-cols-2 gap-2">
      {rows.map(([label, value]) => (
        <div className="contents" key={label}>
          <dt className="text-xs text-neutral-500">{label}</dt>
          <dd className="text-right text-xs">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function WarningsPanel({
  onSelectWarning,
  warnings
}: {
  onSelectWarning: (warning: ScheduleWarning) => void;
  warnings: ScheduleWarning[];
}) {
  return (
    <section>
      <h2 className="text-sm font-semibold">警告一覧</h2>
      {warnings.length ? (
        <ul className="mt-2 space-y-2 text-sm">
          {warnings.map((warning) => (
            <li key={warning.id}>
              <button
                className={`w-full rounded border p-2 text-left ${warningCardClassName(warning.severity)}`}
                onClick={() => onSelectWarning(warning)}
                type="button"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{warningTitle(warning)}</span>
                  <span className="rounded bg-white/70 px-1.5 py-0.5 text-xs">{warningSeverityLabel(warning.severity)}</span>
                </div>
                <p className="mt-1 text-neutral-700">{warning.message}</p>
                <p className="mt-1 text-xs">{warningTargetLabel(warning)}</p>
                {warningFixHint(warning) && (
                  <p className="mt-1 rounded bg-white/70 px-2 py-1 text-xs text-neutral-700">
                    {warningFixHint(warning)}
                  </p>
                )}
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-neutral-500">警告なし</p>
      )}
    </section>
  );
}

function warningCardClassName(severity: string) {
  return severity === "critical"
    ? "border-red-300 bg-red-50 text-red-900 hover:bg-red-100"
    : "border-amber-200 bg-amber-50 text-amber-900 hover:bg-amber-100";
}

function warningTitle(warning: ScheduleWarning) {
  const titles: Record<string, string> = {
    BREAK_VIOLATION: "休憩ルール違反",
    BC_COVERAGE: "B/C配置不足",
    CLOSING_STAFF_SHORTAGE: "クローズ人数不足",
    DEPOSIT_INVALID_TIME: "入金Mの時間違反",
    DEPOSIT_MISSING: "入金Mの担当不足",
    OPEN_CLOSE_SKILL_SHORTAGE: "開店/閉店スキル不足",
    OPENING_STAFF_SHORTAGE: "開店人数不足",
    REQUEST_VIOLATION: "希望シフト違反",
    SKILL_MISMATCH: "スキル不一致",
    STAFF_SHORTAGE: "必要人数不足"
  };
  return titles[warning.warning_type] ?? warning.warning_type;
}

function warningSeverityLabel(severity: string) {
  if (severity === "critical") {
    return "重大";
  }
  if (severity === "warning") {
    return "注意";
  }
  return severity;
}

function warningTargetLabel(warning: ScheduleWarning) {
  const details = warning.details ?? {};
  const date = typeof details.date === "string" ? details.date : null;
  const startTime = typeof details.start_time === "string" ? details.start_time.slice(0, 5) : null;
  const endTime = typeof details.end_time === "string" ? details.end_time.slice(0, 5) : null;
  const currentCount = typeof details.current_count === "number" ? details.current_count : null;
  const minStaffCount = typeof details.min_staff_count === "number" ? details.min_staff_count : null;
  const target = warning.shift_segment_id
    ? "対象: セル"
    : warning.work_shift_id
      ? "対象: 勤務"
      : "対象: 時間帯";

  if (date && startTime && endTime) {
    const count = currentCount !== null && minStaffCount !== null
      ? ` / 現在${currentCount}人・必要${minStaffCount}人`
      : "";
    return `${target} / ${date} ${startTime}-${endTime}${count}`;
  }
  if (date) {
    return `${target} / ${date}`;
  }
  return target;
}

function warningFixHint(warning: ScheduleWarning) {
  if (warning.warning_type === "STAFF_SHORTAGE") {
    return "対処: この時間帯に勤務を追加するか、希望入力からシフト案を作り直します。";
  }
  if (warning.warning_type === "BC_COVERAGE") {
    return "対処: この時間帯でB / バリとC / キャッシャーが両方残るよう、ポジションまたは休憩位置を調整します。";
  }
  if (warning.warning_type === "SKILL_MISMATCH") {
    return "対処: スキルを持つスタッフへ変更するか、ポジションを変更します。";
  }
  if (warning.warning_type === "OPENING_STAFF_SHORTAGE") {
    return "対処: 開店時刻から勤務できるスタッフを増やし、オープンBとオープンCを分担します。";
  }
  if (warning.warning_type === "CLOSING_STAFF_SHORTAGE") {
    return "対処: 閉店時刻まで勤務できるスタッフを増やし、クローズを3人以上にします。";
  }
  if (warning.warning_type === "OPEN_CLOSE_SKILL_SHORTAGE") {
    return "対処: オープンB/オープンCなど該当スキルを持つスタッフを開店・閉店帯へ配置します。";
  }
  if (warning.warning_type === "BREAK_VIOLATION") {
    return "対処: 休憩を分割・移動して、必要な休憩時間を満たします。";
  }
  if (warning.warning_type === "REQUEST_VIOLATION") {
    return "対処: 希望時間内へ勤務を移動するか、採用しない判断にします。";
  }
  if (warning.warning_type.startsWith("DEPOSIT")) {
    return "対処: M / 入金を10:00-10:30、または前日クローズ30分に配置します。";
  }
  return null;
}

function ProposalPanel({
  applyPending,
  generatePending,
  onApply,
  onGenerate,
  onReject,
  onSelectProposal,
  proposals,
  rejectPending
}: {
  applyPending: boolean;
  generatePending: boolean;
  onApply: (proposalId: string) => void;
  onGenerate: () => void;
  onReject: (proposalId: string) => void;
  onSelectProposal: (proposal: OptimizationProposal) => void;
  proposals: OptimizationProposal[];
  rejectPending: boolean;
}) {
  return (
    <section>
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">AI Proposal</h2>
        <button
          className="rounded bg-neutral-950 px-3 py-1.5 text-xs text-white disabled:bg-neutral-300"
          disabled={generatePending}
          onClick={onGenerate}
          type="button"
        >
          {generatePending ? "生成中" : "提案生成"}
        </button>
      </div>
      {proposals.length ? (
        <div className="mt-3 space-y-3">
          {proposals.map((proposal) => (
            <ProposalCard
              applyPending={applyPending}
              key={proposal.id}
              onApply={() => onApply(proposal.id)}
              onReject={() => onReject(proposal.id)}
              onSelect={() => onSelectProposal(proposal)}
              proposal={proposal}
              rejectPending={rejectPending}
            />
          ))}
        </div>
      ) : (
        <p className="mt-2 text-sm text-neutral-500">AI提案はまだありません。</p>
      )}
    </section>
  );
}

function ProposalCard({
  applyPending,
  onApply,
  onReject,
  onSelect,
  proposal,
  rejectPending
}: {
  applyPending: boolean;
  onApply: () => void;
  onReject: () => void;
  onSelect: () => void;
  proposal: OptimizationProposal;
  rejectPending: boolean;
}) {
  const isPending = proposal.status === "pending";
  return (
    <article className="rounded border p-3 text-sm">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="font-medium">{proposal.title}</h3>
          <p className="mt-1 text-xs text-neutral-500">{proposal.summary}</p>
        </div>
        <span className="rounded bg-neutral-100 px-2 py-1 text-xs">{proposal.status}</span>
      </div>
      <button
        className="mt-2 w-full rounded border px-3 py-1.5 text-left text-xs hover:bg-neutral-50"
        onClick={onSelect}
        type="button"
      >
        グリッドで変更箇所をハイライト
      </button>
      {proposal.summary_metrics && <ProposalSummaryMetrics metrics={proposal.summary_metrics} />}
      <div className="mt-3 space-y-2">
        {proposal.changes.map((change) => (
          <ProposalChangeView change={change} key={change.id} />
        ))}
      </div>
      {isPending && (
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button
            className="rounded bg-neutral-950 px-3 py-2 text-sm text-white disabled:bg-neutral-300"
            disabled={applyPending}
            onClick={onApply}
            type="button"
          >
            適用
          </button>
          <button
            className="rounded border px-3 py-2 text-sm disabled:bg-neutral-100"
            disabled={rejectPending}
            onClick={onReject}
            type="button"
          >
            却下
          </button>
        </div>
      )}
    </article>
  );
}

function ProposalSummaryMetrics({ metrics }: { metrics: Record<string, number> }) {
  const rows: Array<[string, number | undefined]> = [
    ["追加勤務", metrics.created_work_shifts],
    ["削除勤務", metrics.deleted_work_shifts],
    ["変更勤務", metrics.updated_work_shifts],
    ["解消警告", metrics.resolved_warnings],
    ["新規警告", metrics.new_warnings],
    ["公平性改善", metrics.fairness_delta],
    ["対象スタッフ", metrics.target_staff_count]
  ];
  return (
    <dl className="mt-3 grid grid-cols-2 gap-1 rounded bg-neutral-50 p-2 text-xs">
      {rows.map(([label, value]) => (
        <div className="contents" key={label}>
          <dt className="text-neutral-500">{label}</dt>
          <dd className="text-right">{value ?? 0}</dd>
        </div>
      ))}
    </dl>
  );
}

function ProposalChangeView({ change }: { change: ProposalChange }) {
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const reasons = Array.isArray(change.explanation?.reasons)
    ? change.explanation.reasons.filter((item): item is string => typeof item === "string")
    : [];
  const explanationSummary =
    typeof change.explanation?.summary === "string" ? change.explanation.summary : null;
  return (
    <div className="rounded bg-neutral-50 p-2">
      <div className="flex items-center justify-between gap-2">
        <div>
          <div className="text-xs font-semibold text-neutral-700">{proposalCommandLabel(change.command_type)}</div>
          <div className="mt-0.5 text-[11px] text-neutral-500">{change.change_type}</div>
        </div>
        <button
          className="rounded border bg-white px-2 py-1 text-[11px] text-neutral-600 hover:bg-neutral-50"
          onClick={() => setIsDetailOpen((current) => !current)}
          type="button"
        >
          {isDetailOpen ? "詳細を閉じる" : "詳細JSON"}
        </button>
      </div>
      {explanationSummary && (
        <p className="mt-1 text-xs text-neutral-600">{explanationSummary}</p>
      )}
      {reasons.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-1">
          {reasons.map((reason) => (
            <li className="rounded bg-sky-100 px-2 py-1 text-[11px] text-sky-800" key={reason}>
              {reason}
            </li>
          ))}
        </ul>
      )}
      {isDetailOpen && (
        <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
          <DiffBox label="変更前" mode="before" value={change.before_value} />
          <DiffBox label="変更後" mode="after" value={change.after_value} />
        </div>
      )}
    </div>
  );
}

function proposalCommandLabel(commandType: string) {
  const labels: Record<string, string> = {
    CreateWorkShift: "勤務を追加",
    DeleteShiftSegment: "セルを削除",
    DeleteWorkShift: "勤務を削除",
    InsertBreak: "休憩を追加",
    MergeSegment: "セルを結合",
    ResizeSegment: "セル時間を変更",
    ResizeWorkShift: "勤務時間を変更",
    SplitSegment: "セルを分割",
    UpdateSegmentBreak: "休憩へ変更",
    UpdateSegmentPosition: "ポジション変更",
    UpdateSegmentTask: "タスク変更"
  };
  return labels[commandType] ?? commandType;
}

function DiffBox({
  label,
  mode,
  value
}: {
  label: string;
  mode: "before" | "after" | "add" | "delete";
  value: unknown;
}) {
  return (
    <div className={diffBoxClassName(mode)}>
      <div className="mb-1 font-medium text-neutral-500">{label}</div>
      <pre className="whitespace-pre-wrap break-all text-[11px] leading-4">
        {JSON.stringify(value ?? {}, null, 2)}
      </pre>
    </div>
  );
}

function diffBoxClassName(mode: "before" | "after" | "add" | "delete") {
  if (mode === "before") {
    return "rounded border border-red-200 bg-red-50 p-2";
  }
  if (mode === "after") {
    return "rounded border border-emerald-200 bg-emerald-50 p-2";
  }
  if (mode === "add") {
    return "rounded border border-blue-200 bg-blue-50 p-2";
  }
  return "rounded border border-neutral-300 bg-neutral-50 p-2";
}

function LockPanel({
  selectedSegment,
  selectedWorkShift
}: {
  selectedSegment?: ShiftSegment;
  selectedWorkShift?: WorkShift;
}) {
  const target = selectedSegment ?? selectedWorkShift;
  return (
    <section>
      <h2 className="text-sm font-semibold">固定</h2>
      {target ? (
        <div className="mt-2 rounded border p-3 text-sm">
          <InfoRows
            rows={[
              ["状態", target.is_locked ? "固定中" : "未固定"],
              ["範囲", target.lock_scope ?? "-"],
              ["理由", target.lock_reason ?? "-"]
            ]}
          />
        </div>
      ) : (
        <p className="mt-2 text-sm text-neutral-500">勤務またはセグメントを選択</p>
      )}
    </section>
  );
}

function HistoryPanel({ logs, runs }: { logs: ScheduleChangeLog[]; runs: OptimizationRun[] }) {
  const [filters, setFilters] = useState({
    user: "",
    date: "",
    command: "",
    target: "",
    source: "",
    status: ""
  });
  const [selectedLogId, setSelectedLogId] = useState<string | null>(null);
  const users = uniqueOptions(logs.map((log) => log.executed_by));
  const commands = uniqueOptions(logs.map((log) => log.command_type));
  const targets = uniqueOptions(logs.map((log) => targetLabel(log)));
  const filteredLogs = logs.filter((log) => {
    if (filters.user && log.executed_by !== filters.user) {
      return false;
    }
    if (filters.date && !log.created_at.startsWith(filters.date)) {
      return false;
    }
    if (filters.command && log.command_type !== filters.command) {
      return false;
    }
    if (filters.target && targetLabel(log) !== filters.target) {
      return false;
    }
    if (filters.source === "proposal" && log.source_type !== "proposal") {
      return false;
    }
    if (filters.source === "batch" && !log.batch_id) {
      return false;
    }
    if (filters.status === "undone" && !log.is_undone) {
      return false;
    }
    if (filters.status === "redo" && log.source_type !== "redo") {
      return false;
    }
    return true;
  });
  const selectedLog = filteredLogs.find((log) => log.id === selectedLogId) ?? filteredLogs[0] ?? null;

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-sm font-semibold">Solver Metrics</h2>
        {runs.length ? (
          <ul className="mt-2 space-y-2 text-sm">
            {runs.map((run) => (
              <li className="rounded border border-sky-200 bg-sky-50 p-2" key={run.id}>
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{run.solver_name}</span>
                  <span className="rounded bg-white px-2 py-1 text-xs">{run.status}</span>
                </div>
                <dl className="mt-2 grid grid-cols-2 gap-1 text-xs">
                  <dt className="text-neutral-500">solve_time_ms</dt>
                  <dd className="text-right">{run.solve_time_ms}</dd>
                  <dt className="text-neutral-500">objective</dt>
                  <dd className="text-right">{run.objective_value ?? "-"}</dd>
                  <dt className="text-neutral-500">changed_segments</dt>
                  <dd className="text-right">{run.changed_segments}</dd>
                  <dt className="text-neutral-500">fairness_score</dt>
                  <dd className="text-right">{run.fairness_score ?? "-"}</dd>
                  <dt className="text-neutral-500">warnings</dt>
                  <dd className="text-right">
                    {sumWarningCounts(run.warning_before)} → {sumWarningCounts(run.warning_after)}
                  </dd>
                </dl>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-neutral-500">Solver実行履歴はまだありません。</p>
        )}
      </div>
      <div>
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold">Audit Log</h2>
          <button
            className="inline-flex items-center gap-1 rounded border px-2 py-1 text-xs disabled:bg-neutral-100 disabled:text-neutral-400"
            disabled={filteredLogs.length === 0}
            onClick={() => exportAuditCsv(filteredLogs)}
            type="button"
          >
            <Download className="h-3.5 w-3.5" />
            CSV
          </button>
        </div>
        <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
          <AuditSelect
            label="実行者"
            onChange={(value) => setFilters((current) => ({ ...current, user: value }))}
            options={users}
            value={filters.user}
          />
          <label className="block">
            <span className="text-neutral-500">日付</span>
            <input
              className="mt-1 w-full rounded border px-2 py-1"
              onChange={(event) => setFilters((current) => ({ ...current, date: event.target.value }))}
              type="date"
              value={filters.date}
            />
          </label>
          <AuditSelect
            label="Command"
            onChange={(value) => setFilters((current) => ({ ...current, command: value }))}
            options={commands}
            value={filters.command}
          />
          <AuditSelect
            label="対象"
            onChange={(value) => setFilters((current) => ({ ...current, target: value }))}
            options={targets}
            value={filters.target}
          />
          <AuditSelect
            label="由来"
            onChange={(value) => setFilters((current) => ({ ...current, source: value }))}
            options={["proposal", "batch"]}
            value={filters.source}
          />
          <AuditSelect
            label="状態"
            onChange={(value) => setFilters((current) => ({ ...current, status: value }))}
            options={["undone", "redo"]}
            value={filters.status}
          />
        </div>
        {filteredLogs.length ? (
          <ul className="mt-3 space-y-2 text-sm">
            {filteredLogs.map((log) => (
              <li key={log.id}>
                <button
                  className={`w-full rounded border p-2 text-left ${
                    selectedLog?.id === log.id ? "border-neutral-900 bg-neutral-50" : "bg-white"
                  }`}
                  onClick={() => setSelectedLogId(log.id)}
                  type="button"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="font-medium">{log.command_type}</div>
                      <div className="mt-1 text-xs text-neutral-500">{targetLabel(log)}</div>
                    </div>
                    <span className="text-xs text-neutral-500">{formatDateTime(log.created_at)}</span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1 text-xs">
                    <AuditBadge>{log.executed_by}</AuditBadge>
                    {log.batch_id && <AuditBadge>Batch</AuditBadge>}
                    {log.source_type === "proposal" && <AuditBadge>Proposal</AuditBadge>}
                    {log.source_type === "undo" && <AuditBadge tone="warning">Undo操作</AuditBadge>}
                    {log.parent_change_log_id && <AuditBadge>Parent</AuditBadge>}
                    {log.is_undone && <AuditBadge tone="warning">Undo済み</AuditBadge>}
                    {log.source_type === "redo" && <AuditBadge tone="success">Redo済み</AuditBadge>}
                  </div>
                  <dl className="mt-2 grid grid-cols-2 gap-1 text-xs">
                    <dt className="text-neutral-500">Before</dt>
                    <dd className="truncate text-right">{compactJson(log.before_value)}</dd>
                    <dt className="text-neutral-500">After</dt>
                    <dd className="truncate text-right">{compactJson(log.after_value)}</dd>
                  </dl>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-neutral-500">条件に一致するAudit Logはありません。</p>
        )}
        {selectedLog && <AuditDetail log={selectedLog} />}
      </div>
    </section>
  );
}

function AuditSelect({
  label,
  onChange,
  options,
  value
}: {
  label: string;
  onChange: (value: string) => void;
  options: string[];
  value: string;
}) {
  return (
    <label className="block">
      <span className="text-neutral-500">{label}</span>
      <select
        className="mt-1 w-full rounded border px-2 py-1"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        <option value="">すべて</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function AuditBadge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "success" | "warning" }) {
  const className =
    tone === "success"
      ? "bg-emerald-50 text-emerald-700"
      : tone === "warning"
        ? "bg-amber-50 text-amber-800"
        : "bg-neutral-100 text-neutral-700";
  return <span className={`rounded px-1.5 py-0.5 ${className}`}>{children}</span>;
}

function AuditDetail({ log }: { log: ScheduleChangeLog }) {
  return (
    <div className="mt-3 rounded border bg-white p-2 text-xs">
      <div className="font-semibold">詳細</div>
      <dl className="mt-2 grid grid-cols-2 gap-1">
        <dt className="text-neutral-500">Change ID</dt>
        <dd className="break-all text-right">{log.id}</dd>
        <dt className="text-neutral-500">Parent Change ID</dt>
        <dd className="break-all text-right">{log.parent_change_log_id ?? "-"}</dd>
        <dt className="text-neutral-500">Batch</dt>
        <dd className="break-all text-right">{log.batch_label ?? log.batch_id ?? "-"}</dd>
        <dt className="text-neutral-500">Source</dt>
        <dd className="break-all text-right">{log.source_type ? `${log.source_type}:${log.source_id ?? "-"}` : "-"}</dd>
      </dl>
      <AuditJson title="command_payload" value={log.command_payload} />
      <AuditJson title="inverse_payload" value={log.inverse_payload} />
      <AuditJson title="before_value" value={log.before_value} />
      <AuditJson title="after_value" value={log.after_value} />
      <AuditJson title="explanation" value={log.explanation} />
    </div>
  );
}

function AuditJson({ title, value }: { title: string; value: unknown }) {
  return (
    <details className="mt-2">
      <summary className="cursor-pointer text-neutral-500">{title}</summary>
      <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap break-all rounded bg-neutral-50 p-2">
        {JSON.stringify(value ?? null, null, 2)}
      </pre>
    </details>
  );
}

function targetLabel(log: ScheduleChangeLog) {
  if (log.shift_segment_id) {
    return `ShiftSegment:${log.shift_segment_id.slice(0, 8)}`;
  }
  if (log.work_shift_id) {
    return `WorkShift:${log.work_shift_id.slice(0, 8)}`;
  }
  return "-";
}

function compactJson(value: unknown) {
  if (value == null) {
    return "-";
  }
  const text = JSON.stringify(value);
  return text.length > 64 ? `${text.slice(0, 64)}...` : text;
}

function uniqueOptions(values: string[]) {
  return Array.from(new Set(values.filter(Boolean))).sort();
}

function exportAuditCsv(logs: ScheduleChangeLog[]) {
  const rows = [
    ["Timestamp", "User", "Command", "Target", "Before", "After", "Undo", "Parent Change ID"],
    ...logs.map((log) => [
      log.created_at,
      log.executed_by,
      log.command_type,
      targetLabel(log),
      JSON.stringify(log.before_value ?? null),
      JSON.stringify(log.after_value ?? null),
      log.is_undone ? "true" : "false",
      log.parent_change_log_id ?? ""
    ])
  ];
  const csv = rows.map((row) => row.map(csvCell).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `crewpilot-audit-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function csvCell(value: string) {
  return `"${value.replaceAll('"', '""')}"`;
}

function sumWarningCounts(counts: Record<string, number>) {
  return Object.values(counts).reduce((total, count) => total + count, 0);
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("ja-JP", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

function proposalHighlights(proposal: OptimizationProposal) {
  const highlights: Record<string, "before" | "after" | "add" | "delete" | null> = {};
  for (const change of proposal.changes) {
    if (change.target_type !== "ShiftSegment" || !change.target_id) {
      continue;
    }
    if (change.change_type.includes("CREATE") || change.change_type.includes("ADD")) {
      highlights[change.target_id] = "add";
    } else if (change.change_type.includes("DELETE")) {
      highlights[change.target_id] = "delete";
    } else {
      highlights[change.target_id] = "after";
    }
  }
  return highlights;
}

function WorkShiftEditor({
  draft,
  isReadOnly,
  isSaving,
  onChange,
  onInsertBreak,
  onSave,
  shift,
  staffName
}: {
  draft?: WorkShiftDraft;
  isReadOnly: boolean;
  isSaving: boolean;
  onChange: (patch: WorkShiftDraft) => void;
  onInsertBreak: (startTime: string, endTime: string) => void;
  onSave: () => void;
  shift: WorkShift;
  staffName: string;
}) {
  const merged = { ...shift, ...draft };
  const isDirty = hasDraftValue(draft);
  const [breakStartTime, setBreakStartTime] = useState(defaultBreakStart(shift));
  const [breakEndTime, setBreakEndTime] = useState(defaultBreakEnd(shift));

  return (
    <div className="mt-2 space-y-3 rounded border p-3">
      <div className="text-sm font-medium">{staffName}</div>
      <div className="grid grid-cols-2 gap-2">
        <Field label="開始">
          <input
            className="w-full rounded border px-2 py-1"
            disabled={isReadOnly}
            onChange={(event) => onChange({ start_time: normalizeTimeInput(event.target.value) })}
            type="time"
            value={timeInputValue(merged.start_time)}
          />
        </Field>
        <Field label="終了">
          <input
            className="w-full rounded border px-2 py-1"
            disabled={isReadOnly}
            onChange={(event) => onChange({ end_time: normalizeTimeInput(event.target.value) })}
            type="time"
            value={timeInputValue(merged.end_time)}
          />
        </Field>
      </div>
      <SaveButton disabled={!isDirty || isSaving} isSaving={isSaving} onClick={onSave} />
      <div className="rounded border bg-neutral-50 p-3">
        <div className="mb-2 text-xs font-semibold text-neutral-600">BREAK追加</div>
        <div className="grid grid-cols-2 gap-2">
          <Field label="開始">
            <input
              className="w-full rounded border px-2 py-1"
              disabled={isReadOnly}
              onChange={(event) => setBreakStartTime(normalizeTimeInput(event.target.value))}
              type="time"
              value={timeInputValue(breakStartTime)}
            />
          </Field>
          <Field label="終了">
            <input
              className="w-full rounded border px-2 py-1"
              disabled={isReadOnly}
              onChange={(event) => setBreakEndTime(normalizeTimeInput(event.target.value))}
              type="time"
              value={timeInputValue(breakEndTime)}
            />
          </Field>
        </div>
        <button
          className="mt-2 inline-flex h-9 w-full items-center justify-center rounded border bg-white px-3 text-sm disabled:bg-neutral-100"
          disabled={isSaving}
          onClick={() => onInsertBreak(breakStartTime, breakEndTime)}
          type="button"
        >
          BREAKを追加
        </button>
      </div>
    </div>
  );
}

function ShiftSegmentEditor({
  draft,
  isReadOnly,
  isSaving,
  nextSegment,
  onChange,
  onMergeNext,
  onSave,
  onSplit,
  positions,
  segment,
  shift,
  taskTypes
}: {
  draft?: ShiftSegmentDraft;
  isReadOnly: boolean;
  isSaving: boolean;
  nextSegment?: ShiftSegment;
  onChange: (patch: ShiftSegmentDraft) => void;
  onMergeNext: () => void;
  onSave: () => void;
  onSplit: (splitTime: string) => void;
  positions: WorkspaceData["positions"];
  segment: ShiftSegment;
  shift?: WorkShift;
  taskTypes: WorkspaceData["task_types"];
}) {
  const merged = { ...segment, ...draft };
  const isDirty = hasDraftValue(draft);
  const [splitTime, setSplitTime] = useState(midpointTime(segment.start_time, segment.end_time));

  return (
    <div className="mt-2 space-y-3 rounded border p-3">
      <div className="text-sm font-medium">
        {shift?.work_date ?? segment.segment_date} / {merged.segment_type}
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs text-neutral-500">
        <div>開始 {segment.start_time.slice(0, 5)}</div>
        <div>終了 {segment.end_time.slice(0, 5)}</div>
      </div>
      <Field label="種別">
        <select
          className="w-full rounded border px-2 py-1"
          disabled={isReadOnly}
          onChange={(event) =>
            onChange({
              segment_type: event.target.value as ShiftSegment["segment_type"],
              position_id: event.target.value === "WORK" ? merged.position_id : null,
              task_type_id: event.target.value === "TASK" ? merged.task_type_id : null
            })
          }
          value={merged.segment_type}
        >
          <option value="WORK">WORK</option>
          <option value="TASK">TASK</option>
        </select>
      </Field>
      {merged.segment_type === "WORK" && (
        <Field label="ポジション">
          <select
            className="w-full rounded border px-2 py-1"
            disabled={isReadOnly}
            onChange={(event) => onChange({ position_id: event.target.value || null })}
            value={merged.position_id ?? ""}
          >
            <option value="">未選択</option>
            {positions.map((position) => (
              <option key={position.id} value={position.id}>
                {positionDisplayLabel(position.code, position.name)}
              </option>
            ))}
          </select>
        </Field>
      )}
      {merged.segment_type === "TASK" && (
        <Field label="TASK">
          <select
            className="w-full rounded border px-2 py-1"
            disabled={isReadOnly}
            onChange={(event) => onChange({ task_type_id: event.target.value || null })}
            value={merged.task_type_id ?? ""}
          >
            <option value="">未選択</option>
            {taskTypes.map((taskType) => (
              <option key={taskType.id} value={taskType.id}>
                {positionDisplayLabel(taskType.code, taskType.name)}
              </option>
            ))}
          </select>
        </Field>
      )}
      <label className="flex items-center gap-2 text-sm">
        <input
          checked={Boolean(merged.is_locked)}
          disabled={isReadOnly}
          onChange={(event) => onChange({ is_locked: event.target.checked })}
          type="checkbox"
        />
        セグメントをロック
      </label>
      <SaveButton disabled={!isDirty || isSaving} isSaving={isSaving} onClick={onSave} />
      <div className="grid grid-cols-2 gap-2">
        <Field label="分割時刻">
          <input
            className="w-full rounded border px-2 py-1"
            disabled={isReadOnly}
            onChange={(event) => setSplitTime(normalizeTimeInput(event.target.value))}
            type="time"
            value={timeInputValue(splitTime)}
          />
        </Field>
        <button
          className="mt-5 inline-flex h-9 items-center justify-center gap-2 rounded border px-3 text-sm disabled:bg-neutral-100"
          disabled={isSaving}
          onClick={() => onSplit(splitTime)}
          type="button"
        >
          <Scissors className="h-4 w-4" />
          分割
        </button>
      </div>
      <button
        className="inline-flex h-9 w-full items-center justify-center gap-2 rounded border px-3 text-sm disabled:bg-neutral-100"
        disabled={!nextSegment || isSaving}
        onClick={onMergeNext}
        type="button"
      >
        <GitMerge className="h-4 w-4" />
        次のセグメントと結合
      </button>
    </div>
  );
}

function Field({ children, label }: { children: ReactNode; label: string }) {
  return (
    <label className="block text-xs text-neutral-500">
      <span className="mb-1 block">{label}</span>
      {children}
    </label>
  );
}

function SaveButton({
  disabled,
  isSaving,
  onClick
}: {
  disabled: boolean;
  isSaving: boolean;
  onClick: () => void;
}) {
  return (
    <button
      className="inline-flex h-9 w-full items-center justify-center gap-2 rounded bg-neutral-950 px-3 text-sm text-white disabled:bg-neutral-300"
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      <Save className="h-4 w-4" />
      {isSaving ? "保存中" : "Draftへ追加"}
    </button>
  );
}

function findNextSegment(segments: ShiftSegment[], current: ShiftSegment) {
  return segments
    .filter((segment) => segment.work_shift_id === current.work_shift_id)
    .sort((a, b) => a.start_time.localeCompare(b.start_time))
    .find((segment) => segment.start_time === current.end_time);
}

function timeInputValue(value: string) {
  return value.slice(0, 5);
}

function normalizeTimeInput(value: string) {
  return value.length === 5 ? `${value}:00` : value;
}

function timeToMinutes(value: string) {
  const [hours, minutes] = value.slice(0, 5).split(":").map(Number);
  return hours * 60 + minutes;
}

function minutesToTime(value: number) {
  const hours = Math.floor(value / 60)
    .toString()
    .padStart(2, "0");
  const minutes = (value % 60).toString().padStart(2, "0");
  return `${hours}:${minutes}:00`;
}

function midpointTime(startTime: string, endTime: string) {
  return minutesToTime(Math.floor((timeToMinutes(startTime) + timeToMinutes(endTime)) / 2));
}

function defaultBreakStart(shift: WorkShift) {
  return minutesToTime(timeToMinutes(shift.start_time) + 180);
}

function defaultBreakEnd(shift: WorkShift) {
  return minutesToTime(timeToMinutes(shift.start_time) + 210);
}

function formatCommandError(error: unknown) {
  if (error instanceof ApiError) {
    if (typeof error.body === "object" && error.body && "detail" in error.body) {
      const detail = error.body.detail;
      if (typeof detail === "string") {
        return detail;
      }
      return JSON.stringify(detail);
    }
    return `Command failed (${error.status})`;
  }
  return error instanceof Error ? error.message : "Command failed";
}
