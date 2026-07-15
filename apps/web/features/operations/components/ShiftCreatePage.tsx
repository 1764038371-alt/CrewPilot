"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { applyProposal, generateProposal } from "@/features/schedule-editor/api/proposalApi";
import type { StaffMember, Uuid } from "@/features/schedule-editor/types";
import { positionDisplayLabel } from "@/features/schedule-editor/utils/positionLabels";
import { formatApiErrorDetail, isUnauthorizedApiError } from "@/lib/api/client";
import { getDailyDraft, getSetup, saveDailyDraft, type DailyDraftWrite } from "../api/operationsApi";

type ShiftCreatePageProps = {
  planningPeriodId: Uuid;
};

type RequestRow = {
  staff_member_id: Uuid;
  request_type: "available" | "off";
  start_time: string;
  end_time: string;
};

const hourOptions = buildHourOptions();
const minuteOptions = ["00", "15", "30", "45"];

export function ShiftCreatePage({ planningPeriodId }: ShiftCreatePageProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const setupQuery = useQuery({
    queryKey: ["operations", "setup"],
    queryFn: getSetup,
    refetchOnMount: "always",
    staleTime: 0
  });
  const planningPeriod = setupQuery.data?.planning_period;
  const [targetDate, setTargetDate] = useState("");
  const draftQuery = useQuery({
    queryKey: ["daily-draft", planningPeriodId, targetDate],
    queryFn: () => getDailyDraft(planningPeriodId, targetDate),
    enabled: Boolean(targetDate),
    refetchOnMount: "always",
    staleTime: 0
  });
  const [rows, setRows] = useState<RequestRow[]>([]);

  useEffect(() => {
    if (!planningPeriod) {
      return;
    }
    const savedDate = window.localStorage.getItem(lastDateStorageKey(planningPeriodId));
    setTargetDate(isDateInPlanningPeriod(savedDate, planningPeriod) ? savedDate : planningPeriod.start_date);
  }, [planningPeriod, planningPeriodId]);

  useEffect(() => {
    if (targetDate && planningPeriod && isDateInPlanningPeriod(targetDate, planningPeriod)) {
      window.localStorage.setItem(lastDateStorageKey(planningPeriodId), targetDate);
    }
  }, [planningPeriod, planningPeriodId, targetDate]);

  useEffect(() => {
    setRows([]);
  }, [targetDate]);

  useEffect(() => {
    if (!draftQuery.data) {
      return;
    }
    setRows(
      sortStaffByEmployeeNumber(draftQuery.data.staff_members).map((staff) => {
        const request = draftQuery.data.shift_requests.find((item) => item.staff_member_id === staff.id);
        return {
          staff_member_id: staff.id,
          request_type: request?.request_type === "off" ? "off" : "available",
          start_time: request?.start_time?.slice(0, 5) ?? "09:00",
          end_time: request?.end_time?.slice(0, 5) ?? "17:00"
        };
      })
    );
  }, [draftQuery.data]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const setup = setupQuery.data;
      if (!setup) {
        throw new Error("設定が読み込まれていません。");
      }
      return saveDailyDraft(planningPeriodId, buildPayload(targetDate, rows, setup.store.operational_settings));
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["daily-draft"] });
      void queryClient.invalidateQueries({ queryKey: ["workspace"] });
    }
  });
  const proposalMutation = useMutation({
    mutationFn: async () => {
      await saveMutation.mutateAsync();
      const proposal = await generateProposal(currentScheduleVersionId, { type: "date", date: targetDate });
      await applyProposal(proposal.id);
      return proposal;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["workspace"] });
      void queryClient.invalidateQueries({ queryKey: ["optimization-proposals"] });
      router.push(`/planning-periods/${planningPeriodId}/workspace?date=${targetDate}`);
    }
  });

  const currentScheduleVersionId = useCurrentScheduleVersionId(planningPeriodId);
  const draftIsLoading = draftQuery.isFetching || (!draftQuery.data && !draftQuery.isError);
  const disabled = saveMutation.isPending || proposalMutation.isPending || !currentScheduleVersionId || draftIsLoading;
  const setup = setupQuery.data;
  const loadError = setupQuery.error ?? draftQuery.error;
  const staffMembers = sortStaffByEmployeeNumber(draftQuery.data?.staff_members ?? []);
  const availableCount = rows.filter((row) => row.request_type === "available").length;
  const offCount = rows.filter((row) => row.request_type === "off").length;

  return (
    <main className="min-h-screen bg-neutral-100 text-neutral-950">
      <div className="mx-auto max-w-6xl px-6 py-6">
        <header className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold">シフト案作成</h1>
            <p className="mt-1 text-sm text-neutral-600">
              日付を選び、店長が希望シフトを入力してからAI提案を作成します。
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link className="inline-flex h-10 items-center rounded border bg-white px-4 text-sm" href="/">
              初期設定へ
            </Link>
            <Link
              className="inline-flex h-10 items-center rounded border bg-white px-4 text-sm"
              href={`/planning-periods/${planningPeriodId}/workspace`}
            >
              Workspace
            </Link>
          </div>
        </header>
        <section className="mt-6 rounded border bg-white p-4">
          <div className="grid gap-4 md:grid-cols-[220px_1fr]">
            <label className="block text-sm">
              <span className="text-neutral-500">作成日</span>
              <input
                className="mt-1 w-full rounded border px-3 py-2"
                max={planningPeriod?.end_date}
                min={planningPeriod?.start_date}
                onChange={(event) => setTargetDate(event.target.value)}
                type="date"
                value={targetDate}
              />
            </label>
            <div className="rounded bg-neutral-50 p-3 text-sm text-neutral-600">
              入金は原則10:00-10:30です。配置できない場合は前日の閉店30分前から閉店までを救済候補として警告します。
            </div>
          </div>
        </section>
        <section className="mt-4 rounded border bg-white p-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold">希望シフト入力</h2>
            <div className="flex items-center gap-2">
              <button
                className="h-9 rounded border px-3 text-sm disabled:bg-neutral-100 disabled:text-neutral-400"
                disabled={disabled}
                onClick={() => saveMutation.mutate()}
                type="button"
              >
                {draftIsLoading ? "読み込み中" : "希望を保存"}
              </button>
              <button
                className="h-9 rounded bg-neutral-950 px-3 text-sm text-white disabled:bg-neutral-300"
                disabled={disabled}
                onClick={() => proposalMutation.mutate()}
                type="button"
              >
                {proposalMutation.isPending ? "AI提案中" : "保存してAI提案"}
              </button>
            </div>
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-3">
            <RequestSummaryItem label="勤務希望" value={`${availableCount}人`} />
            <RequestSummaryItem label="休み希望" value={`${offCount}人`} />
            <RequestSummaryItem label="登録スタッフ" value={`${staffMembers.length}人`} />
          </div>
          <p className="mt-2 text-xs text-neutral-500">
            休み希望のスタッフはAIの割当対象外です。勤務希望だけ開始・終了時刻を選んでください。
          </p>
          {saveMutation.isSuccess && <p className="mt-2 text-sm text-emerald-700">希望シフトを保存しました。</p>}
          {(saveMutation.isError || proposalMutation.isError) && (
            <div className="mt-2 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              <div>{shiftCreateErrorMessage(saveMutation.error ?? proposalMutation.error)}</div>
              {isUnauthorizedApiError(saveMutation.error ?? proposalMutation.error) && (
                <Link className="mt-2 inline-flex font-medium underline" href="/login">
                  ログイン画面へ
                </Link>
              )}
            </div>
          )}
          {loadError && (
            <div className="mt-2 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              <div>{shiftCreateLoadErrorMessage(loadError)}</div>
              {isUnauthorizedApiError(loadError) && (
                <Link className="mt-2 inline-flex font-medium underline" href="/login">
                  ログイン画面へ
                </Link>
              )}
            </div>
          )}
          <div className="mt-4 max-h-[560px] overflow-auto rounded border">
            <table className="w-full min-w-[760px] border-collapse text-sm">
              <thead className="sticky top-0 z-10 bg-neutral-50 text-xs text-neutral-500 shadow-sm">
                <tr>
                  <th className="border p-2 text-left">従業員番号</th>
                  <th className="border p-2 text-left">名前</th>
                  <th className="border p-2">希望</th>
                  <th className="border p-2">開始</th>
                  <th className="border p-2">終了</th>
                  <th className="border p-2 text-left">AI判断材料</th>
                </tr>
              </thead>
              <tbody>
                {draftIsLoading && (
                  <tr>
                    <td className="border p-6 text-center text-neutral-500" colSpan={6}>
                      初期設定の従業員を読み込んでいます。
                    </td>
                  </tr>
                )}
                {!draftIsLoading && !loadError && staffMembers.length === 0 && (
                  <tr>
                    <td className="border p-6 text-center text-neutral-500" colSpan={6}>
                      初期設定で従業員を追加して保存すると、ここに希望入力欄が表示されます。
                    </td>
                  </tr>
                )}
                {rows.map((row, index) => {
                  const staff = draftQuery.data?.staff_members.find((item) => item.id === row.staff_member_id);
                  return (
                    <tr className={row.request_type === "off" ? "bg-neutral-50 text-neutral-400" : undefined} key={row.staff_member_id}>
                      <td className="border p-2 font-medium">{staffLabel(staff)}</td>
                      <td className="border p-2 text-neutral-500">{staffDisplayName(staff)}</td>
                      <td className="border p-2 text-center">
                        <select
                          className="rounded border px-2 py-1"
                          onChange={(event) => updateRow(rows, setRows, index, { request_type: event.target.value as RequestRow["request_type"] })}
                          value={row.request_type}
                        >
                          <option value="available">勤務希望</option>
                          <option value="off">休み希望</option>
                        </select>
                      </td>
                      <td className="border p-2 text-center">
                        <TimeSelect
                          disabled={row.request_type === "off"}
                          label={`${staffLabel(staff)} 開始時刻`}
                          onChange={(value) => updateRow(rows, setRows, index, { start_time: value })}
                          value={row.start_time}
                        />
                      </td>
                      <td className="border p-2 text-center">
                        <TimeSelect
                          disabled={row.request_type === "off"}
                          label={`${staffLabel(staff)} 終了時刻`}
                          onChange={(value) => updateRow(rows, setRows, index, { end_time: value })}
                          value={row.end_time}
                        />
                      </td>
                      <td className="border p-2 text-xs text-neutral-500">{staffCapabilitySummary(staff, setup)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </main>
  );
}

function shiftCreateErrorMessage(error: unknown) {
  if (isUnauthorizedApiError(error)) {
    return "ログイン状態が切れています。希望保存やAI提案を行うにはもう一度ログインしてください。";
  }

  const detail = formatApiErrorDetail(error);
  return detail ? `保存またはAI提案に失敗しました: ${detail}` : "保存またはAI提案に失敗しました。入力内容を確認してください。";
}

function RequestSummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border bg-neutral-50 px-3 py-2">
      <div className="text-xs text-neutral-500">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value}</div>
    </div>
  );
}

function shiftCreateLoadErrorMessage(error: unknown) {
  if (isUnauthorizedApiError(error)) {
    return "ログイン状態が切れています。従業員の希望入力欄を表示するにはもう一度ログインしてください。";
  }

  const detail = formatApiErrorDetail(error);
  return detail
    ? `初期設定の従業員を読み込めません: ${detail}`
    : "初期設定の従業員を読み込めません。APIの接続先を確認してから再読み込みしてください。";
}

function buildPayload(
  targetDate: string,
  rows: RequestRow[],
  settings: Record<string, unknown> | null
): DailyDraftWrite {
  const operationalSettings = settings as {
    required_staff_templates?: Array<Record<string, unknown>>;
    weekday_required_staff_templates?: Array<Record<string, unknown>>;
    holiday_required_staff_templates?: Array<Record<string, unknown>>;
  } | null;
  const requiredStaffTemplates = templatesForDate(targetDate, operationalSettings);
  return {
    target_date: targetDate,
    required_staff_templates: requiredStaffTemplates,
    requests: rows.map((row) => ({
      staff_member_id: row.staff_member_id,
      request_type: row.request_type,
      start_time: row.request_type === "off" ? null : row.start_time,
      end_time: row.request_type === "off" ? null : row.end_time,
      note: null
    }))
  };
}

function templatesForDate(
  targetDate: string,
  settings: {
    required_staff_templates?: Array<Record<string, unknown>>;
    weekday_required_staff_templates?: Array<Record<string, unknown>>;
    holiday_required_staff_templates?: Array<Record<string, unknown>>;
  } | null
) {
  if (!settings) {
    return [];
  }
  const templates = isHolidayDate(targetDate)
    ? settings.holiday_required_staff_templates
    : settings.weekday_required_staff_templates;
  return templates ?? settings.required_staff_templates ?? [];
}

function isHolidayDate(targetDate: string) {
  const day = new Date(`${targetDate}T00:00:00`).getDay();
  return day === 0 || day === 6;
}

function updateRow(
  rows: RequestRow[],
  setRows: (rows: RequestRow[]) => void,
  index: number,
  patch: Partial<RequestRow>
) {
  const next = [...rows];
  next[index] = { ...next[index], ...patch };
  setRows(next);
}

function staffLabel(staff?: StaffMember) {
  return staff?.employee_number ?? staff?.display_name ?? "-";
}

function sortStaffByEmployeeNumber<T extends { employee_number: string | null; display_name: string; id: string }>(
  staffMembers: T[]
) {
  return [...staffMembers].sort((first, second) => compareEmployeeNumber(first, second));
}

function compareEmployeeNumber(
  first: { employee_number: string | null; display_name: string; id: string },
  second: { employee_number: string | null; display_name: string; id: string }
) {
  const firstNumber = Number.parseInt(first.employee_number ?? "", 10);
  const secondNumber = Number.parseInt(second.employee_number ?? "", 10);
  if (Number.isFinite(firstNumber) && Number.isFinite(secondNumber) && firstNumber !== secondNumber) {
    return firstNumber - secondNumber;
  }
  return (first.employee_number ?? first.display_name ?? first.id).localeCompare(
    second.employee_number ?? second.display_name ?? second.id,
    "ja",
    { numeric: true }
  );
}

function staffDisplayName(staff?: StaffMember) {
  if (!staff || isGeneratedStaffName(staff.display_name)) {
    return "";
  }
  return staff.display_name;
}

function isGeneratedStaffName(value: string) {
  return /^新規スタッフ\d+$/.test(value.trim());
}

function staffCapabilitySummary(staff: StaffMember | undefined, setup: Awaited<ReturnType<typeof getSetup>> | undefined) {
  if (!staff || !setup) {
    return "-";
  }
  const skillIds = new Set(setup.staff_skills.filter((item) => item.staff_member_id === staff.id).map((item) => item.skill_definition_id));
  const codes = setup.skill_definitions.filter((skill) => skillIds.has(skill.id)).map((skill) => skill.code);
  return codes.length ? codes.map((code) => positionDisplayLabel(code)).join(" / ") : "スキル未設定";
}

function TimeSelect({
  disabled = false,
  label,
  onChange,
  value
}: {
  disabled?: boolean;
  label: string;
  onChange: (value: string) => void;
  value: string;
}) {
  const [open, setOpen] = useState(false);
  const normalizedValue = normalizeTimeValue(value);
  const [pendingValue, setPendingValue] = useState(normalizedValue);
  const [selectedHour, selectedMinute] = pendingValue.split(":");
  const containerRef = useRef<HTMLDivElement>(null);

  const commitPendingValue = () => {
    onChange(pendingValue);
    setOpen(false);
  };

  useEffect(() => {
    if (!open) {
      return;
    }
    const closeOnOutsidePointer = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        onChange(pendingValue);
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", closeOnOutsidePointer, true);
    return () => document.removeEventListener("pointerdown", closeOnOutsidePointer, true);
  }, [onChange, open, pendingValue]);

  return (
    <div
      className="relative inline-block w-24 text-left"
      ref={containerRef}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
          if (open) {
            commitPendingValue();
          }
        }
      }}
      onKeyDown={(event) => {
        if (open && event.key === "Enter") {
          event.preventDefault();
          commitPendingValue();
        } else if (open && event.key === "Escape") {
          event.preventDefault();
          setPendingValue(normalizedValue);
          setOpen(false);
        }
      }}
    >
      <button
        aria-expanded={open}
        aria-label={label}
        className="flex h-9 w-full items-center justify-between rounded border bg-white px-2 text-sm font-medium shadow-sm disabled:bg-neutral-100 disabled:text-neutral-400"
        disabled={disabled}
        onClick={() => {
          if (open) {
            commitPendingValue();
          } else {
            setPendingValue(normalizedValue);
            setOpen(true);
          }
        }}
        type="button"
      >
        <span>{normalizedValue}</span>
        <span className="text-xs text-neutral-400">▼</span>
      </button>
      {open && !disabled && (
        <div
          className="absolute left-0 z-30 mt-1 grid w-32 grid-cols-[1fr_52px] overflow-hidden rounded border bg-white shadow-lg"
          role="listbox"
        >
          <div className="max-h-56 overflow-y-auto border-r py-1">
            {hourOptions.map((hour) => (
              <button
                aria-selected={hour === selectedHour}
                className={`block w-full px-3 py-1.5 text-left text-sm hover:bg-neutral-100 ${
                  hour === selectedHour ? "bg-neutral-950 text-white hover:bg-neutral-950" : ""
                }`}
                key={hour}
                onClick={() => {
                  setPendingValue(`${hour}:${selectedMinute}`);
                }}
                onMouseDown={(event) => event.preventDefault()}
                role="option"
                type="button"
              >
                {hour}時
              </button>
            ))}
          </div>
          <div className="max-h-56 overflow-y-auto py-1">
            {minuteOptions.map((minute) => (
              <button
                aria-selected={minute === selectedMinute}
                className={`block w-full px-2 py-1.5 text-center text-sm hover:bg-neutral-100 ${
                  minute === selectedMinute ? "bg-neutral-950 text-white hover:bg-neutral-950" : ""
                }`}
                key={minute}
                onClick={() => {
                  setPendingValue(`${selectedHour}:${minute}`);
                }}
                onMouseDown={(event) => event.preventDefault()}
                role="option"
                type="button"
              >
                {minute}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function buildHourOptions() {
  return Array.from({ length: 24 }, (_, hour) => String(hour).padStart(2, "0"));
}

function lastDateStorageKey(planningPeriodId: Uuid) {
  return `crewpilot:last-shift-date:${planningPeriodId}`;
}

function isDateInPlanningPeriod(
  date: string | null,
  planningPeriod: { start_date: string; end_date: string }
): date is string {
  return Boolean(date && date >= planningPeriod.start_date && date <= planningPeriod.end_date);
}

function normalizeTimeValue(value: string) {
  const normalized = value.slice(0, 5);
  const [hour, minute] = normalized.split(":");
  if (hourOptions.includes(hour) && minuteOptions.includes(minute)) {
    return `${hour}:${minute}`;
  }
  return "09:00";
}

function useCurrentScheduleVersionId(planningPeriodId: Uuid) {
  const query = useQuery({
    queryKey: ["workspace", planningPeriodId, "for-ai"],
    queryFn: async () => {
      const { getWorkspace } = await import("@/features/schedule-editor/api/workspaceApi");
      return getWorkspace(planningPeriodId);
    }
  });
  return query.data?.current_schedule_version?.id ?? "";
}
