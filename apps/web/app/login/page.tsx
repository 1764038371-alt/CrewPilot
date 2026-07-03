"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError } from "@/lib/api/client";
import { login } from "@/features/auth/api/authApi";

const workspacePath = "/planning-periods/20000000-0000-0000-0000-000000000001/workspace";
const quickUsers = [
  {
    email: "manager@example.com",
    label: "店長",
    description: "編集・AI提案・公開まで操作できます。"
  },
  {
    email: "admin@example.com",
    label: "管理者",
    description: "すべての操作を確認できます。"
  },
  {
    email: "viewer@example.com",
    label: "閲覧者",
    description: "編集不可の表示確認に使います。"
  }
];

export default function LoginPage() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const [email, setEmail] = useState("manager@example.com");
  const [password, setPassword] = useState("");
  const loginMutation = useMutation({
    mutationFn: (payload?: { email: string; password: string }) =>
      login(payload?.email ?? email, payload?.password ?? password),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
      router.push(workspacePath);
    }
  });
  const errorMessage = loginMutation.error ? formatLoginError(loginMutation.error) : null;

  return (
    <main
      className="flex min-h-screen items-center justify-center bg-neutral-100 p-6 text-neutral-950"
      style={{
        alignItems: "center",
        background: "#f5f5f5",
        color: "#171717",
        display: "flex",
        justifyContent: "center",
        minHeight: "100vh",
        padding: 24
      }}
    >
      <section
        className="w-full max-w-md rounded border bg-white p-6 shadow-sm"
        style={{
          background: "#fff",
          border: "1px solid #e5e5e5",
          borderRadius: 8,
          boxShadow: "0 1px 2px rgba(0,0,0,0.06)",
          maxWidth: 480,
          padding: 24,
          width: "100%"
        }}
      >
        <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">CrewPilot</p>
        <h1 className="mt-2 text-2xl font-semibold">ログイン</h1>
        <p className="mt-2 text-sm text-neutral-600">
          共有されたパスワードを知っている人だけがCrewPilotに入れます。
        </p>
        {errorMessage && (
          <div className="mt-4 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {errorMessage}
          </div>
        )}
        <div className="mt-5 grid gap-2">
          <p className="text-xs font-semibold text-neutral-500">アカウントを選択</p>
          {quickUsers.map((user) => (
            <button
              className="rounded border bg-white p-3 text-left text-sm hover:bg-neutral-50 disabled:opacity-50"
              disabled={loginMutation.isPending}
              key={user.email}
              onClick={() => {
                setEmail(user.email);
              }}
              type="button"
            >
              <span className="block font-semibold">{user.label}</span>
              <span className="mt-1 block text-xs text-neutral-500">{user.description}</span>
            </button>
          ))}
        </div>
        <div className="my-5 flex items-center gap-3 text-xs text-neutral-400">
          <span className="h-px flex-1 bg-neutral-200" />
          直接入力
          <span className="h-px flex-1 bg-neutral-200" />
        </div>
        <form
          className="space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            loginMutation.mutate({ email, password });
          }}
        >
          <label className="block text-sm">
            <span className="text-neutral-600">Email</span>
            <input
              className="mt-1 w-full rounded border px-3 py-2"
              onChange={(event) => setEmail(event.target.value)}
              type="email"
              value={email}
            />
          </label>
          <label className="block text-sm">
            <span className="text-neutral-600">Password</span>
            <input
              className="mt-1 w-full rounded border px-3 py-2"
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              value={password}
            />
          </label>
          <button
            className="h-10 w-full rounded bg-neutral-950 text-sm font-semibold text-white disabled:bg-neutral-300"
            disabled={loginMutation.isPending}
            type="submit"
          >
            {loginMutation.isPending ? "ログイン中..." : "ログインしてWorkspaceへ"}
          </button>
        </form>
        <p className="mt-4 text-xs leading-5 text-neutral-500">
          パスワードは管理者から共有されたものを入力してください。
        </p>
      </section>
    </main>
  );
}

function formatLoginError(error: unknown) {
  if (error instanceof ApiError) {
    if (typeof error.body === "object" && error.body && "detail" in error.body) {
      const detail = error.body.detail;
      return typeof detail === "string" ? detail : JSON.stringify(detail);
    }
  }
  return error instanceof Error ? error.message : "ログインに失敗しました。";
}
