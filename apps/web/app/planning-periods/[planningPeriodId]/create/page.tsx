import { ShiftCreatePage } from "@/features/operations/components/ShiftCreatePage";

type PageProps = {
  params: Promise<{
    planningPeriodId: string;
  }>;
};

export default async function Page({ params }: PageProps) {
  const { planningPeriodId } = await params;
  return <ShiftCreatePage planningPeriodId={planningPeriodId} />;
}
