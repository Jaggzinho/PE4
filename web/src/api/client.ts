export type ApiErrorPayload = {
  code?: string;
  message?: string;
  detail?: unknown;
};

/** Decimal string so DuckDB BIGINT identifiers remain exact in JavaScript. */
export type ApiId = string;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: unknown;

  constructor(status: number, payload: ApiErrorPayload) {
    super(payload.message || `HTTP ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.code = payload.code || `http_${status}`;
    this.detail = payload.detail;
  }
}

const TOKEN_KEY = "pe3_access_token";
// Old tokens lack an environment claim. Each tab now owns its session.
localStorage.removeItem(TOKEN_KEY);

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (!token) sessionStorage.removeItem(TOKEN_KEY);
  else sessionStorage.setItem(TOKEN_KEY, token);
}

export function getEnvironmentId(): string {
  return sessionStorage.getItem("pe3.environment") || "tcm_ro";
}

export function environmentStorageKey(key: string): string {
  return `pe3.${getEnvironmentId()}.${key}`;
}

function checkSession(token: string | null): void {
  if (token !== getToken()) throw new ApiError(409, { code: "session_changed", message: "The session changed. Please retry." });
}

async function errorFromResponse(response: Response): Promise<ApiError> {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    try {
      return new ApiError(response.status, (await response.json()) as ApiErrorPayload);
    } catch {
      return new ApiError(response.status, {});
    }
  }
  const message = await response.text();
  return new ApiError(response.status, { message: message || undefined });
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init?.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...init, headers });
  checkSession(token);
  if (!response.ok) throw await errorFromResponse(response);
  if (response.status === 204 || response.status === 205) return undefined as T;
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) return undefined as T;
  const result = await response.json() as T;
  checkSession(token);
  return result;
}

export async function apiFetchBlob(path: string, init?: RequestInit): Promise<Blob> {
  const token = getToken();
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(path, { ...init, headers });
  checkSession(token);
  if (!response.ok) throw await errorFromResponse(response);
  const result = await response.blob();
  checkSession(token);
  return result;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError && Array.isArray(error.detail)) {
    const fields = error.detail.filter((item): item is { loc: unknown[]; msg: string } =>
      typeof item === "object" && item !== null && Array.isArray((item as { loc?: unknown }).loc) && typeof (item as { msg?: unknown }).msg === "string"
    );
    if (fields.length) return fields.map((item) => `${String(item.loc.at(-1) || "Field")}: ${item.msg}`).join("; ");
  }
  return error instanceof Error ? error.message : String(error);
}
