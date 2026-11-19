import { useEffect } from "react";
import { comparisonStorageKey, useMaterialSelection } from "./useMaterialSelection";
import type { Material } from "../api";

export function useComparison() {
  const selection = useMaterialSelection(true);
  const { materialId, searchParams, setSearchParams } = selection;
  const extras = materialId ? [...new Set(searchParams.getAll("compare_material_id")
    .filter(id => /^[1-9]\d*$/.test(id) && id !== materialId))].slice(0, 3) : [];
  const ids = materialId ? [materialId, ...extras] : [];
  const comparing = extras.length > 0;
  const storageKey = comparisonStorageKey();

  useEffect(() => {
    if (comparing) sessionStorage.setItem(storageKey, searchParams.toString());
  }, [comparing, searchParams, storageKey]);

  function update(primary: string, compared: string[], initialTo?: string) {
    const next = new URLSearchParams(searchParams);
    next.set("material_id", primary);
    next.delete("compare_material_id");
    if (primary) compared.filter(id => id !== primary).forEach(id => next.append("compare_material_id", id));
    if (initialTo && !next.has("date_to")) next.set("date_to", initialTo);
    if (comparing && !next.has("compare_material_id")) sessionStorage.removeItem(storageKey);
    setSearchParams(next);
  }
  function link(page: "charts" | "ratings", defaultTo?: string) {
    const next = new URLSearchParams(searchParams);
    if (defaultTo && !next.has("date_to")) next.set("date_to", defaultTo);
    return `/${page}?${next}`;
  }
  return { ...selection, extras, ids, comparing, update, link };
}

export const materialColors = ["#4f86ff", "#db7034", "#219474", "#ba62ce"];
export function materialCode(materials: Material[], id: string) {
  return materials.find(item => String(item.material_id) === id)?.code ?? `Material ${id}`;
}

export function materialDescription(materials: Material[], id: string) {
  return materials.find(item => String(item.material_id) === id)?.description?.trim()
    || materialCode(materials, id);
}

export function ComparisonControls({ selection, materials, initialTo }: {
  selection: ReturnType<typeof useComparison>; materials: Material[]; initialTo?: string;
}) {
  const { materialId, extras, ids, update } = selection;
  const available = materials.filter(m => m.active && !ids.includes(String(m.material_id)));
  if (!materialId) return null;
  return <>
    <select className="input" aria-label="Add material to compare" value=""
      disabled={ids.length >= 4 || !available.length}
      onChange={event => update(materialId, [...extras, event.target.value], initialTo)}>
      <option value="">Add material to compare</option>
      {available.map(m => <option key={m.material_id} value={m.material_id}>{m.code}{m.description ? ` — ${m.description}` : ""}</option>)}
    </select>
    {extras.map(id => <button type="button" className="btn" key={id}
      aria-label={`Remove ${materialDescription(materials, id)} from comparison`}
      onClick={() => update(materialId, extras.filter(extra => extra !== id))}>
      {materialDescription(materials, id)} ×
    </button>)}
  </>;
}

export function ComparisonLegend({ items, materials, hidden, toggle }: {
  items: { id: string; color: string }[]; materials: Material[]; hidden: Set<string>; toggle: (id: string) => void;
}) {
  if (!items.length) return null;
  return <div role="group" aria-label="Material legend" className="row" style={{ justifyContent: "center", marginTop: 10 }}>
    {items.map(({ id, color }) => <button type="button" className="btn" key={id}
      aria-pressed={!hidden.has(id)} onClick={() => toggle(id)}>
      <span aria-hidden="true" style={{ display: "inline-block", width: 24, borderTop: `3px solid ${color}`, verticalAlign: "middle", marginRight: 6 }} />
      {materialDescription(materials, id)}
    </button>)}
  </div>;
}

export function toggleMaterial(current: Set<string>, id: string) {
  const next = new Set(current);
  if (!next.delete(id)) next.add(id);
  return next;
}
