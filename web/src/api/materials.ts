import { apiFetch } from "./client";
import type { ApiId } from "./client";

export type Material = {
  material_id: ApiId;
  code: string;
  description: string | null;
  lastrina_code: string | null;
  lastrina_desc: string | null;
  active: boolean;
  component_defaults: Partial<Record<"ISO" | "POL" | "CAT" | "ADD1" | "ADD2" | "ADD3" | "ADD4" | "EXT", {
    code: string | null;
    desc: string | null;
  }>>;
};

export function searchMaterials(query: string): Promise<Material[]> {
  const url = query.trim() ? `/api/materials?q=${encodeURIComponent(query.trim())}` : "/api/materials";
  return apiFetch(url);
}
