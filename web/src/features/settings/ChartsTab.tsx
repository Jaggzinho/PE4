import { useEffect, useMemo, useState } from "react";
import {
  settingsCreateUser,
  settingsDeleteRole,
  settingsDeleteUser,
  settingsGetChartsTolerancePct,
  settingsGetThresholds,
  settingsListRatings,
  settingsListRoles,
  settingsListUsers,
  settingsResetPassword,
  settingsSetChartsTolerancePct,
  settingsSetRatingRule,
  settingsSetRatingWeight,
  settingsSetThresholds,
  settingsUpdateUser,
  settingsUpsertRole,
  type ChartsTolerancePct,
  type RatingRow,
  type Role,
  type Thresholds,
  type User,
} from "../../api";
import { modalFrame } from "../ModalFrame";

export function ChartsTab({ value, busy, onSave }: { value: ChartsTolerancePct; busy: boolean; onSave: (v: ChartsTolerancePct) => void }) {
  const [warn, setWarn] = useState<string>(value.warn_pct == null ? "" : String(value.warn_pct));
  const [alarm, setAlarm] = useState<string>(value.alarm_pct == null ? "" : String(value.alarm_pct));
  useEffect(() => {
    setWarn(value.warn_pct == null ? "" : String(value.warn_pct));
    setAlarm(value.alarm_pct == null ? "" : String(value.alarm_pct));
  }, [value.warn_pct, value.alarm_pct]);

  function toNumOrNull(s: string): number | null {
    const t = s.trim();
    if (!t) return null;
    const n = Number(t);
    return Number.isFinite(n) ? n : null;
  }
  const invalid = [warn, alarm].some((text) => text.trim() !== "" && (!Number.isFinite(Number(text)) || Number(text) < 0));

  return (
    <>
      <div className="muted" style={{ marginBottom: 10 }}>
        Fallback tolerance bands as ±% of average when no explicit tolerances are configured.
      </div>
      <div className="row" style={{ marginBottom: 10 }}>
        <label>Warn % <input className="input" type="number" min={0} step="any" value={warn} onChange={(e) => setWarn(e.target.value)} disabled={busy} aria-invalid={invalid} /></label>
        <label>Alarm % <input className="input" type="number" min={0} step="any" value={alarm} onChange={(e) => setAlarm(e.target.value)} disabled={busy} aria-invalid={invalid} /></label>
        <button className="btn primary" disabled={busy || invalid} onClick={() => onSave({ warn_pct: toNumOrNull(warn), alarm_pct: toNumOrNull(alarm) })}>
          Save
        </button>
      </div>
      {invalid && <p role="alert">Enter non-negative finite percentages, or leave both fields blank.</p>}
    </>
  );
}
