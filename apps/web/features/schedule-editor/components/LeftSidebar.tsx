import { Info, Users } from "lucide-react";
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
            <Info className="h-4 w-4" />
            操作
          </h2>
          <div className="mt-2 space-y-2 rounded border bg-neutral-50 p-3 text-xs leading-relaxed text-neutral-600">
            <p>セルをクリックして選択します。</p>
            <p>右クリックで変更・削除・固定できます。</p>
            <p>編集後は上部の保存を押します。</p>
          </div>
        </section>
        <section>
          <h2 className="flex items-center gap-2 text-xs font-semibold uppercase text-neutral-500">
            <Users className="h-4 w-4" />
            Staff
          </h2>
          <div className="mt-2 max-h-[calc(100vh-260px)] space-y-1 overflow-y-auto pr-1">
            {(workspace?.staff_members ?? []).map((staff) => (
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
