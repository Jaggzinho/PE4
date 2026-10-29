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
  type ApiId,
  type RatingRow,
  type Role,
  type Thresholds,
  type User,
} from "../../api";
import { modalFrame } from "../ModalFrame";
import { confirmDelete } from "../confirmAction";

export function UsersTab({
  rows,
  roles,
  busy,
  onWork,
}: {
  rows: User[];
  roles: Role[];
  busy: boolean;
  onWork: (fn: () => Promise<void>) => void;
}) {
  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState<User | null>(null);
  const [f, setF] = useState<{ username: string; password: string; role_id: ApiId; active: boolean }>({
    username: "",
    password: "",
    role_id: roles[0]?.role_id || "",
    active: true,
  });

  function startNew() {
    setEdit(null);
    setF({ username: "", password: "", role_id: roles[0]?.role_id || "", active: true });
    setOpen(true);
  }
  function startEdit(r: User) {
    setEdit(r);
    setF({ username: r.username, password: "", role_id: r.role_id, active: r.active });
    setOpen(true);
  }

  return (
    <>
      <div className="row" style={{ marginBottom: 10 }}>
        <button className="btn primary" onClick={startNew} disabled={busy || !roles.length}>
          Add
        </button>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th>Username</th>
            <th>Role</th>
            <th>Active</th>
            <th>Created</th>
            <th>Last login</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.user_id}>
              <td>{r.username}</td>
              <td>{r.role_name}</td>
              <td>{r.active ? "Yes" : "No"}</td>
              <td>{r.created_at ? String(r.created_at).slice(0, 19).replace("T", " ") : "—"}</td>
              <td>{r.last_login_at ? String(r.last_login_at).slice(0, 19).replace("T", " ") : "—"}</td>
              <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                <button className="btn" disabled={busy} onClick={() => startEdit(r)}>
                  Edit
                </button>{" "}
                <button
                  className="btn"
                  disabled={busy}
                  onClick={() =>
                    onWork(async () => {
                      const pw = prompt(`Reset password for ${r.username}:`);
                      if (!pw) return;
                      await settingsResetPassword(r.user_id, pw);
                    })
                  }
                >
                  Reset PW
                </button>{" "}
                <button className="btn danger" disabled={busy} onClick={() => confirmDelete("user", r.username) && onWork(async () => settingsDeleteUser(r.user_id))}>
                  Delete
                </button>
              </td>
            </tr>
          ))}
          {!rows.length && (
            <tr>
              <td colSpan={6} className="muted">
                No data
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {open &&
        modalFrame(
          <>
            <div className="row" style={{ marginBottom: 10 }}>
              <div style={{ fontWeight: 700 }}>{edit ? `Edit ${edit.username}` : "New user"}</div>
              <div className="spacer" />
              <button className="btn" disabled={busy} onClick={() => setOpen(false)}>
                Close
              </button>
              <button
                className="btn primary"
                disabled={busy || !f.role_id || !f.username.trim() || (!edit && !f.password.trim())}
                onClick={() =>
                  onWork(async () => {
                    if (edit) {
                      await settingsUpdateUser(edit.user_id, { role_id: f.role_id, active: f.active });
                    } else {
                      await settingsCreateUser({ username: f.username, password: f.password, role_id: f.role_id, active: f.active });
                    }
                    setOpen(false);
                  })
                }
              >
                Save
              </button>
            </div>
            <div className="row">
              <input className="input" aria-label="Username" required placeholder="Username" value={f.username} onChange={(e) => setF((p) => ({ ...p, username: e.target.value }))} disabled={!!edit} />
              <input className="input" aria-label="Password" required={!edit} placeholder={edit ? "(password unchanged)" : "Password"} type="password" value={f.password} onChange={(e) => setF((p) => ({ ...p, password: e.target.value }))} disabled={!!edit} />
              <select className="input" aria-label="User role" required value={f.role_id} onChange={(e) => setF((p) => ({ ...p, role_id: e.target.value }))}>
                <option value="">Select role…</option>
                {roles.map((r) => (
                  <option key={r.role_id} value={r.role_id}>
                    {r.name}
                  </option>
                ))}
              </select>
              <label className="pill" style={{ cursor: "pointer" }}>
                <input type="checkbox" checked={!!f.active} onChange={(e) => setF((p) => ({ ...p, active: e.target.checked }))} /> Active
              </label>
            </div>
            {edit && <div className="muted" style={{ marginTop: 10 }}>Use “Reset PW” from the table to change passwords.</div>}
          </>,
          () => !busy && setOpen(false),
        )}
    </>
  );
}
