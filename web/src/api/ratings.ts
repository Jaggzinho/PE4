import { apiFetch } from "./client";
import type { ApiId } from "./client";

export type RatingPoint = { date: string; rating_percent: number };
export type RatingOverview = {
  material_id: ApiId; configured: boolean; date_min: string | null; date_max: string | null;
  date_from: string | null; date_to: string | null; points: RatingPoint[];
  latest_rating: number | null; average_rating: number | null;
};

export function ratingsOverview(materialId: ApiId, dateFrom?: string, dateTo?: string): Promise<RatingOverview> {
  const query = new URLSearchParams({ material_id: String(materialId) });
  if (dateFrom) query.set("date_from", dateFrom);
  if (dateTo) query.set("date_to", dateTo);
  return apiFetch(`/api/ratings?${query.toString()}`);
}
