import { useEffect, useMemo, useState } from "react";
import { settingsSetRatingRule, settingsSetRatingWeight, type RatingRow } from "../../api";
import { modalFrame } from "../ModalFrame";

type BandDraft = { id: number; maxPct: string; points: string };
type RuleDraft = { maxPoints: string; bands: BandDraft[] };
let nextBandId = 1;

function band(maxPct: unknown = "", points: unknown = ""): BandDraft {
  return { id: nextBandId++, maxPct: maxPct == null ? "" : String(maxPct), points: points == null ? "" : String(points) };
}

function numericOrDefault(value: unknown, fallback: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed === 0) return fallback;
  return Math.min(1_000_000, Math.max(1, Math.trunc(parsed)));
}

function objectValue(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value != null && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function loadRule(ruleJson: string | null): RuleDraft {
  if (!ruleJson) return { maxPoints: "20", bands: [band()] };
  let data: unknown;
  try { data = JSON.parse(ruleJson); } catch { return { maxPoints: "20", bands: [band()] }; }
  const rule = objectValue(data);
  if (rule.type === "ranges_v1") {
    const ranges = Array.isArray(rule.ranges) ? rule.ranges : [];
    return { maxPoints: "100", bands: ranges.length ? ranges.map((entry) => { const r = objectValue(entry); return band(r.max, r.score); }) : [band()] };
  }
  if (rule.type === "pct_from_avg_v1") {
    const ranges = Array.isArray(rule.ranges) ? rule.ranges : [];
    return { maxPoints: String(numericOrDefault(rule.max_points, 20)), bands: ranges.length ? ranges.map((entry) => { const r = objectValue(entry); return band(r.max, r.points); }) : [band()] };
  }
  if (rule.type === "pct_from_avg_bands_v1") {
    const bands = Array.isArray(rule.bands) ? rule.bands : [];
    return { maxPoints: String(numericOrDefault(rule.max_points, 20)), bands: bands.length ? bands.map((entry) => { const r = objectValue(entry); return band(r.max_pct, r.points); }) : [band()] };
  }
  return { maxPoints: "20", bands: [band()] };
}

function serializeRule(draft: RuleDraft): { ruleJson: string; error: string } {
  const maxPoints = Number(draft.maxPoints);
  if (!Number.isInteger(maxPoints) || maxPoints < 1 || maxPoints > 1_000_000) return { ruleJson: "", error: "Max points must be a whole number from 1 to 1,000,000." };
  if (!draft.bands.length) return { ruleJson: "", error: "Add at least one tolerance band." };
  const seenMax = new Set<number>();
  let catchAllCount = 0;
  const bands: { max_pct: number | null; points: number }[] = [];
  for (let index = 0; index < draft.bands.length; index += 1) {
    const item = draft.bands[index];
    const label = `Band ${index + 1}`;
    let maxPct: number | null = null;
    if (item.maxPct.trim() === "") {
      catchAllCount += 1;
      if (catchAllCount > 1) return { ruleJson: "", error: "Only one catch-all band may have an empty Max %." };
    } else {
      maxPct = Number(item.maxPct);
      if (!Number.isFinite(maxPct) || maxPct < 0) return { ruleJson: "", error: `${label} Max % must be zero or greater.` };
      if (seenMax.has(maxPct)) return { ruleJson: "", error: "Each Max % threshold must be unique." };
      seenMax.add(maxPct);
    }
    if (item.points.trim() === "") return { ruleJson: "", error: `${label} points are required.` };
    const rawPoints = Number(item.points);
    if (!Number.isFinite(rawPoints)) return { ruleJson: "", error: `${label} points must be a number.` };
    const points = Math.trunc(rawPoints);
    if (points < 0 || points > maxPoints) return { ruleJson: "", error: `${label} points must be between 0 and ${maxPoints}.` };
    bands.push({ max_pct: maxPct, points });
  }
  return { ruleJson: JSON.stringify({ type: "pct_from_avg_bands_v1", bands, max_points: maxPoints }), error: "" };
}

function WeightField({ row, busy, onWork }: { row: RatingRow; busy: boolean; onWork: (fn: () => Promise<void>) => void }) {
  const [value, setValue] = useState(String(row.weight));
  useEffect(() => setValue(String(row.weight)), [row.weight]);
  const valid = value.trim() !== "" && Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 1_000_000;
  return <label><span className="sr-only">Weight for {row.property_name}</span><input className="input" style={{ minWidth: 120 }} type="number" min={0} max={1_000_000} step="0.1" value={value} disabled={busy} aria-invalid={!valid} onChange={(event) => setValue(event.target.value)} onBlur={() => { if (valid && Number(value) !== row.weight) onWork(async () => settingsSetRatingWeight(row.property_id, Number(value))); }} onKeyDown={(event) => { if (event.key === "Enter") event.currentTarget.blur(); }} /></label>;
}

function RuleEditor({ row, busy, onCancel, onSave }: { row: RatingRow; busy: boolean; onCancel: () => void; onSave: (ruleJson: string) => void }) {
  const [draft, setDraft] = useState<RuleDraft>(() => loadRule(row.rule_json));
  const [selected, setSelected] = useState<number | null>(null);
  const result = useMemo(() => serializeRule(draft), [draft]);
  const changeBand = (id: number, field: "maxPct" | "points", value: string) => setDraft((current) => ({ ...current, bands: current.bands.map((item) => item.id === id ? { ...item, [field]: value } : item) }));
  const removeBand = () => {
    setDraft((current) => { const target = selected ?? current.bands.at(-1)?.id; return { ...current, bands: current.bands.filter((item) => item.id !== target) }; });
    setSelected(null);
  };
  return <>
    <div className="row"><h3 style={{ margin: 0 }}>Rating rule - {row.property_name}</h3></div>
    <p className="muted">Fallback rule when a material/property has no saved tolerance: define % distance-from-average bands → points. Leave Max % empty for the catch-all band.</p>
    <div className="row" style={{ justifyContent: "center", marginBottom: 12 }}><label className="row" style={{ gap: 8 }}><span>Max points</span><input className="input" style={{ width: 140 }} type="number" min={1} max={1_000_000} step={1} value={draft.maxPoints} disabled={busy} onChange={(event) => setDraft((current) => ({ ...current, maxPoints: event.target.value }))} /></label></div>
    <table className="table"><thead><tr><th>Max %</th><th>Points</th></tr></thead><tbody>
      {draft.bands.map((item, index) => <tr key={item.id} onClick={() => setSelected(item.id)} style={selected === item.id ? { background: "var(--table-row-alt)" } : undefined}>
        <td><label><span className="sr-only">Maximum percent for band {index + 1}</span><input className="input" style={{ width: "100%" }} type="number" min={0} step="any" placeholder="Catch-all" value={item.maxPct} disabled={busy} onFocus={() => setSelected(item.id)} onChange={(event) => changeBand(item.id, "maxPct", event.target.value)} /></label></td>
        <td><label><span className="sr-only">Points for band {index + 1}</span><input className="input" style={{ width: "100%" }} type="number" step="any" value={item.points} disabled={busy} onFocus={() => setSelected(item.id)} onChange={(event) => changeBand(item.id, "points", event.target.value)} /></label></td>
      </tr>)}
    </tbody></table>
    <div className="row" style={{ marginTop: 10 }}><button className="btn" disabled={busy} onClick={() => setDraft((current) => ({ ...current, bands: [...current.bands, band()] }))}>Add band</button><button className="btn" disabled={busy || !draft.bands.length} onClick={removeBand}>Remove band</button></div>
    {result.error && <p role="alert" style={{ color: "var(--danger)" }}>{result.error}</p>}
    <div className="row" style={{ marginTop: 16 }}><div className="spacer" /><button className="btn" disabled={busy} onClick={() => { setDraft({ maxPoints: "20", bands: [band()] }); setSelected(null); }}>Clear</button><button className="btn" disabled={busy} onClick={onCancel}>Cancel</button><button className="btn primary" disabled={busy || !!result.error} onClick={() => onSave(result.ruleJson)}>Save</button></div>
  </>;
}

export function RatingsTab({ rows, busy, onWork }: { rows: RatingRow[]; busy: boolean; onWork: (fn: () => Promise<void>) => void }) {
  const [edit, setEdit] = useState<RatingRow | null>(null);
  return <>
    <div className="muted" style={{ marginBottom: 10 }}>Saved tolerances score 100% within warning limits and decline to 0% at alarm limits. Without a warning limit, the decline starts at the reference. Where no saved limit applies, the rating rule uses % distance from the material average. Property scores are combined using the weight.</div>
    <table className="table"><thead><tr><th>Property</th><th>Unit</th><th>Weight</th><th>Rule</th><th /></tr></thead><tbody>
      {rows.map((r) => <tr key={r.property_id}><td>{r.property_name}</td><td>{r.unit || "—"}</td><td><WeightField row={r} busy={busy} onWork={onWork} /></td><td>{r.rule_json ? "Set" : "—"}</td><td style={{ textAlign: "right", whiteSpace: "nowrap" }}><button className="btn" disabled={busy} onClick={() => setEdit(r)}>Edit…</button></td></tr>)}
      {!rows.length && <tr><td colSpan={5} className="muted">No data</td></tr>}
    </tbody></table>
    {edit && modalFrame(<RuleEditor row={edit} busy={busy} onCancel={() => setEdit(null)} onSave={(ruleJson) => onWork(async () => { await settingsSetRatingRule(edit.property_id, ruleJson); setEdit(null); })} />, () => !busy && setEdit(null))}
  </>;
}
