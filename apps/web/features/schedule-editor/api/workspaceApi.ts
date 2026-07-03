import { apiGet } from "@/lib/api/client";
import type { WorkspaceData } from "../types";

export function getWorkspace(planningPeriodId: string): Promise<WorkspaceData> {
  return apiGet<WorkspaceData>(`/api/workspaces/planning-periods/${planningPeriodId}`);
}

