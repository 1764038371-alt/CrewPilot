import { SetupFlowPage } from "@/features/operations/components/SetupFlowPage";
import type { SetupData } from "@/features/operations/api/operationsApi";

export const dynamic = "force-dynamic";

async function getInitialSetup(): Promise<SetupData | null> {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

  try {
    const response = await fetch(`${apiBaseUrl}/api/setup`, { cache: "no-store" });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as SetupData;
  } catch {
    return null;
  }
}

export default async function HomePage() {
  const initialSetup = await getInitialSetup();
  return <SetupFlowPage initialSetup={initialSetup} />;
}
