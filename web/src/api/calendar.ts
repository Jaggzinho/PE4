import { apiFetch } from "./client";
import type { ApiId } from "./client";

export type CalendarItem = { test_id: ApiId; material_id: ApiId; material_code: string; material_desc: string | null; lastrina_code: string | null; prod_date: string; rating_percent: number | null };
export type CalendarMonth = { year: number; month: number; date_from: string; date_to: string; items: CalendarItem[] };
export type QcFailureReport = { test_id: ApiId; material_code: string; request_date: string | null; failures: { property_name: string; actual_value: string }[] };

export function calendarMonth(year: number, month: number): Promise<CalendarMonth> {
  const query = new URLSearchParams({ year: String(year), month: String(month) });
  return apiFetch(`/api/calendar?${query.toString()}`);
}

export function calendarFailures(testId: ApiId): Promise<QcFailureReport> {
  return apiFetch(`/api/calendar/tests/${testId}/failures`);
}
