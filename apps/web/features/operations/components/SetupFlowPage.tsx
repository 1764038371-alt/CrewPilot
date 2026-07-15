"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { getSetup, saveSetup, type SetupWrite, type StaffSetupWrite } from "../api/operationsApi";
import type { SetupData, StaffSkillRead } from "../api/operationsApi";
import type { Position, SkillDefinition, StaffMember } from "@/features/schedule-editor/types";
import { formatApiErrorDetail, isUnauthorizedApiError } from "@/lib/api/client";

const staffSkillColumns = [
  { code: "B", label: "B / バリ" },
  { code: "C", label: "C / キャッシャー" },
  { code: "F", label: "F / フロア" },
  { code: "S", label: "S / サブ" },
  { code: "M", label: "M / 入金" },
  { code: "B_OPEN", label: "オープンB" },
  { code: "C_OPEN", label: "オープンC" },
  { code: "B_CLOSE", label: "クローズB" },
  { code: "C_CLOSE", label: "クローズC" },
  { code: "F_CLOSE", label: "クローズF" }
] as const;

type SetupForm = SetupWrite;
const hourOptions = buildHourOptions();
const minuteOptions = ["00", "15", "30", "45"];

export function SetupFlowPage({ initialSetup }: { initialSetup?: SetupData | null }) {
  const queryClient = useQueryClient();
  const setupQuery = useQuery({
    queryKey: ["operations", "setup"],
    queryFn: getSetup,
    initialData: initialSetup ?? undefined,
    retry: false
  });
  const [form, setForm] = useState<SetupForm | null>(() =>
    initialSetup ? buildSetupForm(initialSetup) : null
  );
  const setup = setupQuery.data;

  useEffect(() => {
    if (setup && !form) {
      setForm(buildSetupForm(setup));
    }
  }, [form, setup]);

  const saveMutation = useMutation({
    mutationFn: (payload: SetupWrite) => saveSetup(normalizeSetupForSave(payload)),
    onSuccess: (data) => {
      setForm(buildSetupForm(data));
      void queryClient.invalidateQueries({ queryKey: ["operations"] });
      void queryClient.invalidateQueries({ queryKey: ["daily-draft"] });
    }
  });

  if (setupQuery.isError) {
    return <SetupLoadError error={setupQuery.error} />;
  }

  if (setupQuery.isLoading || !form || !setup) {
    return <main className="min-h-screen bg-neutral-100 p-6 text-sm text-neutral-500">読み込み中</main>;
  }

  return (
    <main className="min-h-screen bg-neutral-100 text-neutral-950">
      <div className="mx-auto max-w-7xl px-6 py-6">
        <header className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold">初期設定</h1>
            <p className="mt-1 text-sm text-neutral-600">
              店舗・必要人数・従業員スキルを整えてから、日別の希望入力へ進みます。
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              className="h-10 rounded bg-neutral-950 px-4 text-sm text-white disabled:bg-neutral-300"
              disabled={saveMutation.isPending}
              onClick={() => saveMutation.mutate(form)}
              type="button"
            >
              {saveMutation.isPending ? "保存中" : "設定を保存"}
            </button>
            <Link
              className="inline-flex h-10 items-center rounded border bg-white px-4 text-sm"
              href={`/planning-periods/${setup.planning_period.id}/create`}
            >
              シフト案作成へ
            </Link>
          </div>
        </header>
        {saveMutation.isError && (
          <div className="mt-4 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            <div>{setupSaveErrorMessage(saveMutation.error)}</div>
            {isUnauthorizedApiError(saveMutation.error) && (
              <Link className="mt-2 inline-flex font-medium underline" href="/login">
                ログイン画面へ
              </Link>
            )}
          </div>
        )}
        {saveMutation.isSuccess && (
          <div className="mt-4 rounded border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">
            保存しました。
          </div>
        )}
        <div className="mt-6 grid gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
          <StoreSettings form={form} setForm={setForm} />
          <StaffSettings form={form} setup={setup} setForm={setForm} />
        </div>
      </div>
    </main>
  );
}

function SetupLoadError({ error }: { error: unknown }) {
  const isUnauthorized = isUnauthorizedApiError(error);
  const detail = formatApiErrorDetail(error);

  return (
    <main className="flex min-h-screen items-center justify-center bg-neutral-100 p-6 text-neutral-950">
      <section className="w-full max-w-md rounded border bg-white p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">CrewPilot</p>
        <h1 className="mt-2 text-2xl font-semibold">
          {isUnauthorized ? "ログインが必要です" : "初期設定を読み込めません"}
        </h1>
        <p className="mt-2 text-sm text-neutral-600">
          {isUnauthorized
            ? "Cookieが切れているか、まだログインしていません。店長アカウントで入り直してください。"
            : detail ?? "APIの状態を確認してから、もう一度読み込んでください。"}
        </p>
        <div className="mt-5 flex gap-2">
          <Link className="inline-flex h-10 items-center rounded bg-neutral-950 px-4 text-sm text-white" href="/login">
            ログインへ
          </Link>
          <button
            className="inline-flex h-10 items-center rounded border bg-white px-4 text-sm"
            onClick={() => window.location.reload()}
            type="button"
          >
            再読み込み
          </button>
        </div>
      </section>
    </main>
  );
}

function setupSaveErrorMessage(error: unknown) {
  if (isUnauthorizedApiError(error)) {
    return "ログイン状態が切れています。保存するにはもう一度ログインしてください。";
  }

  const detail = formatApiErrorDetail(error);
  return detail ? `保存に失敗しました: ${detail}` : "保存に失敗しました。入力内容を確認してください。";
}

function StoreSettings({
  form,
  setForm
}: {
  form: SetupForm;
  setForm: Dispatch<SetStateAction<SetupForm | null>>;
}) {
  const weekdayTemplates = requiredTemplates(form, "weekday");
  const holidayTemplates = requiredTemplates(form, "holiday");
  return (
    <section className="space-y-4">
      <div className="rounded border bg-white p-4">
        <h2 className="text-base font-semibold">店舗情報</h2>
        <label className="mt-3 block text-sm">
          <span className="text-neutral-500">店舗名</span>
          <input
            className="mt-1 w-full rounded border px-3 py-2"
            onChange={(event) =>
              setForm({ ...form, store: { ...form.store, name: event.target.value } })
            }
            value={form.store.name}
          />
        </label>
        <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
          <TimeInput label="平日 開店" value={businessHour(form, "weekday", "open")} onChange={(value) => setBusinessHour(form, setForm, "weekday", "open", value)} />
          <TimeInput label="平日 閉店" value={businessHour(form, "weekday", "close")} onChange={(value) => setBusinessHour(form, setForm, "weekday", "close", value)} />
          <TimeInput label="休日 開店" value={businessHour(form, "holiday", "open")} onChange={(value) => setBusinessHour(form, setForm, "holiday", "open", value)} />
          <TimeInput label="休日 閉店" value={businessHour(form, "holiday", "close")} onChange={(value) => setBusinessHour(form, setForm, "holiday", "close", value)} />
        </div>
      </div>
      <div className="rounded border bg-white p-4">
        <h2 className="text-base font-semibold">必要人数設定</h2>
        <div className="mt-3 space-y-4">
          <RequiredStaffSection
            label="平日の必要人数"
            onAdd={() =>
              setForm((current) =>
                current
                  ? setRequiredTemplates(current, "weekday", [
                      ...requiredTemplates(current, "weekday"),
                      { start_time: "18:00", end_time: "22:00", target_staff_count: 2 }
                    ])
                  : current
              )
            }
            onChange={(index, key, value) =>
              setForm((current) => (current ? updateTemplate(current, "weekday", index, key, value) : current))
            }
            onRemove={(index) =>
              setForm((current) =>
                current
                  ? setRequiredTemplates(
                      current,
                      "weekday",
                      requiredTemplates(current, "weekday").filter((_, itemIndex) => itemIndex !== index)
                    )
                  : current
              )
            }
            templates={weekdayTemplates}
          />
          <RequiredStaffSection
            label="休日の必要人数"
            onAdd={() =>
              setForm((current) =>
                current
                  ? setRequiredTemplates(current, "holiday", [
                      ...requiredTemplates(current, "holiday"),
                      { start_time: "18:00", end_time: "22:00", target_staff_count: 3 }
                    ])
                  : current
              )
            }
            onChange={(index, key, value) =>
              setForm((current) => (current ? updateTemplate(current, "holiday", index, key, value) : current))
            }
            onRemove={(index) =>
              setForm((current) =>
                current
                  ? setRequiredTemplates(
                      current,
                      "holiday",
                      requiredTemplates(current, "holiday").filter((_, itemIndex) => itemIndex !== index)
                    )
                  : current
              )
            }
            templates={holidayTemplates}
          />
        </div>
        <p className="mt-3 text-xs text-neutral-500">入金は日別作成時に10:00-10:30のTASKとして追加されます。</p>
      </div>
    </section>
  );
}

function RequiredStaffSection({
  label,
  onAdd,
  onChange,
  onRemove,
  templates
}: {
  label: string;
  onAdd: () => void;
  onChange: (index: number, key: string, value: string | number) => void;
  onRemove: (index: number) => void;
  templates: Array<Record<string, unknown>>;
}) {
  const [localTemplates, setLocalTemplates] = useState(templates);

  useEffect(() => {
    setLocalTemplates(templates);
  }, [templates]);

  const updateLocalTemplate = (index: number, key: string, value: string | number) => {
    setLocalTemplates((current) => {
      const next = [...current];
      next[index] = { ...next[index], [key]: value };
      return next;
    });
  };

  const commitTemplate = (index: number, key: string, value: string | number) => {
    updateLocalTemplate(index, key, value);
    onChange(index, key, value);
  };

  return (
    <div>
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">{label}</h3>
        <button className="rounded border px-2 py-1 text-xs" onClick={onAdd} type="button">
          追加
        </button>
      </div>
      <div className="mt-2 space-y-2">
        {localTemplates.map((item, index) => (
          <div className="grid grid-cols-[104px_104px_72px_32px] gap-2 text-sm" key={index}>
            <SplitTimeSelect
              label="開始時刻"
              onChange={(value) => commitTemplate(index, "start_time", value)}
              value={String(item.start_time)}
            />
            <SplitTimeSelect
              label="終了時刻"
              onChange={(value) => commitTemplate(index, "end_time", value)}
              value={String(item.end_time)}
            />
            <input
              className="rounded border px-2 py-1"
              min={0}
              onChange={(event) =>
                commitTemplate(
                  index,
                  "target_staff_count",
                  event.target.value === "" ? "" : Number(event.target.value)
                )
              }
              type="number"
              value={String(item.target_staff_count ?? "")}
            />
            <button className="rounded border text-xs" onClick={() => onRemove(index)} type="button">削除</button>
          </div>
        ))}
      </div>
    </div>
  );
}

function StaffSettings({
  form,
  setup,
  setForm
}: {
  form: SetupForm;
  setup: SetupData;
  setForm: Dispatch<SetStateAction<SetupForm | null>>;
}) {
  return (
    <section className="rounded border bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">従業員管理</h2>
          <p className="mt-1 text-xs text-neutral-500">
            従業員番号は追加時に自動採番されます。名前はシフト画面の表示に使います。
          </p>
        </div>
        <button
          className="rounded border px-3 py-1 text-sm"
          onClick={() =>
            setForm((current) => {
              if (!current) {
                return current;
              }
              const nextNumber = nextEmployeeNumber(current.staff_members);
              return {
                ...current,
                staff_members: [
                  ...current.staff_members,
                  {
                    employee_number: nextNumber,
                    display_name: "",
                    employment_type: "part_time",
                    hourly_wage_yen: null,
                    position_ids: [],
                    skill_definition_ids: [],
                    can_open: false,
                    can_close: false,
                    can_deposit: false,
                    is_active: true
                  }
                ]
              };
            })
          }
          type="button"
        >
          従業員追加
        </button>
      </div>
      <div className="mt-4 max-h-[520px] overflow-auto rounded border">
        <table className="w-full min-w-[1180px] border-collapse text-sm">
          <thead className="sticky top-0 z-10 bg-neutral-50 text-xs text-neutral-500 shadow-sm">
            <tr>
              <th className="border p-2 text-left">従業員番号</th>
              <th className="border p-2 text-left">名前</th>
              <th className="border p-2 text-left">雇用区分</th>
              {staffSkillColumns.map((column) => (
                <th className="border p-2" key={column.code}>{column.label}</th>
              ))}
              <th className="border p-2">有効</th>
              <th className="border p-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {form.staff_members.map((staff, index) => (
              <StaffRow
                key={staff.id ?? `new-${index}`}
                index={index}
                setup={setup}
                staff={staff}
                update={(next) => {
                  const staffMembers = [...form.staff_members];
                  staffMembers[index] = next;
                  setForm({ ...form, staff_members: staffMembers });
                }}
                onRemove={() => {
                  const shouldRemove =
                    !staff.id ||
                    window.confirm(`${staff.employee_number || "新規スタッフ"}を削除しますか？保存すると希望入力画面にも表示されなくなります。`);
                  if (!shouldRemove) {
                    return;
                  }
                  setForm({
                    ...form,
                    staff_members: form.staff_members.filter((_, itemIndex) => itemIndex !== index)
                  });
                }}
              />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function StaffRow({
  index,
  setup,
  staff,
  onRemove,
  update
}: {
  index: number;
  setup: SetupData;
  staff: StaffSetupWrite;
  onRemove: () => void;
  update: (staff: StaffSetupWrite) => void;
}) {
  return (
    <tr>
      <td className="border p-2">
        <input
          className="w-24 rounded border px-2 py-1"
          onChange={(event) => update({ ...staff, employee_number: event.target.value })}
          placeholder={String(101 + index)}
          value={staff.employee_number}
        />
      </td>
      <td className="border p-2">
        <input className="w-28 rounded border px-2 py-1" onChange={(event) => update({ ...staff, display_name: event.target.value })} value={staff.display_name} />
      </td>
      <td className="border p-2">
        <select className="rounded border px-2 py-1" onChange={(event) => update({ ...staff, employment_type: event.target.value })} value={staff.employment_type}>
          <option value="part_time">アルバイト</option>
          <option value="employee">社員</option>
          <option value="manager">店長</option>
        </select>
      </td>
      {staffSkillColumns.map((column) => {
        const skill = setup.skill_definitions.find((item) => item.code === column.code);
        const checked = Boolean(skill && staff.skill_definition_ids.includes(skill.id));
        return (
          <td className="border p-0 text-center" key={column.code}>
            <label className={`flex min-h-11 w-full items-center justify-center ${skill ? "cursor-pointer hover:bg-neutral-50" : "cursor-not-allowed"}`}>
              <input
                aria-label={`${staff.display_name || staff.employee_number || "従業員"} ${column.label}`}
                checked={checked}
                className="h-5 w-5 cursor-pointer accent-neutral-950 disabled:cursor-not-allowed"
                disabled={!skill}
                onChange={(event) => {
                  if (!skill) {
                    return;
                  }
                  update({
                    ...staff,
                    skill_definition_ids: event.target.checked
                      ? [...staff.skill_definition_ids, skill.id]
                      : staff.skill_definition_ids.filter((id) => id !== skill.id),
                    position_ids: nextPositionIds(staff, setup, skill, event.target.checked),
                    can_deposit: column.code === "M" ? event.target.checked : staff.can_deposit
                  });
                }}
                type="checkbox"
              />
            </label>
          </td>
        );
      })}
      <td className="border p-0 text-center">
        <label className="flex min-h-11 w-full cursor-pointer items-center justify-center hover:bg-neutral-50">
          <input
            aria-label={`${staff.display_name || staff.employee_number || "従業員"} 有効`}
            checked={staff.is_active}
            className="h-5 w-5 cursor-pointer accent-neutral-950"
            onChange={(event) => update({ ...staff, is_active: event.target.checked })}
            type="checkbox"
          />
        </label>
      </td>
      <td className="border p-2 text-center">
        <button
          className="rounded border border-red-200 px-2 py-1 text-xs text-red-700 hover:bg-red-50"
          onClick={onRemove}
          type="button"
        >
          削除
        </button>
      </td>
    </tr>
  );
}

function TimeInput({ label, onChange, value }: { label: string; onChange: (value: string) => void; value: string }) {
  return (
    <label className="block text-sm">
      <span className="text-xs text-neutral-500">{label}</span>
      <SplitTimeSelect className="mt-1 w-full" label={label} onChange={onChange} value={value} />
    </label>
  );
}

function SplitTimeSelect({
  className = "w-24",
  disabled = false,
  label,
  onChange,
  value
}: {
  className?: string;
  disabled?: boolean;
  label: string;
  onChange: (value: string) => void;
  value: string;
}) {
  const [open, setOpen] = useState(false);
  const normalizedValue = normalizeSplitTimeValue(value);
  const [selectedHour, selectedMinute] = normalizedValue.split(":");

  return (
    <div
      className={`relative inline-block text-left ${className}`}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
          setOpen(false);
        }
      }}
    >
      <button
        aria-expanded={open}
        aria-label={label}
        className="flex h-9 w-full items-center justify-between rounded border bg-white px-2 text-sm font-medium shadow-sm disabled:bg-neutral-100 disabled:text-neutral-400"
        disabled={disabled}
        onClick={() => setOpen((current) => !current)}
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
                  onChange(`${hour}:${selectedMinute}`);
                  if (selectedMinute === "00") {
                    setOpen(false);
                  }
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
                  onChange(`${selectedHour}:${minute}`);
                  setOpen(false);
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

function buildSetupForm(setup: SetupData): SetupForm {
  const businessHours = normalizeBusinessHours(
    setup.store.business_hours,
    setup.store.opening_time,
    setup.store.closing_time
  );
  const operationalSettings = normalizeOperationalSettings(setup.store.operational_settings);
  return {
    store: {
      name: setup.store.name,
      opening_time: setup.store.opening_time.slice(0, 5),
      closing_time: setup.store.closing_time.slice(0, 5),
      business_hours: businessHours,
      operational_settings: operationalSettings
    },
    staff_members: staffMembersToForm(setup)
  };
}

function staffMembersToForm(setup: SetupData): StaffSetupWrite[] {
  const usedNumbers = new Set<string>();
  return sortStaffByEmployeeNumber(setup.staff_members).map((staff) => {
    const rawNumber = (staff.employee_number ?? "").trim();
    const employeeNumber =
      isUsableEmployeeNumber(rawNumber, usedNumbers)
        ? rawNumber
        : nextAvailableEmployeeNumber(usedNumbers);
    usedNumbers.add(employeeNumber);
    return staffToForm(
      staff,
      setup.positions,
      setup.skill_definitions,
      setup.staff_skills,
      employeeNumber
    );
  });
}

function normalizeBusinessHours(
  businessHours: Record<string, unknown> | null,
  opening: string,
  closing: string
) {
  const defaults = defaultBusinessHours(opening, closing);
  const source = businessHours ?? {};
  return {
    weekday: {
      ...defaults.weekday,
      ...((source.weekday as object | undefined) ?? {})
    },
    holiday: {
      ...defaults.holiday,
      ...((source.holiday as object | undefined) ?? {})
    }
  };
}

function normalizeOperationalSettings(settings: Record<string, unknown> | null) {
  const defaults = defaultOperationalSettings();
  const source = settings ?? {};
  const legacyTemplates = source.required_staff_templates as
    | Array<Record<string, unknown>>
    | undefined;
  return {
    ...defaults,
    ...source,
    weekday_required_staff_templates:
      (source.weekday_required_staff_templates as Array<Record<string, unknown>> | undefined)
      ?? legacyTemplates
      ?? defaults.weekday_required_staff_templates,
    holiday_required_staff_templates:
      (source.holiday_required_staff_templates as Array<Record<string, unknown>> | undefined)
      ?? legacyTemplates
      ?? defaults.holiday_required_staff_templates
  };
}

function staffToForm(
  staff: StaffMember,
  positions: Position[],
  skills: SkillDefinition[],
  staffSkills: StaffSkillRead[],
  employeeNumber: string
): StaffSetupWrite {
  const skillIds = new Set(staffSkills.filter((item) => item.staff_member_id === staff.id).map((item) => item.skill_definition_id));
  const positionIds = positions
    .filter((position) =>
      skills.some(
        (skill) =>
          skill.position_id === position.id
          && skill.skill_category === "position"
          && skillIds.has(skill.id)
      )
    )
    .map((position) => position.id);
  return {
    id: staff.id,
    employee_number: employeeNumber,
    display_name: isGeneratedStaffName(staff.display_name) ? "" : staff.display_name,
    employment_type: staff.employment_type,
    hourly_wage_yen: staff.hourly_wage_yen,
    position_ids: positionIds,
    skill_definition_ids: [...skillIds],
    can_open: skills.some((skill) => skill.code.includes("OPEN") && skillIds.has(skill.id)),
    can_close: skills.some((skill) => skill.code.includes("CLOSE") && skillIds.has(skill.id)),
    can_deposit: skills.some((skill) => skill.code === "M" && skillIds.has(skill.id)),
    is_active: staff.is_active
  };
}

function nextPositionIds(
  staff: StaffSetupWrite,
  setup: SetupData,
  skill: SkillDefinition,
  checked: boolean
) {
  if (skill.skill_category !== "position" || !skill.position_id) {
    return staff.position_ids;
  }
  if (checked) {
    return staff.position_ids.includes(skill.position_id)
      ? staff.position_ids
      : [...staff.position_ids, skill.position_id];
  }
  return staff.position_ids.filter((id) => id !== skill.position_id);
}

function defaultBusinessHours(opening: string, closing: string) {
  const open = opening.slice(0, 5);
  const close = closing.slice(0, 5);
  return {
    weekday: { open, close },
    holiday: { open: "10:00", close }
  };
}

function defaultOperationalSettings() {
  const weekdayTemplates = [
    { start_time: "09:00", end_time: "12:00", target_staff_count: 2 },
    { start_time: "12:00", end_time: "15:00", target_staff_count: 3 },
    { start_time: "15:00", end_time: "18:00", target_staff_count: 2 }
  ];
  return {
    weekday_required_staff_templates: weekdayTemplates,
    holiday_required_staff_templates: weekdayTemplates.map((item) => ({
      ...item,
      target_staff_count: Number(item.target_staff_count) + 1
    })),
    deposit_rule: {
      primary_start: "10:00",
      primary_end: "10:30",
      fallback: "previous_day_close_30_minutes"
    }
  };
}

function businessHour(form: SetupForm, key: string, field: "open" | "close") {
  const hours = form.store.business_hours as Record<string, { open?: string; close?: string; }>;
  return hours[key]?.[field] ?? "09:00";
}

function setBusinessHour(
  form: SetupForm,
  setForm: Dispatch<SetStateAction<SetupForm | null>>,
  key: string,
  field: "open" | "close",
  value: string
) {
  setForm((currentForm) => {
    const source = currentForm ?? form;
    const current = source.store.business_hours as Record<string, unknown>;
    const next = structuredClone(current);
    next[key] = { ...(next[key] as object), [field]: value };
    return { ...source, store: { ...source.store, business_hours: next } };
  });
}

function requiredTemplates(form: SetupForm, dayType: "weekday" | "holiday") {
  const settings = form.store.operational_settings as {
    required_staff_templates?: Array<Record<string, unknown>>;
    weekday_required_staff_templates?: Array<Record<string, unknown>>;
    holiday_required_staff_templates?: Array<Record<string, unknown>>;
  };
  if (dayType === "weekday") {
    return settings.weekday_required_staff_templates ?? settings.required_staff_templates ?? [];
  }
  return (
    settings.holiday_required_staff_templates
    ?? settings.weekday_required_staff_templates
    ?? settings.required_staff_templates
    ?? []
  );
}

function setRequiredTemplates(
  form: SetupForm,
  dayType: "weekday" | "holiday",
  templates: Array<Record<string, unknown>>
) {
  const key = `${dayType}_required_staff_templates`;
  return {
    ...form,
    store: {
      ...form.store,
      operational_settings: {
        ...form.store.operational_settings,
        [key]: templates
      }
    }
  };
}

function updateTemplate(
  form: SetupForm,
  dayType: "weekday" | "holiday",
  index: number,
  key: string,
  value: string | number
) {
  const templates = [...requiredTemplates(form, dayType)];
  templates[index] = { ...templates[index], [key]: value };
  return setRequiredTemplates(form, dayType, templates);
}

function buildHourOptions() {
  return Array.from({ length: 24 }, (_, hour) => String(hour).padStart(2, "0"));
}

function normalizeSplitTimeValue(value: string) {
  const normalized = value.slice(0, 5);
  const [hour, minute] = normalized.split(":");
  if (hourOptions.includes(hour) && minuteOptions.includes(minute)) {
    return `${hour}:${minute}`;
  }
  return "09:00";
}

function nextEmployeeNumber(staffMembers: StaffSetupWrite[]) {
  const numbers = staffMembers
    .map((staff) => Number.parseInt(staff.employee_number, 10))
    .filter((value) => Number.isFinite(value));
  const next = numbers.length > 0 ? Math.max(...numbers) + 1 : 101;
  return String(next);
}

function isUsableEmployeeNumber(value: string, usedNumbers: Set<string>) {
  return /^\d+$/.test(value) && !usedNumbers.has(value);
}

function nextAvailableEmployeeNumber(usedNumbers: Set<string>) {
  let candidate = 101;
  while (usedNumbers.has(String(candidate))) {
    candidate += 1;
  }
  return String(candidate);
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

function normalizeSetupForSave(form: SetupWrite): SetupWrite {
  const usedNumbers = new Set<string>();
  return {
    ...form,
    staff_members: form.staff_members.map((staff) => {
      const rawNumber = staff.employee_number.trim();
      const employeeNumber =
        isUsableEmployeeNumber(rawNumber, usedNumbers)
          ? rawNumber
          : nextAvailableEmployeeNumber(usedNumbers);
      usedNumbers.add(employeeNumber);
      return {
        ...staff,
        employee_number: employeeNumber,
        display_name: staff.display_name.trim(),
        hourly_wage_yen: staff.hourly_wage_yen ?? null
      };
    })
  };
}

function isGeneratedStaffName(value: string) {
  return /^新規スタッフ\d+$/.test(value.trim());
}
