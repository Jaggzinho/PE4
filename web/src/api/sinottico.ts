import { apiFetch, apiFetchBlob } from "./client";
import type { ApiId } from "./client";

export type SinotticoRow = {
  item_id: ApiId;
  machine_code: string | null;
  excel_code: string | null;
  description: string | null;
  material_id: ApiId | null;
  material_code: string | null;
  lastrina_code: string | null;
  last_request_date: string | null;
  days_since?: number | null;
  status_level?: string | null;
  status_color?: string | null;
  rating_percent?: number | null;
};

export type QueueRow = {
  item_id: ApiId;
  machine_code: string | null;
  material_code: string | null;
  description: string | null;
  lastrina_code: string | null;
  last_request_date: string | null;
};

export type EmailDraft = { to_list: string; cc_list: string; subject: string; body: string; is_html: boolean };
export type FinalizeQueueResult = { sample_requests_logged: number; tests_created: number };

export function listSinottico(): Promise<SinotticoRow[]> { return apiFetch("/api/sinottico"); }
export function listQueue(): Promise<QueueRow[]> { return apiFetch("/api/sinottico/queue"); }
export async function queueAdd(itemId: ApiId): Promise<void> { await apiFetch(`/api/sinottico/queue/items/${itemId}`, { method: "POST" }); }
export async function queueRemove(itemId: ApiId): Promise<void> { await apiFetch(`/api/sinottico/queue/items/${itemId}`, { method: "DELETE" }); }
export async function queueClear(): Promise<void> { await apiFetch("/api/sinottico/queue", { method: "DELETE" }); }
export function queueEmailPreview(): Promise<EmailDraft> { return apiFetch("/api/sinottico/queue/email-preview", { method: "POST" }); }
export function queueEmailEmlBlob(): Promise<Blob> { return apiFetchBlob("/api/sinottico/queue/email.eml", { method: "POST" }); }
export function queueFinalize(): Promise<FinalizeQueueResult> { return apiFetch("/api/sinottico/queue/finalize", { method: "POST" }); }
