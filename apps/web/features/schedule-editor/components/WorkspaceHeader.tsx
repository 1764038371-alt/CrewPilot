import Link from "next/link";
import { Archive, CalendarDays, CheckCircle2, ClipboardList, Copy, LogOut, Redo2, Save, Send, Settings, Undo2 } from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";
import type { CurrentUser } from "@/features/auth/api/authApi";
import type { DraftSaveStatus } from "../store/editingStore";
import type { WorkspaceData } from "../types";

type WorkspaceHeaderProps = {
  planningPeriodId: string;
  workspace?: WorkspaceData;
  canSave?: boolean;
  draftError?: string | null;
  draftStatus?: DraftSaveStatus;
  unsavedCount?: number;
  undoPending?: boolean;
  redoPending?: boolean;
  actionPending?: boolean;
  isReadOnly?: boolean;
  currentUser?: CurrentUser;
  selectedDate?: string;
  onSave?: () => void;
  onSelectedDateChange?: (date: string) => void;
  onUndo?: () => void;
  onRedo?: () => void;
  onApprove?: () => void;
  onArchive?: () => void;
  onDuplicate?: () => void;
  onLogout?: () => void;
  onPublish?: () => void;
};

export function WorkspaceHeader({
  planningPeriodId,
  workspace,
  canSave = false,
  draftError,
  draftStatus = "saved",
  unsavedCount = 0,
  undoPending = false,
  redoPending = false,
  actionPending = false,
  isReadOnly = false,
  currentUser,
  selectedDate,
  onSave,
  onSelectedDateChange,
  onUndo,
  onRedo,
  onApprove,
  onArchive,
  onDuplicate,
  onLogout,
  onPublish
}: WorkspaceHeaderProps) {
  const scheduleVersion = workspace?.current_schedule_version;
  const status = scheduleVersion?.status ?? "loading";
  const isPublished = status === "published";
  const [isDatePickerOpen, setIsDatePickerOpen] = useState(false);
  const planningPeriod = workspace?.planning_period;

  return (
    <header className="relative flex min-h-20 shrink-0 flex-wrap items-center justify-between gap-3 border-b bg-white px-4 py-3">
      <div className="min-w-48">
        <div className="text-xs text-neutral-500">{workspace?.store.name ?? "CrewPilot"}</div>
        <h1 className="text-lg font-semibold">
          {workspace?.planning_period.name ?? "シフトWorkspace"}
        </h1>
        <div className="mt-1 flex items-center gap-3">
          <Link
            className="inline-flex items-center gap-1 text-xs text-neutral-500 hover:text-neutral-950"
            href="/"
          >
            <Settings className="h-3.5 w-3.5" />
            初期設定
          </Link>
          <Link
            className="inline-flex items-center gap-1 text-xs text-neutral-500 hover:text-neutral-950"
            href={`/planning-periods/${planningPeriodId}/create`}
          >
            <ClipboardList className="h-3.5 w-3.5" />
            希望入力
          </Link>
        </div>
      </div>
      <DateNavigator
        endDate={planningPeriod?.end_date}
        isPickerOpen={isDatePickerOpen}
        onDateChange={onSelectedDateChange}
        onPickerOpenChange={setIsDatePickerOpen}
        selectedDate={selectedDate}
        startDate={planningPeriod?.start_date}
      />
      <div className="flex min-w-[360px] flex-1 flex-col items-end gap-2">
        <div className="flex flex-wrap items-center justify-end gap-2">
          <span className={publishStatusClassName(status)}>
            {publishStatusLabel(status)}
          </span>
          <span
            className={draftStatusClassName(draftStatus)}
            title={draftError ?? undefined}
          >
            {draftStatusLabel(draftStatus, unsavedCount)}
          </span>
          {currentUser && (
            <button
              aria-label="ログアウト"
              className="inline-flex h-9 items-center gap-2 rounded border border-neutral-300 bg-white px-3 text-sm text-neutral-700 hover:bg-neutral-50"
              onClick={onLogout}
              title={`${currentUser.display_name}としてログイン中・ログアウト`}
              type="button"
            >
              <LogOut className="h-4 w-4" />
              ログアウト
            </button>
          )}
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <button
            className="inline-flex h-9 items-center gap-2 rounded border px-3 text-sm disabled:bg-neutral-100 disabled:text-neutral-400"
            disabled={!onUndo || undoPending}
            onClick={onUndo}
            title="Undo (⌘Z / Ctrl+Z)"
            type="button"
          >
            <Undo2 className="h-4 w-4" />
            戻す
          </button>
          <button
            className="inline-flex h-9 items-center gap-2 rounded border px-3 text-sm disabled:bg-neutral-100 disabled:text-neutral-400"
            disabled={!onRedo || redoPending}
            onClick={onRedo}
            title="Redo (⌘⇧Z / Ctrl+Shift+Z)"
            type="button"
          >
            <Redo2 className="h-4 w-4" />
            やり直し
          </button>
          <button
            className="inline-flex h-9 items-center gap-2 rounded border px-3 text-sm disabled:bg-neutral-100 disabled:text-neutral-400"
            disabled={!canSave}
            onClick={onSave}
            title="保存 (⌘S / Ctrl+S)"
            type="button"
          >
            <Save className="h-4 w-4" />
            {draftStatus === "saving" ? "保存中" : "保存"}
          </button>
          {status === "draft" && (
            <button
              className="inline-flex h-9 items-center gap-2 rounded border px-3 text-sm disabled:bg-neutral-100 disabled:text-neutral-400"
              disabled={!onApprove || actionPending || unsavedCount > 0 || isReadOnly}
              onClick={onApprove}
              title="確定"
              type="button"
            >
              <CheckCircle2 className="h-4 w-4" />
              確定
            </button>
          )}
          {(status === "draft" || status === "approved") && (
            <button
              className="inline-flex h-9 items-center gap-2 rounded border px-3 text-sm disabled:bg-neutral-100 disabled:text-neutral-400"
              disabled={!onPublish || actionPending || unsavedCount > 0 || isReadOnly}
              onClick={onPublish}
              title="公開"
              type="button"
            >
              <Send className="h-4 w-4" />
              公開
            </button>
          )}
          {(isPublished || status === "archived") && (
            <button
              className="inline-flex h-9 items-center gap-2 rounded border px-3 text-sm disabled:bg-neutral-100 disabled:text-neutral-400"
              disabled={!onDuplicate || actionPending || currentUser?.role === "viewer"}
              onClick={onDuplicate}
              title="複製して編集再開"
              type="button"
            >
              <Copy className="h-4 w-4" />
              複製して編集
            </button>
          )}
          {status !== "archived" && (
            <button
              className="inline-flex h-9 items-center gap-2 rounded border px-3 text-sm disabled:bg-neutral-100 disabled:text-neutral-400"
              disabled={!onArchive || actionPending || currentUser?.role === "viewer"}
              onClick={onArchive}
              title="Archive"
              type="button"
            >
              <Archive className="h-4 w-4" />
              保管
            </button>
          )}
        </div>
      </div>
      {isPublished && scheduleVersion?.published_at && (
        <span className="absolute bottom-1 right-4 text-[10px] text-neutral-400">
          {formatDateTime(scheduleVersion.published_at)} 公開
        </span>
      )}
    </header>
  );
}

function DateNavigator({
  endDate,
  isPickerOpen,
  onDateChange,
  onPickerOpenChange,
  selectedDate,
  startDate
}: {
  endDate?: string;
  isPickerOpen: boolean;
  onDateChange?: (date: string) => void;
  onPickerOpenChange: (isOpen: boolean) => void;
  selectedDate?: string;
  startDate?: string;
}) {
  const today = currentLocalDate();
  const canNavigate = Boolean(selectedDate && startDate && endDate && onDateChange);
  const go = (offsetDays: number) => {
    if (!selectedDate || !onDateChange) {
      return;
    }
    const nextDate = addDays(selectedDate, offsetDays);
    if (startDate && endDate && isWithinRange(nextDate, startDate, endDate)) {
      onDateChange(nextDate);
    }
  };
  const canGo = (offsetDays: number) => {
    if (!selectedDate || !startDate || !endDate) {
      return false;
    }
    return isWithinRange(addDays(selectedDate, offsetDays), startDate, endDate);
  };
  const canGoToday = Boolean(startDate && endDate && isWithinRange(today, startDate, endDate) && selectedDate !== today);

  return (
    <div className="relative flex shrink-0 items-center gap-1 rounded border bg-neutral-50 p-1">
      <DateNavButton disabled={!canNavigate || !canGo(-7)} onClick={() => go(-7)}>
        &lt;&lt; 一週前
      </DateNavButton>
      <DateNavButton disabled={!canNavigate || !canGo(-1)} onClick={() => go(-1)}>
        &lt; 前日
      </DateNavButton>
      <button
        className="inline-flex h-9 min-w-40 items-center justify-center gap-2 rounded bg-white px-3 text-sm font-semibold shadow-sm disabled:text-neutral-400"
        disabled={!canNavigate}
        onClick={() => onPickerOpenChange(!isPickerOpen)}
        type="button"
      >
        <CalendarDays className="h-4 w-4 text-neutral-500" />
        {selectedDate ? formatDateWithWeekday(selectedDate) : "日付選択"}
      </button>
      <DateNavButton disabled={!canNavigate || !canGo(1)} onClick={() => go(1)}>
        翌日 &gt;
      </DateNavButton>
      <DateNavButton disabled={!canNavigate || !canGo(7)} onClick={() => go(7)}>
        一週後 &gt;&gt;
      </DateNavButton>
      <DateNavButton disabled={!canNavigate || !canGoToday} onClick={() => onDateChange?.(today)}>
        今日
      </DateNavButton>
      {isPickerOpen && selectedDate && startDate && endDate && (
        <div
          className="absolute left-1/2 top-12 z-40 w-64 -translate-x-1/2 rounded border bg-white p-3 text-sm shadow-lg"
          onBlur={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget)) {
              onPickerOpenChange(false);
            }
          }}
        >
          <label className="text-xs font-medium text-neutral-600" htmlFor="workspace-date-picker">
            日付を選択
          </label>
          <input
            autoFocus
            className="mt-2 h-10 w-full rounded border px-3 text-sm"
            id="workspace-date-picker"
            max={endDate}
            min={startDate}
            onChange={(event) => {
              const nextDate = event.target.value;
              if (isWithinRange(nextDate, startDate, endDate)) {
                onDateChange?.(nextDate);
                onPickerOpenChange(false);
              }
            }}
            type="date"
            value={selectedDate}
          />
          <p className="mt-2 text-xs text-neutral-500">
            移動可能期間: {formatDateWithWeekday(startDate)} - {formatDateWithWeekday(endDate)}
          </p>
        </div>
      )}
    </div>
  );
}

function DateNavButton({
  children,
  disabled,
  onClick
}: {
  children: ReactNode;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      className="inline-flex h-9 items-center rounded px-2 text-xs font-medium text-neutral-700 hover:bg-white disabled:cursor-not-allowed disabled:text-neutral-300 disabled:hover:bg-transparent"
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      {children}
    </button>
  );
}

function publishStatusLabel(status: string) {
  if (status === "draft") {
    return "Draft";
  }
  if (status === "approved") {
    return "Approved";
  }
  if (status === "published") {
    return "Published";
  }
  if (status === "archived") {
    return "Archived";
  }
  return status;
}

function publishStatusClassName(status: string) {
  const base = "rounded border px-2 py-1 text-xs";
  if (status === "published") {
    return `${base} border-emerald-200 bg-emerald-50 text-emerald-700`;
  }
  if (status === "approved") {
    return `${base} border-sky-200 bg-sky-50 text-sky-700`;
  }
  if (status === "archived") {
    return `${base} border-neutral-300 bg-neutral-100 text-neutral-700`;
  }
  return `${base} border-amber-200 bg-amber-50 text-amber-800`;
}

function draftStatusLabel(status: DraftSaveStatus, unsavedCount: number) {
  if (status === "saving") {
    return "Saving...";
  }
  if (status === "failed") {
    return "Save Failed";
  }
  if (unsavedCount > 0) {
    return `Unsaved Changes (${unsavedCount})`;
  }
  return "Saved";
}

function draftStatusClassName(status: DraftSaveStatus) {
  const base = "rounded border px-2 py-1 text-xs";
  if (status === "saving") {
    return `${base} border-sky-200 bg-sky-50 text-sky-800`;
  }
  if (status === "failed") {
    return `${base} border-red-200 bg-red-50 text-red-700`;
  }
  if (status === "unsaved") {
    return `${base} border-amber-200 bg-amber-50 text-amber-800`;
  }
  return `${base} border-emerald-200 bg-emerald-50 text-emerald-700`;
}

function formatDateWithWeekday(value: string) {
  const date = new Date(`${value}T00:00:00`);
  const weekdays = ["日", "月", "火", "水", "木", "金", "土"];
  return `${value.replaceAll("-", "/")}（${weekdays[date.getDay()]}）`;
}

function addDays(value: string, days: number) {
  const date = new Date(`${value}T00:00:00`);
  date.setDate(date.getDate() + days);
  return toDateString(date);
}

function currentLocalDate() {
  return toDateString(new Date());
}

function toDateString(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function isWithinRange(value: string, start: string, end: string) {
  return value >= start && value <= end;
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("ja-JP", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}
