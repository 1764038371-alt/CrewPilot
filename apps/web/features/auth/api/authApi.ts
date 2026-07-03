import { apiGet, apiPost } from "@/lib/api/client";

export type UserRole = "admin" | "manager" | "viewer";

export type CurrentUser = {
  id: string;
  email: string;
  display_name: string;
  role: UserRole | string;
  is_active: boolean;
};

export type LoginResponse = {
  user: CurrentUser;
  expires_at: string;
};

export function login(email: string, password: string): Promise<LoginResponse> {
  return apiPost<LoginResponse>("/api/auth/login", { email, password });
}

export function logout(): Promise<{ status: string }> {
  return apiPost<{ status: string }>("/api/auth/logout", {});
}

export function getCurrentUser(): Promise<CurrentUser> {
  return apiGet<CurrentUser>("/api/auth/me");
}
