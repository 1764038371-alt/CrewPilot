"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, PanelRightClose } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api/client";
import { getCurrentUser, logout } from "@/features/auth/api/authApi";
import { executeScheduleCommand } from "../api/scheduleCommandApi";
import {
  approveScheduleVersion,
  archiveScheduleVersion,
  duplicateScheduleVersion,
  publishScheduleVersion,
  validatePublish,
  type PublishValidationIssue
} from "../api/scheduleVersionApi";
import { useWorkspaceShortcuts } from "../hooks/useWorkspaceShortcuts";
import { useWorkspaceQuery } from "../hooks/useWorkspaceQuery";
import { getUnsavedDraftCount, useEditingStore } from "../store/editingStore";
import { buildDraftCommands } from "../utils/draftCommands";
import { LeftSidebar } from "./LeftSidebar";
import { QuickEditBar } from "./QuickEditBar";
import { RightPanel, type PanelTab } from "./RightPanel";
import { ShiftGrid } from "./ShiftGrid";
import { StatusBar } from "./StatusBar";
import { WorkspaceHeader } from "./WorkspaceHeader";
import type { WorkspaceData } from "../types";

type WorkspaceLayoutProps = {
  planningPeriodId: string;
  initialWorkspace?: WorkspaceData;
};

export function WorkspaceLayout({ planningPeriodId, initialWorkspace }: WorkspaceLayoutProps) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const searchParams = useSearchParams();
  const authQuery = useQuery({
    queryKey: ["auth", "me"],
    queryFn: getCurrentUser,
    retry: false
  });
  const workspaceQuery = useWorkspaceQuery(planningPeriodId, initialWorkspace);
  const workspace = workspaceQuery.data;
  const workShiftDrafts = useEditingStore((state) => state.workShiftDrafts);
  const shiftSegmentDrafts = useEditingStore((state) => state.shiftSegmentDrafts);
  const pendingCommands = useEditingStore((state) => state.pendingCommands);
  const saveStatus = useEditingStore((state) => state.saveStatus);
  const saveError = useEditingStore((state) => state.saveError);
  const clearDrafts = useEditingStore((state) => state.clearDrafts);
  const setSaveStatus = useEditingStore((state) => state.setSaveStatus);
  const unsavedCount = useEditingStore(getUnsavedDraftCount);
  const scheduleVersionId = workspace?.current_schedule_version?.id;
  const scheduleRevision = workspace?.current_schedule_version?.revision ?? 0;
  const scheduleStatus = workspace?.current_schedule_version?.status;
  const isAuthReady = Boolean(authQuery.data);
  const isViewer = authQuery.data?.role === "viewer";
  const isReadOnly =
    scheduleStatus === "published" || scheduleStatus === "archived" || !isAuthReady || isViewer;
  const [publishIssues, setPublishIssues] = useState<PublishValidationIssue[]>([]);
  const [rightPanelTab, setRightPanelTab] = useState<PanelTab>("details");
  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!scheduleVersionId) {
        throw new Error("ScheduleVersionがありません。");
      }
      const commands = buildDraftCommands({
        pendingCommands,
        shiftSegmentDrafts,
        workspace,
        workShiftDrafts
      });
      if (commands.length === 0) {
        return;
      }
      const batchId = crypto.randomUUID();
      setSaveStatus("saving");
      for (const command of commands) {
        await executeScheduleCommand(scheduleVersionId, command, {
          batchId,
          batchLabel: `Draft Save (${commands.length} commands)`
        });
      }
    },
    onSuccess: () => {
      clearDrafts();
      void queryClient.invalidateQueries({ queryKey: ["workspace"] });
      void queryClient.invalidateQueries({ queryKey: ["schedule-change-logs"] });
      void queryClient.invalidateQueries({ queryKey: ["optimization-proposals"] });
    },
    onError: (error) => {
      setSaveStatus("failed", error instanceof Error ? error.message : "保存に失敗しました。");
    }
  });
  const runSave = () => {
    if (unsavedCount === 0 || saveMutation.isPending || isReadOnly) {
      return;
    }
    saveMutation.mutate();
  };
  const invalidateWorkspace = () => {
    void queryClient.invalidateQueries({ queryKey: ["workspace"] });
    void queryClient.invalidateQueries({ queryKey: ["schedule-change-logs"] });
    void queryClient.invalidateQueries({ queryKey: ["optimization-proposals"] });
  };
  const approveMutation = useMutation({
    mutationFn: () => approveScheduleVersion(scheduleVersionId ?? ""),
    onSuccess: () => {
      setPublishIssues([]);
      invalidateWorkspace();
    },
    onError: (error) => setPublishIssues(apiErrorIssues(error))
  });
  const publishMutation = useMutation({
    mutationFn: async () => {
      if (!scheduleVersionId) {
        throw new Error("ScheduleVersionがありません。");
      }
      if (unsavedCount > 0) {
        setPublishIssues([
          {
            code: "UNSAVED_DRAFT",
            message: "未保存Draftがあります。保存してからPublishしてください。",
            severity: "error"
          }
        ]);
        return null;
      }
      const validation = await validatePublish(scheduleVersionId, scheduleRevision);
      if (!validation.can_publish) {
        setPublishIssues(validation.issues);
        return null;
      }
      if (!window.confirm("公開後は編集できません。公開しますか？")) {
        return null;
      }
      return publishScheduleVersion(scheduleVersionId, scheduleRevision);
    },
    onSuccess: (result) => {
      if (!result) {
        return;
      }
      setPublishIssues(result.validation?.issues ?? []);
      invalidateWorkspace();
    },
    onError: (error) => setPublishIssues(apiErrorIssues(error))
  });
  const archiveMutation = useMutation({
    mutationFn: () => archiveScheduleVersion(scheduleVersionId ?? ""),
    onSuccess: () => {
      clearDrafts();
      setPublishIssues([]);
      invalidateWorkspace();
    },
    onError: (error) => setPublishIssues(apiErrorIssues(error))
  });
  const duplicateMutation = useMutation({
    mutationFn: () => duplicateScheduleVersion(scheduleVersionId ?? ""),
    onSuccess: () => {
      clearDrafts();
      setPublishIssues([]);
      invalidateWorkspace();
    },
    onError: (error) => setPublishIssues(apiErrorIssues(error))
  });
  const actionPending =
    approveMutation.isPending ||
    publishMutation.isPending ||
    archiveMutation.isPending ||
    duplicateMutation.isPending;
  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
      window.location.href = "/login";
    }
  });
  const shortcuts = useWorkspaceShortcuts({
    disabled: isReadOnly,
    onSave: runSave,
    workspace
  });
  const canUndoRedo = Boolean(workspace?.current_schedule_version?.id);
  const selectedDate = resolveSelectedDate(searchParams.get("date"), workspace);
  const changeSelectedDate = (date: string) => {
    if (!workspace || !isDateWithinPeriod(date, workspace)) {
      return;
    }
    const params = new URLSearchParams(searchParams.toString());
    params.set("date", date);
    router.push(`/planning-periods/${planningPeriodId}/workspace?${params.toString()}`, { scroll: false });
  };

  useEffect(() => {
    if (!workspace || !selectedDate || searchParams.get("date") === selectedDate) {
      return;
    }
    const params = new URLSearchParams(searchParams.toString());
    params.set("date", selectedDate);
    router.replace(`/planning-periods/${planningPeriodId}/workspace?${params.toString()}`, { scroll: false });
  }, [planningPeriodId, router, searchParams, selectedDate, workspace]);

  useUnsavedChangesGuard(unsavedCount > 0);

  return (
    <main className="flex h-screen min-h-[720px] flex-col overflow-hidden bg-neutral-100 text-neutral-950">
      <WorkspaceHeader
        isFetching={workspaceQuery.isFetching}
        canSave={unsavedCount > 0 && !saveMutation.isPending && !isReadOnly}
        actionPending={actionPending}
        currentUser={authQuery.data}
        draftError={saveError}
        draftStatus={saveMutation.isPending ? "saving" : saveStatus}
        isReadOnly={isReadOnly}
        onApprove={() => approveMutation.mutate()}
        onArchive={() => {
          if (window.confirm("このScheduleVersionをArchiveしますか？")) {
            archiveMutation.mutate();
          }
        }}
        onAiClick={() => setRightPanelTab("proposals")}
        onDuplicate={() => duplicateMutation.mutate()}
        onLogout={() => logoutMutation.mutate()}
        onPublish={() => publishMutation.mutate()}
        onRedo={canUndoRedo ? shortcuts.runRedo : undefined}
        onSave={runSave}
        onSelectedDateChange={changeSelectedDate}
        onUndo={canUndoRedo ? shortcuts.runUndo : undefined}
        planningPeriodId={planningPeriodId}
        redoPending={shortcuts.redoPending}
        selectedDate={selectedDate}
        unsavedCount={unsavedCount}
        undoPending={shortcuts.undoPending}
        workspace={workspace}
      />
      {workspaceQuery.isError ? (
        <section className="m-4 flex flex-1 items-center justify-center rounded border border-red-200 bg-red-50 p-6 text-red-900">
          <div className="max-w-xl">
            <div className="flex items-center gap-2 text-base font-semibold">
              <AlertCircle className="h-5 w-5" />
              Workspace APIに接続できません
            </div>
            <p className="mt-2 text-sm">
              FastAPIが起動しているか、`NEXT_PUBLIC_API_BASE_URL` が正しいか確認してください。
            </p>
          </div>
        </section>
      ) : authQuery.isError ? (
        <section className="m-4 flex flex-1 items-center justify-center rounded border border-amber-200 bg-amber-50 p-6 text-amber-900">
          <div className="max-w-xl">
            <div className="text-base font-semibold">ログインが必要です</div>
            <a className="mt-3 inline-flex rounded bg-neutral-950 px-4 py-2 text-sm text-white" href="/login">
              ログインへ
            </a>
          </div>
        </section>
      ) : (
        <section className="grid min-h-0 flex-1 grid-cols-[240px_minmax(0,1fr)_320px] gap-px bg-neutral-200">
          <LeftSidebar workspace={workspace} />
          <div className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)] bg-white">
            <QuickEditBar isReadOnly={isReadOnly} workspace={workspace} />
            <ShiftGrid
              isLoading={workspaceQuery.isLoading}
              isReadOnly={isReadOnly}
              selectedDate={selectedDate}
              workspace={workspace}
            />
          </div>
          <RightPanel
            activeTab={rightPanelTab}
            isReadOnly={isReadOnly}
            onActiveTabChange={setRightPanelTab}
            selectedDate={selectedDate}
            workspace={workspace}
          />
        </section>
      )}
      {publishIssues.length > 0 && <PublishIssues issues={publishIssues} />}
      <StatusBar
        isError={workspaceQuery.isError}
        isFetching={workspaceQuery.isFetching}
        selectedDate={selectedDate}
        unsavedCount={unsavedCount}
        workspace={workspace}
      />
      <button
        aria-label="Right panel placeholder"
        className="fixed bottom-4 right-4 hidden h-9 w-9 items-center justify-center rounded border bg-white text-neutral-600 shadow-sm"
        type="button"
      >
        <PanelRightClose className="h-4 w-4" />
      </button>
    </main>
  );
}

function resolveSelectedDate(dateParam: string | null, workspace?: WorkspaceData) {
  if (!workspace) {
    return dateParam ?? undefined;
  }
  if (dateParam && isDateWithinPeriod(dateParam, workspace)) {
    return dateParam;
  }
  return workspace.planning_period.start_date;
}

function isDateWithinPeriod(date: string, workspace: WorkspaceData) {
  return date >= workspace.planning_period.start_date && date <= workspace.planning_period.end_date;
}

function PublishIssues({ issues }: { issues: PublishValidationIssue[] }) {
  return (
    <div className="fixed right-4 top-20 z-20 w-96 rounded border border-red-200 bg-white p-3 text-sm shadow-lg">
      <div className="font-semibold text-red-700">Publishできません</div>
      <ul className="mt-2 space-y-1">
        {issues.map((issue) => (
          <li className="rounded bg-red-50 px-2 py-1 text-red-800" key={`${issue.code}:${issue.message}`}>
            <span className="font-medium">{issue.code}</span>: {issue.message}
          </li>
        ))}
      </ul>
    </div>
  );
}

function apiErrorIssues(error: unknown): PublishValidationIssue[] {
  if (error instanceof ApiError) {
    const detail =
      typeof error.body === "object" && error.body && "detail" in error.body
        ? (error.body as { detail?: unknown }).detail
        : null;
    if (
      typeof detail === "object" &&
      detail &&
      "issues" in detail &&
      Array.isArray((detail as { issues?: unknown }).issues)
    ) {
      return (detail as { issues: PublishValidationIssue[] }).issues;
    }
    return [
      {
        code: `HTTP_${error.status}`,
        message: typeof detail === "string" ? detail : error.message,
        severity: "error"
      }
    ];
  }
  return [
    {
      code: "UNKNOWN",
      message: error instanceof Error ? error.message : "操作に失敗しました。",
      severity: "error"
    }
  ];
}

function useUnsavedChangesGuard(hasUnsavedChanges: boolean) {
  useEffect(() => {
    if (!hasUnsavedChanges) {
      return;
    }
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    const handleDocumentClick = (event: MouseEvent) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) {
        return;
      }
      const link = target.closest("a[href]");
      if (!(link instanceof HTMLAnchorElement)) {
        return;
      }
      const href = link.getAttribute("href");
      if (!href || href.startsWith("#") || link.target === "_blank") {
        return;
      }
      if (!window.confirm("未保存の編集があります。保存せずに移動しますか？")) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    window.onbeforeunload = handleBeforeUnload;
    document.addEventListener("click", handleDocumentClick, true);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
      window.onbeforeunload = null;
      document.removeEventListener("click", handleDocumentClick, true);
    };
  }, [hasUnsavedChanges]);
}
