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

export function ThresholdsTab({ thresholds, busy, onSave }: { thresholds: Thresholds; busy: boolean; onSave: (t: Thresholds) => void }) {
  const [g, setG] = useState<number>(thresholds.green_days);
  const [y, setY] = useState<number>(thresholds.yellow_days);
  useEffect(() => {
    setG(thresholds.green_days);
    setY(thresholds.yellow_days);
  }, [thresholds.green_days, thresholds.yellow_days]);
  const invalid = !Number.isInteger(g) || !Number.isInteger(y) || g < 0 || y < g;

  return (
    <>
      <div className="muted" style={{ marginBottom: 10 }}>
        Green &lt;= {g} days, Yellow &lt;= {y} days, Red &gt; {y} days
      </div>
      <div className="row" style={{ marginBottom: 10 }}>
        <label>Green days <input className="input" type="number" min={0} step={1} required value={g} onChange={(e) => setG(Number(e.target.value))} disabled={busy} /></label>
        <label>Yellow days <input className="input" type="number" min={0} step={1} required aria-invalid={invalid} value={y} onChange={(e) => setY(Number(e.target.value))} disabled={busy} /></label>
        <button className="btn primary" disabled={busy || invalid} onClick={() => onSave({ green_days: g, yellow_days: y })}>
          Save
        </button>
      </div>
      {invalid && <p role="alert">Enter whole, non-negative days; yellow must be at least green.</p>}
    </>
  );
}
