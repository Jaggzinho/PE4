import { apiFetch, apiFetchBlob } from "./client";
import type { ApiId } from "./client";
import type { ChartsTolerancePct } from "./charts";

export type Thresholds = { green_days: number; yellow_days: number };
export type RatingRow = { property_id: ApiId; property_name: string; unit: string | null; weight: number; rule_json: string | null };
export type Role = { role_id: ApiId; name: string; can_edit_master: boolean; can_edit_tests: boolean; can_manage_users: boolean; can_send_outlook: boolean };
export type User = { user_id: ApiId; username: string; role_id: ApiId; role_name: string; active: boolean; created_at: string; last_login_at: string | null };
export type DatabaseSource = { active_path: string; active_source: string; configured_next_path: string | null; restart_required: boolean; override_active: boolean };
export function settingsGetDatabaseSource(): Promise<DatabaseSource> { return apiFetch("/api/settings/database-source"); }
export function settingsSetDatabaseSource(path: string): Promise<DatabaseSource> { return apiFetch("/api/settings/database-source", { method: "PUT", body: JSON.stringify({ path }) }); }

export function settingsCreateOutlookTestDraft(): Promise<{ message: string }> { return apiFetch("/api/settings/outlook/test-draft", { method: "POST" }); }
export function settingsDownloadOutlookTestEml(): Promise<Blob> { return apiFetchBlob("/api/settings/outlook/test-draft.eml"); }

export function settingsGetThresholds(): Promise<Thresholds> { return apiFetch("/api/settings/thresholds"); }
export function settingsSetThresholds(payload: Thresholds): Promise<Thresholds> { return apiFetch("/api/settings/thresholds", { method: "PUT", body: JSON.stringify(payload) }); }
export function settingsGetChartsTolerancePct(): Promise<ChartsTolerancePct> { return apiFetch("/api/settings/charts-tolerance-pct"); }
export function settingsSetChartsTolerancePct(payload: ChartsTolerancePct): Promise<ChartsTolerancePct> { return apiFetch("/api/settings/charts-tolerance-pct", { method: "PUT", body: JSON.stringify(payload) }); }
export function settingsListRatings(): Promise<RatingRow[]> { return apiFetch("/api/settings/ratings"); }
export async function settingsSetRatingWeight(propertyId: ApiId, weight: number): Promise<void> { await apiFetch(`/api/settings/ratings/${propertyId}/weight`, { method: "PUT", body: JSON.stringify({ weight }) }); }
export async function settingsSetRatingRule(propertyId: ApiId, rule_json: string): Promise<void> { await apiFetch(`/api/settings/ratings/${propertyId}/rule`, { method: "PUT", body: JSON.stringify({ rule_json }) }); }
export function settingsListRoles(): Promise<Role[]> { return apiFetch("/api/settings/roles"); }
export function settingsUpsertRole(id: ApiId | null, payload: Omit<Role, "role_id">): Promise<Role> { return apiFetch(id == null ? "/api/settings/roles" : `/api/settings/roles/${id}`, { method: id == null ? "POST" : "PUT", body: JSON.stringify(payload) }); }
export async function settingsDeleteRole(id: ApiId): Promise<void> { await apiFetch(`/api/settings/roles/${id}`, { method: "DELETE" }); }
export function settingsListUsers(): Promise<User[]> { return apiFetch("/api/settings/users"); }
export function settingsCreateUser(payload: { username: string; password: string; role_id: ApiId; active: boolean }): Promise<User> { return apiFetch("/api/settings/users", { method: "POST", body: JSON.stringify(payload) }); }
export function settingsUpdateUser(id: ApiId, payload: { role_id: ApiId; active: boolean }): Promise<User> { return apiFetch(`/api/settings/users/${id}`, { method: "PUT", body: JSON.stringify(payload) }); }
export async function settingsResetPassword(id: ApiId, newPassword: string): Promise<void> { await apiFetch(`/api/settings/users/${id}/reset-password`, { method: "POST", body: JSON.stringify({ new_password: newPassword }) }); }
export async function settingsDeleteUser(id: ApiId): Promise<void> { await apiFetch(`/api/settings/users/${id}`, { method: "DELETE" }); }
