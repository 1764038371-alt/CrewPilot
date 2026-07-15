"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LogOut } from "lucide-react";
import { logout } from "../api/authApi";

export function LogoutButton() {
  const queryClient = useQueryClient();
  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
      window.location.assign("/login");
    }
  });

  return (
    <button
      className="inline-flex h-10 items-center gap-2 rounded border border-neutral-300 bg-white px-4 text-sm text-neutral-700 hover:bg-neutral-50 disabled:cursor-wait disabled:text-neutral-400"
      disabled={logoutMutation.isPending}
      onClick={() => logoutMutation.mutate()}
      type="button"
    >
      <LogOut className="h-4 w-4" />
      {logoutMutation.isPending ? "ログアウト中" : "ログアウト"}
    </button>
  );
}
