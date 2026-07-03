import { apiGet, apiPut } from "@/lib/api/client";
import type {
  PlanningPeriod,
  Position,
  ShiftRequest,
  SkillDefinition,
  StaffMember,
  Store,
  TaskType,
  Uuid
} from "@/features/schedule-editor/types";

export type StaffSkillRead = {
  staff_member_id: Uuid;
  skill_definition_id: Uuid;
};

export type SetupData = {
  store: Store;
  planning_period: PlanningPeriod;
  staff_members: StaffMember[];
  positions: Position[];
  task_types: TaskType[];
  skill_definitions: SkillDefinition[];
  staff_skills: StaffSkillRead[];
};

export type StaffSetupWrite = {
  id?: Uuid;
  employee_number: string;
  display_name: string;
  employment_type: string;
  hourly_wage_yen: number | null;
  position_ids: Uuid[];
  skill_definition_ids: Uuid[];
  can_open: boolean;
  can_close: boolean;
  can_deposit: boolean;
  is_active: boolean;
};

export type SetupWrite = {
  store: {
    name: string;
    opening_time: string;
    closing_time: string;
    business_hours: Record<string, unknown>;
    operational_settings: Record<string, unknown>;
  };
  staff_members: StaffSetupWrite[];
};

export type DailyDraftData = {
  planning_period: PlanningPeriod;
  store: Store;
  staff_members: StaffMember[];
  shift_requests: ShiftRequest[];
};

export type DailyDraftWrite = {
  target_date: string;
  requests: Array<{
    staff_member_id: Uuid;
    request_type: string;
    start_time: string | null;
    end_time: string | null;
    note?: string | null;
  }>;
  required_staff_templates: Array<Record<string, unknown>>;
};

export function getSetup(): Promise<SetupData> {
  return apiGet<SetupData>("/api/setup");
}

export function saveSetup(payload: SetupWrite): Promise<SetupData> {
  return apiPut<SetupData>("/api/setup", payload);
}

export function getDailyDraft(planningPeriodId: Uuid, targetDate: string): Promise<DailyDraftData> {
  return apiGet<DailyDraftData>(
    `/api/planning-periods/${planningPeriodId}/daily-draft?target_date=${targetDate}`
  );
}

export function saveDailyDraft(
  planningPeriodId: Uuid,
  payload: DailyDraftWrite
): Promise<DailyDraftData> {
  return apiPut<DailyDraftData>(`/api/planning-periods/${planningPeriodId}/daily-draft`, payload);
}
