import { useMemo, useState } from "react";
import { mdDeleteTolerance, mdUpsertTolerance, type Material, type Property, type Tolerance, type ToleranceBound, type ToleranceMode, type ToleranceUpsert } from "../../api";
import { modalFrame } from "../ModalFrame";
import { confirmDelete } from "../confirmAction";

const bounds: ToleranceBound[] = ["warn_low", "warn_high", "alarm_low", "alarm_high"];
type Draft = { property: string; material: string; reference: string; values: Record<ToleranceBound, string>; modes: Record<ToleranceBound, ToleranceMode> };
const empty = (property = ""): Draft => ({ property, material: "", reference: "", values: { warn_low: "", warn_high: "", alarm_low: "", alarm_high: "" }, modes: { warn_low: "absolute", warn_high: "absolute", alarm_low: "absolute", alarm_high: "absolute" } });
const number = (text: string) => text.trim() ? Number(text) : null;

function resolve(draft: Draft) {
  const reference = number(draft.reference);
  const effective = {} as Record<ToleranceBound, number | null>;
  let error: string | null = !draft.property ? "Select a property." : null;
  if (reference !== null && !Number.isFinite(reference)) error = "Reference must be finite.";
  const payload = { property_id: draft.property, material_id: draft.material || null, reference_value: reference,
    warn_low_input: number(draft.values.warn_low), warn_low_mode: draft.modes.warn_low,
    warn_high_input: number(draft.values.warn_high), warn_high_mode: draft.modes.warn_high,
    alarm_low_input: number(draft.values.alarm_low), alarm_low_mode: draft.modes.alarm_low,
    alarm_high_input: number(draft.values.alarm_high), alarm_high_mode: draft.modes.alarm_high } satisfies ToleranceUpsert;
  for (const bound of bounds) {
    const value = payload[`${bound}_input`];
    if (value !== null && !Number.isFinite(value)) error = "Tolerance values must be finite.";
    if (value !== null && draft.modes[bound] === "percent") {
      if (reference === null || reference === 0) error = "A nonzero reference is required for percentage tolerances.";
      if (value < 0) error = "Percentage deviations must be nonnegative.";
      const delta = reference === null ? 0 : Math.abs(reference) * value / 100;
      effective[bound] = reference === null ? null : bound.endsWith("low") ? reference - delta : reference + delta;
    } else effective[bound] = value;
  }
  if (bounds.every((bound) => effective[bound] === null)) error = "Enter at least one limit.";
  for (const [low, high] of [["warn_low", "warn_high"], ["alarm_low", "alarm_high"]] as const)
    if (effective[low] !== null && effective[high] !== null && effective[low] > effective[high]) error = "Minimum must not exceed maximum.";
  if (effective.warn_low !== null && effective.alarm_low !== null && effective.warn_low < effective.alarm_low) error = "Warning minimum must be inside the alarm limits.";
  if (effective.warn_high !== null && effective.alarm_high !== null && effective.warn_high > effective.alarm_high) error = "Warning maximum must be inside the alarm limits.";
  if (reference !== null && bounds.some((bound) => effective[bound] !== null && (bound.endsWith("low") ? effective[bound] > reference : effective[bound] < reference))) error = "Reference must be within the configured limits.";
  return { payload, effective, error };
}

export function TolerancesTab({ rows, materials, properties, busy, onWork }: {
  rows: Tolerance[]; materials: Material[]; properties: Property[]; busy: boolean; onWork: (fn: () => Promise<void>) => void;
}) {
  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState<Tolerance | null>(null);
  const [draft, setDraft] = useState<Draft>(empty());
  const props = useMemo(() => properties.slice().sort((a, b) => a.name.localeCompare(b.name)), [properties]);
  const mats = useMemo(() => materials.slice().sort((a, b) => a.code.localeCompare(b.code)), [materials]);
  const propName = Object.fromEntries(properties.map((p) => [p.property_id, p.name]));
  const matName = Object.fromEntries(materials.map((m) => [m.material_id, m.code]));
  const result = resolve(draft);
  const unchangedKey = edit && String(edit.property_id) === draft.property && String(edit.material_id ?? "") === draft.material;
  const sameKey = rows.filter((r) => r.tolerance_id !== edit?.tolerance_id && String(r.property_id) === draft.property && String(r.material_id ?? "") === draft.material);
  const duplicate = !unchangedKey && sameKey.some((r) => r.is_custom);
  const replacingFallback = !edit && sameKey.length > 0 && !duplicate;
  const error = duplicate ? "A tolerance already exists for this material and property." : result.error;

  function startEdit(row: Tolerance) {
    setEdit(row);
    setDraft({ property: String(row.property_id), material: String(row.material_id ?? ""), reference: String(row.reference_value ?? ""),
      values: Object.fromEntries(bounds.map((b) => [b, String(row[`${b}_input`] ?? row[b] ?? "")])) as Record<ToleranceBound, string>,
      modes: Object.fromEntries(bounds.map((b) => [b, row[`${b}_mode`] || "absolute"])) as Record<ToleranceBound, ToleranceMode> });
    setOpen(true);
  }

  return <>
    <div className="row" style={{ marginBottom: 10 }}><button className="btn primary" disabled={busy || !props.length} onClick={() => { setEdit(null); setDraft(empty(String(props[0]?.property_id ?? ""))); setOpen(true); }}>Add</button></div>
    <table className="table"><thead><tr><th>Property</th><th>Material</th><th>Source</th><th>Reference</th><th>Warn min</th><th>Warn max</th><th>Alarm min</th><th>Alarm max</th><th /></tr></thead>
      <tbody>{rows.map((r) => <tr key={r.tolerance_id}>
        <td>{propName[r.property_id] || String(r.property_id)}</td><td>{r.material_id == null ? "(Default)" : matName[r.material_id] || String(r.material_id)}</td><td>{r.is_custom ? "Custom" : "Legacy/fallback"}</td><td>{r.reference_value ?? "—"}</td>
        {bounds.map((b) => <td key={b}>{r[b] ?? "—"}{r[`${b}_mode`] === "percent" && r[`${b}_input`] != null ? ` (${r[`${b}_input`]}%)` : ""}</td>)}
        <td style={{ textAlign: "right", whiteSpace: "nowrap" }}><button className="btn" disabled={busy} onClick={() => startEdit(r)}>Edit</button>{" "}
          <button className="btn danger" disabled={busy} onClick={() => confirmDelete("tolerance", String(r.tolerance_id)) && onWork(async () => mdDeleteTolerance(r.tolerance_id))}>Delete</button></td>
      </tr>)}{!rows.length && <tr><td colSpan={9} className="muted">No data</td></tr>}</tbody></table>
    {open && modalFrame(<form onSubmit={(e) => { e.preventDefault(); if (error || busy) return; onWork(async () => { await mdUpsertTolerance(edit?.tolerance_id ?? null, result.payload); setOpen(false); }); }}>
      <div className="row" style={{ marginBottom: 10 }}><strong>{edit ? `Edit tolerance ${edit.tolerance_id}` : "New tolerance"}</strong><div className="spacer" />
        <button type="button" className="btn" disabled={busy} onClick={() => setOpen(false)}>Close</button><button type="submit" className="btn primary" disabled={busy || !!error}>Save</button></div>
      <div className="row">
        <label>Property <select className="input" required value={draft.property} onChange={(e) => setDraft((d) => ({ ...d, property: e.target.value }))}><option value="">Select property…</option>{props.map((p) => <option key={p.property_id} value={p.property_id}>{p.name}</option>)}</select></label>
        <label>Material <select className="input" value={draft.material} onChange={(e) => setDraft((d) => ({ ...d, material: e.target.value }))}><option value="">(Default)</option>{mats.map((m) => <option key={m.material_id} value={m.material_id}>{m.code}</option>)}</select></label>
        <label>Reference value <input className="input" type="number" step="any" value={draft.reference} onChange={(e) => setDraft((d) => ({ ...d, reference: e.target.value }))} /></label>
      </div>
      <div className="row" style={{ marginTop: 10 }}>{bounds.map((b) => <label key={b}>{b.replace("_", " ")}
        <input className="input" type="number" aria-label={b.replace("_", " ")} step="any" min={draft.modes[b] === "percent" ? 0 : undefined} value={draft.values[b]} onChange={(e) => setDraft((d) => ({ ...d, values: { ...d.values, [b]: e.target.value } }))} />
        <select className="input" aria-label={`${b.replace("_", " ")} unit`} value={draft.modes[b]} onChange={(e) => setDraft((d) => ({ ...d, modes: { ...d.modes, [b]: e.target.value as ToleranceMode } }))}>
          <option value="absolute">Numeric limit</option><option value="percent">% from reference</option></select>
        {result.effective[b] != null && <small className="muted">Effective: {result.effective[b]}</small>}
      </label>)}</div>{replacingFallback && <p className="muted">Saving will replace the existing fallback for this material and property.</p>}{error && <p role="alert">{error}</p>}
    </form>, () => !busy && setOpen(false))}
  </>;
}
