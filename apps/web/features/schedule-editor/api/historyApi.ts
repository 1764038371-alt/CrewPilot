import { apiGet } from "@/lib/api/client";
import type { OptimizationRun, ScheduleChangeLog, Uuid } from "../types";

export function listScheduleChangeLogs(scheduleVersionId: Uuid): Promise<ScheduleChangeLog[]> {
  return apiGet<ScheduleChangeLog[]>(
    `/api/schedule-versions/${scheduleVersionId}/change-logs`
  );
}

export function listOptimizationRuns(scheduleVersionId: Uuid): Promise<OptimizationRun[]> {
  return apiGet<OptimizationRun[]>(
    `/api/schedule-versions/${scheduleVersionId}/optimization-runs`
  );
}
