"use client";

import { useQuery } from "@tanstack/react-query";
import { getWorkspace } from "../api/workspaceApi";
import type { WorkspaceData } from "../types";

export function useWorkspaceQuery(planningPeriodId: string, initialData?: WorkspaceData) {
  return useQuery({
    queryKey: ["workspace", planningPeriodId],
    queryFn: () => getWorkspace(planningPeriodId),
    initialData,
    enabled: planningPeriodId.length > 0
  });
}
