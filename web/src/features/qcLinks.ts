import type { ApiId } from "../api/client";

export function qcHref(page: "sinottico" | "lots" | "charts" | "ratings" | "calendar", selection: {
  materialId?: ApiId | null; testId?: ApiId | null; prodDate?: string | null; returnTo?: string | null;
}): string {
  const params = new URLSearchParams();
  if (selection.materialId) params.set("material_id", selection.materialId);
  if (selection.testId && (page === "lots" || page === "calendar")) params.set("test_id", selection.testId);
  if (page === "calendar" && selection.prodDate) params.set("month", selection.prodDate.slice(0, 7));
  if (page === "lots" && selection.returnTo) params.set("return_to", selection.returnTo);
  const query = params.toString();
  return `/${page}${query ? `?${query}` : ""}`;
}
