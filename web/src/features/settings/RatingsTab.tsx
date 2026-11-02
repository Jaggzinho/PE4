import { useEffect, useMemo, useState } from "react";
import { settingsSetRatingRule, settingsSetRatingWeight, type RatingRow } from "../../api";
import type { TolerancePointsRule } from "../../api/settings";
import { modalFrame } from "../ModalFrame";

const pointFields = [
  ["warn_low_points", "Warn min"], ["warn_high_points", "Warn max"],
  ["alarm_low_points", "Alarm min"], ["alarm_high_points", "Alarm max"],
] as const;
type PointField = typeof pointFields[number][0];
type RuleDraft = { maxPoints: string } & Record<PointField, string>;

function defaultDraft(maxPoints = 20): RuleDraft {
  return { maxPoints: String(maxPoints), warn_low_points: String(maxPoints), warn_high_points: String(maxPoints), alarm_low_points: "0", alarm_high_points: "0" };
}

function loadRule(ruleJson: string | null): RuleDraft {
  if (!ruleJson) return defaultDraft();
  try {
    const value: unknown = JSON.parse(ruleJson);
    if (typeof value !== "object" || value === null || Array.isArray(value)) return defaultDraft();
    const rule = value as Record<string, unknown>;
    const max = rule.type === "ranges_v1" ? 100 : Number(rule.max_points);
    const draft = defaultDraft(Number.isFinite(max) && max > 0 ? max : 20);
    if (rule.type === "custom_tolerance_points_v1") {
      for (const [key] of pointFields) draft[key] = rule[key] == null ? "" : String(rule[key]);
    }
    return draft;
  } catch { return defaultDraft(); }
}

function serializeRule(draft: RuleDraft): { ruleJson: string; error: string } {
  const max = Number(draft.maxPoints);
  if (!draft.maxPoints.trim() || !Number.isFinite(max) || max <= 0 || max > 1_000_000) return { ruleJson: "", error: "Max points must be greater than 0 and at most 1,000,000." };
  const rule: TolerancePointsRule = { type: "custom_tolerance_points_v1", max_points: max, warn_low_points: 0, warn_high_points: 0, alarm_low_points: 0, alarm_high_points: 0 };
  for (const [key, label] of pointFields) {
    const points = Number(draft[key]);
    if (!draft[key].trim() || !Number.isFinite(points) || points < 0 || points > max) return { ruleJson: "", error: `${label} points must be between 0 and ${max}.` };
    rule[key] = points;
  }
  return { ruleJson: JSON.stringify(rule), error: "" };
}

function WeightField({ row, busy, onWork }: { row: RatingRow; busy: boolean; onWork: (fn: () => Promise<void>) => void }) {
  const [value, setValue] = useState(String(row.weight));
  useEffect(() => setValue(String(row.weight)), [row.weight]);
  const valid = value.trim() !== "" && Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 1_000_000;
  return <label><span className="sr-only">Weight for {row.property_name}</span><input className="input" style={{ minWidth: 120 }} type="number" min={0} max={1_000_000} step="0.1" value={value} disabled={busy} aria-invalid={!valid} onChange={(event) => setValue(event.target.value)} onBlur={() => { if (valid && Number(value) !== row.weight) onWork(async () => settingsSetRatingWeight(row.property_id, Number(value))); }} onKeyDown={(event) => { if (event.key === "Enter") event.currentTarget.blur(); }} /></label>;
}

function RuleEditor({ row, busy, onCancel, onSave }: { row: RatingRow; busy: boolean; onCancel: () => void; onSave: (ruleJson: string) => void }) {
  const [draft, setDraft] = useState<RuleDraft>(() => loadRule(row.rule_json));
  const result = useMemo(() => serializeRule(draft), [draft]);
  return <>
    <div className="row"><h3 style={{ margin: 0 }}>Rating rule - {row.property_name}</h3></div>
    <p className="muted">Points apply at the custom tolerance limits saved in Master Data. Material-specific limits take priority over property defaults. Scores interpolate linearly from Max points at the reference through the warning and alarm points. Beyond an alarm limit, the score is zero. A side without an alarm remains open at its last configured score.</p>
    <p className="muted">Set all four values equal to Max points to award full points throughout the alarm band, including its boundaries. Without custom limits, values within ±20% of the material average receive Max points; values outside receive zero.</p>
    <label className="row" style={{ gap: 8, marginBottom: 12 }}><span>Max points</span><input className="input" style={{ width: 140 }} type="number" min={0.01} max={1_000_000} step="any" value={draft.maxPoints} disabled={busy} onChange={(event) => setDraft((current) => ({ ...current, maxPoints: event.target.value }))} /></label>
    <table className="table"><thead><tr>{pointFields.map(([key, label]) => <th key={key}>{label}</th>)}</tr></thead><tbody><tr>
      {pointFields.map(([key, label]) => <td key={key}><label><span className="sr-only">{label} points</span><input className="input" style={{ width: "100%" }} type="number" min={0} max={Number(draft.maxPoints) || undefined} step="any" value={draft[key]} disabled={busy} onChange={(event) => setDraft((current) => ({ ...current, [key]: event.target.value }))} /></label></td>)}
    </tr></tbody></table>
    {result.error && <p role="alert" style={{ color: "var(--danger)" }}>{result.error}</p>}
    <div className="row" style={{ marginTop: 16 }}><div className="spacer" /><button className="btn" disabled={busy} onClick={() => setDraft(defaultDraft())}>Clear</button><button className="btn" disabled={busy} onClick={onCancel}>Cancel</button><button className="btn primary" disabled={busy || !!result.error} onClick={() => onSave(result.ruleJson)}>Save</button></div>
  </>;
}

export function RatingsTab({ rows, busy, onWork }: { rows: RatingRow[]; busy: boolean; onWork: (fn: () => Promise<void>) => void }) {
  const [edit, setEdit] = useState<RatingRow | null>(null);
  return <>
    <div className="muted" style={{ marginBottom: 10 }}>Rating points use the custom tolerance limits in Master Data. Without custom limits, the fallback awards full points within ±20% of the material average and zero outside. Property scores are combined using the weight; weight 0 excludes a property.</div>
    <div style={{ overflowX: "auto" }}><table className="table"><thead><tr><th>Property</th><th>Unit</th><th>Weight</th><th>Max points</th>{pointFields.map(([key, label]) => <th key={key}>{label}</th>)}<th /></tr></thead><tbody>
      {rows.map((r) => { const rule = loadRule(r.rule_json); return <tr key={r.property_id}><td>{r.property_name}</td><td>{r.unit || "—"}</td><td><WeightField row={r} busy={busy} onWork={onWork} /></td><td>{rule.maxPoints}</td>{pointFields.map(([key]) => <td key={key}>{rule[key]}</td>)}<td style={{ textAlign: "right", whiteSpace: "nowrap" }}><button className="btn" disabled={busy} onClick={() => setEdit(r)}>Edit…</button></td></tr>; })}
      {!rows.length && <tr><td colSpan={9} className="muted">No data</td></tr>}
    </tbody></table></div>
    {edit && modalFrame(<RuleEditor row={edit} busy={busy} onCancel={() => setEdit(null)} onSave={(ruleJson) => onWork(async () => { await settingsSetRatingRule(edit.property_id, ruleJson); setEdit(null); })} />, () => !busy && setEdit(null))}
  </>;
}
