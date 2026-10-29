import { apiFetch } from "./client";
import type { ApiId } from "./client";

export type LotsRow = {
  test_id: ApiId; material_id: ApiId; material_code: string; material_desc: string | null; lastrina_code: string | null;
  request_date: string | null; prod_date: string | null; analysis_date: string | null;
  iso_code: string | null; iso_desc: string | null; iso_lot: string | null;
  pol_code: string | null; pol_desc: string | null; pol_lot: string | null;
  cat_code: string | null; cat_desc: string | null; cat_lot: string | null;
  add1_code: string | null; add1_desc: string | null; add1_lot: string | null;
  add2_code: string | null; add2_desc: string | null; add2_lot: string | null;
  durezza: string | null; carico_rottura: string | null; allungamento: string | null;
  lacerazione_ba: string | null; lacerazione_ca: string | null; abrasione: string | null;
  resistivita_superficiale: string | null;
};

export type LotsPage = { items: LotsRow[]; total: number; limit: number; offset: number; has_next: boolean };

export type ComponentLot = { code?: string | null; desc?: string | null; lot?: string | null };
export type LotDetails = { test_id: ApiId; material_id: ApiId; request_date: string | null; prod_date: string | null; analysis_date: string | null; components: Record<string, ComponentLot>; qc: Record<string, string | null> };
export type LotUpsert = { material_id: ApiId; request_date?: string | null; prod_date?: string | null; analysis_date?: string | null; components?: Record<string, ComponentLot>; qc?: Record<string, string | null> };

export type LotsDateField = "request_date" | "prod_date" | "analysis_date";
export type LotsStatus = "all" | "completed" | "awaiting_production" | "awaiting_analysis";
export type LotsSortKey = "latest" | LotsDateField | "material" | "lastrina" | "iso" | "pol" | "cat" | "add1" | "add2" | "durezza" | "carico_rottura" | "allungamento" | "lacerazione_ba" | "lacerazione_ca" | "abrasione" | "resistivita_superficiale";
export type LotsListOptions = {
  limit?: number; offset?: number; includeDeleted?: boolean; materialId?: ApiId; testId?: ApiId;
  q?: string; dateField?: LotsDateField; dateFrom?: string; dateTo?: string;
  status?: LotsStatus; sortBy?: LotsSortKey; sortDir?: "asc" | "desc";
  components?: Partial<Record<"iso" | "pol" | "cat" | "add1" | "add2", string>>;
  qcField?: QcSortKey; qcMin?: number; qcMax?: number;
};

type QcSortKey = "durezza" | "carico_rottura" | "allungamento" | "lacerazione_ba" | "lacerazione_ca" | "abrasione" | "resistivita_superficiale";

export function listLots(options: LotsListOptions = {}): Promise<LotsPage> {
  const query = new URLSearchParams({ limit: String(options.limit ?? 2000), offset: String(options.offset ?? 0) });
  if (options.includeDeleted) query.set("include_deleted", "true");
  if (options.materialId) query.set("material_id", options.materialId);
  if (options.testId) query.set("test_id", options.testId);
  if (options.q) query.set("q", options.q);
  if (options.dateField) query.set("date_field", options.dateField);
  if (options.dateFrom) query.set("date_from", options.dateFrom);
  if (options.dateTo) query.set("date_to", options.dateTo);
  if (options.status && options.status !== "all") query.set("status", options.status);
  if (options.sortBy) query.set("sort_by", options.sortBy);
  if (options.sortDir) query.set("sort_dir", options.sortDir);
  Object.entries(options.components || {}).forEach(([key, value]) => { if (value) query.set(key, value); });
  if (options.qcField) query.set("qc_field", options.qcField);
  if (options.qcMin != null) query.set("qc_min", String(options.qcMin));
  if (options.qcMax != null) query.set("qc_max", String(options.qcMax));
  return apiFetch(`/api/lots?${query.toString()}`);
}
export function getLotDetails(testId: ApiId): Promise<LotDetails> { return apiFetch(`/api/lots/${testId}`); }
export function createLot(payload: LotUpsert): Promise<LotDetails> { return apiFetch("/api/lots", { method: "POST", body: JSON.stringify(payload) }); }
export function updateLot(testId: ApiId, payload: LotUpsert): Promise<LotDetails> { return apiFetch(`/api/lots/${testId}`, { method: "PUT", body: JSON.stringify(payload) }); }
export async function deleteLot(testId: ApiId): Promise<void> { await apiFetch(`/api/lots/${testId}`, { method: "DELETE" }); }
