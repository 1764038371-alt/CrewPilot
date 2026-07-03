import { WorkspaceLayout } from "@/features/schedule-editor/components/WorkspaceLayout";
import { getWorkspace } from "@/features/schedule-editor/api/workspaceApi";

type WorkspacePageProps = {
  params: Promise<{
    planningPeriodId: string;
  }>;
};

export default async function WorkspacePage({ params }: WorkspacePageProps) {
  const { planningPeriodId } = await params;
  const initialWorkspace = await getInitialWorkspace(planningPeriodId);

  return <WorkspaceLayout initialWorkspace={initialWorkspace} planningPeriodId={planningPeriodId} />;
}

async function getInitialWorkspace(planningPeriodId: string) {
  try {
    return await getWorkspace(planningPeriodId);
  } catch {
    return undefined;
  }
}
