export type Uuid = string;

export type Store = {
  id: Uuid;
  name: string;
  code: string;
  timezone: string;
  opening_time: string;
  closing_time: string;
  business_hours: Record<string, unknown> | null;
  operational_settings: Record<string, unknown> | null;
  time_slot_minutes: number;
  is_active: boolean;
};

export type StaffMember = {
  id: Uuid;
  store_id: Uuid;
  employee_number: string | null;
  display_name: string;
  employment_type: string;
  hourly_wage_yen: number | null;
  max_weekly_minutes: number | null;
  min_shift_minutes: number | null;
  max_shift_minutes: number | null;
  priority: number;
  is_active: boolean;
  joined_on: string | null;
  left_on: string | null;
};

export type Position = {
  id: Uuid;
  store_id: Uuid;
  name: string;
  code: string;
  priority: number;
  color: string | null;
  is_active: boolean;
};

export type TaskType = {
  id: Uuid;
  store_id: Uuid;
  code: string;
  name: string;
  description: string | null;
  default_duration_minutes: number | null;
  requires_offsite: boolean;
  priority: number;
  is_active: boolean;
};

export type SkillDefinition = {
  id: Uuid;
  store_id: Uuid;
  code: string;
  name: string;
  skill_category: string;
  position_id: Uuid | null;
  task_type_id: Uuid | null;
  description: string | null;
  is_active: boolean;
};

export type StaffSkill = {
  staff_member_id: Uuid;
  skill_definition_id: Uuid;
};

export type PlanningPeriod = {
  id: Uuid;
  store_id: Uuid;
  name: string;
  start_date: string;
  end_date: string;
  status: string;
  request_deadline: string | null;
};

export type ShiftRequest = {
  id: Uuid;
  planning_period_id: Uuid;
  staff_member_id: Uuid;
  request_date: string;
  start_time: string | null;
  end_time: string | null;
  request_type: string;
  priority: number;
  note: string | null;
};

export type ShiftRequirement = {
  id: Uuid;
  planning_period_id: Uuid;
  store_id: Uuid;
  requirement_date: string;
  start_time: string;
  end_time: string;
  requirement_type: "WORK" | "TASK";
  position_id: Uuid | null;
  task_type_id: Uuid | null;
  min_staff_count: number;
  target_staff_count: number;
  max_staff_count: number | null;
  priority: number;
};

export type ScheduleVersion = {
  id: Uuid;
  planning_period_id: Uuid;
  store_id: Uuid;
  parent_schedule_version_id: Uuid | null;
  version_number: number;
  revision: number;
  name: string;
  status: "draft" | "approved" | "published" | "archived" | string;
  is_locked: boolean;
  published_at: string | null;
  published_by?: string | null;
  change_summary: string | null;
};

export type WorkShift = {
  id: Uuid;
  schedule_version_id: Uuid;
  staff_member_id: Uuid;
  store_id: Uuid;
  work_date: string;
  start_time: string;
  end_time: string;
  total_work_minutes: number;
  total_break_minutes: number;
  assignment_source: string;
  is_locked: boolean;
  lock_scope: string | null;
  locked_at: string | null;
  lock_reason: string | null;
  note: string | null;
};

export type ShiftSegment = {
  id: Uuid;
  work_shift_id: Uuid;
  schedule_version_id: Uuid;
  store_id: Uuid;
  segment_date: string;
  start_time: string;
  end_time: string;
  segment_type: "WORK" | "BREAK" | "TASK";
  position_id: Uuid | null;
  task_type_id: Uuid | null;
  label: string | null;
  assignment_source: string;
  is_locked: boolean;
  lock_scope: string | null;
  locked_at: string | null;
  lock_reason: string | null;
  confidence_score: string | null;
  note: string | null;
};

export type ScheduleWarning = {
  id: Uuid;
  schedule_version_id: Uuid;
  work_shift_id: Uuid | null;
  shift_segment_id: Uuid | null;
  warning_type: string;
  severity: string;
  message: string;
  details: Record<string, unknown> | null;
};

export type ProposalChange = {
  id: Uuid;
  proposal_id: Uuid;
  change_type: string;
  target_type: string;
  target_id: Uuid | null;
  command_type: string;
  command_payload: Record<string, unknown>;
  before_value: unknown;
  after_value: unknown;
  explanation: Record<string, unknown> | null;
  sort_order: number;
};

export type OptimizationProposal = {
  id: Uuid;
  schedule_version_id: Uuid;
  optimization_run_id: Uuid | null;
  title: string;
  summary: string | null;
  summary_metrics: Record<string, number> | null;
  status: "pending" | "applied" | "rejected" | string;
  generated_by: string;
  created_at: string;
  applied_at: string | null;
  rejected_at: string | null;
  changes: ProposalChange[];
};

export type OptimizationRun = {
  id: Uuid;
  schedule_version_id: Uuid;
  solver_name: string;
  status: string;
  scope: Record<string, unknown>;
  solve_time_ms: number;
  objective_value: number | null;
  warning_before: Record<string, number>;
  warning_after: Record<string, number>;
  changed_segments: number;
  changed_work_shifts: number;
  fairness_score: number | null;
  created_at: string;
};

export type ProposalActionResult = {
  proposal_id: Uuid;
  status: string;
  applied_commands: number;
};

export type OptimizationScope =
  | {
      type: "full";
    }
  | {
      type: "date";
      date: string;
    }
  | {
      type: "time_range";
      date: string;
      start_time: string;
      end_time: string;
    }
  | {
      type: "staff";
      staff_member_id: Uuid;
      date?: string | null;
    }
  | {
      type: "warning";
      warning_id: Uuid;
    };

export type OptimizationRequest = {
  scope: OptimizationScope;
  time_limit_seconds?: number;
};

export type ExplanationFactor = {
  key: string;
  label: string;
  value: string;
  impact: "positive" | "negative" | "neutral" | string;
};

export type RequiredSkillExplanation = {
  id: Uuid;
  code: string;
  name: string;
  matched: boolean;
};

export type WarningExplanation = {
  id: Uuid;
  warning_type: string;
  severity: string;
  message: string;
};

export type CandidateStaffExplanation = {
  staff_member_id: Uuid;
  display_name: string;
  fit_score: number;
  reason: string;
};

export type ShiftSegmentExplanation = {
  target_type: "ShiftSegment" | string;
  target_id: Uuid;
  generated_by: string;
  assignment_reason: string;
  factors: ExplanationFactor[];
  required_skills: RequiredSkillExplanation[];
  current_warnings: WarningExplanation[];
  candidate_staff: CandidateStaffExplanation[];
  lock_state: {
    is_locked: boolean;
    lock_scope: string | null;
    lock_reason: string | null;
  };
};

export type ScheduleChangeLog = {
  id: Uuid;
  schedule_version_id: Uuid;
  work_shift_id: Uuid | null;
  shift_segment_id: Uuid | null;
  command_type: string;
  command_payload: Record<string, unknown> | null;
  inverse_payload: Record<string, unknown> | null;
  before_value: unknown;
  after_value: unknown;
  reason: string | null;
  executed_by: string;
  executed_by_user_id: Uuid | null;
  source_type: string | null;
  source_id: Uuid | null;
  batch_id: Uuid | null;
  batch_label: string | null;
  explanation: Record<string, unknown> | null;
  is_undone: boolean;
  undone_at: string | null;
  parent_change_log_id: Uuid | null;
  created_at: string;
};

export type WorkspaceData = {
  planning_period: PlanningPeriod;
  store: Store;
  current_schedule_version: ScheduleVersion | null;
  staff_members: StaffMember[];
  positions: Position[];
  task_types: TaskType[];
  skill_definitions: SkillDefinition[];
  staff_skills: StaffSkill[];
  shift_requests: ShiftRequest[];
  shift_requirements: ShiftRequirement[];
  work_shifts: WorkShift[];
  shift_segments: ShiftSegment[];
  warnings: ScheduleWarning[];
  locks: Record<string, unknown>[];
};
