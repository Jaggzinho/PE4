import { apiFetch, setToken } from "./client";
import type { ApiId } from "./client";

export type Session = {
  user_id: ApiId;
  username: string;
  role_name: string;
  permissions: Record<string, boolean>;
};

export type SetupStatus = { needs_setup: boolean };

export async function login(username: string, password: string): Promise<void> {
  const data = await apiFetch<{ access_token: string }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  setToken(data.access_token);
}

export function setupStatus(): Promise<SetupStatus> {
  return apiFetch("/api/setup/status");
}

export async function setupFirstAdmin(
  setupToken: string,
  username: string,
  password: string,
  password2: string,
): Promise<void> {
  await apiFetch("/api/setup/first-admin", {
    method: "POST",
    headers: { "X-PE3-SETUP-TOKEN": setupToken },
    body: JSON.stringify({ username, password, password2 }),
  });
}

export function me(): Promise<Session> {
  return apiFetch("/api/auth/me");
}
