import { apiFetch } from "./client";
import type { ApiId } from "./client";

export type ChartsResponse = { material_id: ApiId; date_from: string | null; date_to: string | null; traces: { name: string; x: string[]; y: number[] }[] };
export type ChartsTolerancePct = { warn_pct: number | null; alarm_pct: number | null };
export type ChartsConfig = { tolerance_pct: ChartsTolerancePct; fixed_properties: [ApiId | null, string, string][]; defaults: Record<string, boolean> };
export type PanelTrace = { name: string; x: string[]; y: number[]; kind: string };
export type ChartPanel = { property_id: ApiId | null; title: string; unit?: string | null; traces: PanelTrace[] };
export type ChartsPanels = { material_id: ApiId; date_from: string | null; date_to: string | null; panels: ChartPanel[] };

export function charts(materialId: ApiId, dateFrom?: string, dateTo?: string): Promise<ChartsResponse> {
  const query = new URLSearchParams({ material_id: String(materialId) });
  if (dateFrom) query.set("date_from", dateFrom);
  if (dateTo) query.set("date_to", dateTo);
  return apiFetch(`/api/charts?${query.toString()}`);
}

export function chartsConfig(): Promise<ChartsConfig> { return apiFetch("/api/charts/config"); }

export function chartsPanels(args: { material_id: ApiId; date_from?: string; date_to?: string; smooth?: boolean; avg?: boolean; tolerances?: boolean }): Promise<ChartsPanels> {
  const query = new URLSearchParams({ material_id: String(args.material_id) });
  if (args.date_from) query.set("date_from", args.date_from);
  if (args.date_to) query.set("date_to", args.date_to);
  if (args.smooth != null) query.set("smooth", String(args.smooth));
  if (args.avg != null) query.set("avg", String(args.avg));
  if (args.tolerances != null) query.set("tolerances", String(args.tolerances));
  return apiFetch(`/api/charts/panels?${query.toString()}`);
}
