import type { WorkspaceData } from "../types";
import { useSelectionStore } from "../store/selectionStore";

type StatusBarProps = {
  workspace?: WorkspaceData;
  isFetching: boolean;
  isError: boolean;
  unsavedCount: number;
  selectedDate?: string;
};

export function StatusBar({ workspace, isFetching, isError, unsavedCount, selectedDate }: StatusBarProps) {
  const selection = useSelectionStore((state) => state.selection);

  return (
    <footer className="flex h-8 shrink-0 items-center justify-between border-t bg-white px-3 text-xs text-neutral-600">
      <span>
        {isError
          ? "API接続エラー"
          : isFetching
            ? "同期中"
            : workspace
              ? `${workspace.planning_period.start_date} - ${workspace.planning_period.end_date}`
              : "待機中"}
      </span>
      <span>
        日付 {selectedDate ? formatDateWithWeekday(selectedDate) : "-"} / 選択{" "}
        {selection ? `${selection.type}:${selection.id.slice(0, 8)}` : "-"} / Unsaved {unsavedCount} / Requests{" "}
        {workspace?.shift_requests.length ?? 0} / Requirements{" "}
        {workspace?.shift_requirements.length ?? 0}
      </span>
    </footer>
  );
}

function formatDateWithWeekday(value: string) {
  const date = new Date(`${value}T00:00:00`);
  const weekdays = ["日", "月", "火", "水", "木", "金", "土"];
  return `${value.replaceAll("-", "/")}（${weekdays[date.getDay()]}）`;
}
