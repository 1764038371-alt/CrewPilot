import { CalendarDays, Filter, Users } from "lucide-react";
import type { WorkspaceData } from "../types";

type LeftSidebarProps = {
  workspace?: WorkspaceData;
};

export function LeftSidebar({ workspace }: LeftSidebarProps) {
  return (
    <aside className="min-h-0 overflow-auto bg-white p-3">
      <div className="space-y-4">
        <section>
          <h2 className="flex items-center gap-2 text-xs font-semibold uppercase text-neutral-500">
            <CalendarDays className="h-4 w-4" />
            View
          </h2>
          <div className="mt-2 grid gap-1">
            {["日別", "週別", "スタッフ別", "警告中心"].map((label) => (
              <button
                className="rounded px-2 py-1.5 text-left text-sm hover:bg-neutral-100"
                key={label}
                type="button"
              >
                {label}
              </button>
            ))}
          </div>
        </section>
        <section>
          <h2 className="flex items-center gap-2 text-xs font-semibold uppercase text-neutral-500">
            <Filter className="h-4 w-4" />
            Filters
          </h2>
          <div className="mt-2 space-y-2 text-sm">
            <label className="flex items-center gap-2">
              <input type="checkbox" />
              警告ありのみ
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" />
              ロック済みのみ
            </label>
          </div>
        </section>
        <section>
          <h2 className="flex items-center gap-2 text-xs font-semibold uppercase text-neutral-500">
            <Users className="h-4 w-4" />
            Staff
          </h2>
          <div className="mt-2 space-y-1">
            {(workspace?.staff_members ?? []).slice(0, 12).map((staff) => (
              <div className="rounded px-2 py-1 text-sm text-neutral-700" key={staff.id}>
                <div className="font-medium">{staff.employee_number ?? staff.display_name}</div>
                <div className="truncate text-xs text-neutral-400">{staff.display_name}</div>
              </div>
            ))}
            {!workspace && <div className="text-sm text-neutral-400">読み込み中</div>}
          </div>
        </section>
      </div>
    </aside>
  );
}
