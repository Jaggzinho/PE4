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
import { confirmDelete } from "../confirmAction";

export function RolesTab({ rows, busy, onWork }: { rows: Role[]; busy: boolean; onWork: (fn: () => Promise<void>) => void }) {
  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState<Role | null>(null);
  const [f, setF] = useState<Omit<Role, "role_id">>({
    name: "",
    can_edit_master: false,
    can_edit_tests: false,
    can_manage_users: false,
    can_send_outlook: false,
  });

  function startNew() {
    setEdit(null);
    setF({ name: "", can_edit_master: false, can_edit_tests: false, can_manage_users: false, can_send_outlook: false });
    setOpen(true);
  }
  function startEdit(r: Role) {
    setEdit(r);
    setF({
      name: r.name,
      can_edit_master: r.can_edit_master,
      can_edit_tests: r.can_edit_tests,
      can_manage_users: r.can_manage_users,
      can_send_outlook: r.can_send_outlook,
    });
    setOpen(true);
  }

  return (
    <>
      <div className="row" style={{ marginBottom: 10 }}>
        <button className="btn primary" onClick={startNew} disabled={busy}>
          Add
        </button>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Master</th>
            <th>Tests</th>
            <th>Users</th>
            <th>Outlook</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.role_id}>
              <td>{r.name}</td>
              <td>{r.can_edit_master ? "Y" : "—"}</td>
              <td>{r.can_edit_tests ? "Y" : "—"}</td>
              <td>{r.can_manage_users ? "Y" : "—"}</td>
              <td>{r.can_send_outlook ? "Y" : "—"}</td>
              <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                <button className="btn" disabled={busy} onClick={() => startEdit(r)}>
                  Edit
                </button>{" "}
                <button className="btn danger" disabled={busy} onClick={() => confirmDelete("role", r.name) && onWork(async () => settingsDeleteRole(r.role_id))}>
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
              <div style={{ fontWeight: 700 }}>{edit ? `Edit ${edit.name}` : "New role"}</div>
              <div className="spacer" />
              <button className="btn" disabled={busy} onClick={() => setOpen(false)}>
                Close
              </button>
              <button
                className="btn primary"
                disabled={busy || !f.name.trim()}
                onClick={() =>
                  onWork(async () => {
                    await settingsUpsertRole(edit ? edit.role_id : null, f);
                    setOpen(false);
                  })
                }
              >
                Save
              </button>
            </div>
            <div className="row">
              <input className="input" aria-label="Role name" required placeholder="Role name" value={f.name} onChange={(e) => setF((p) => ({ ...p, name: e.target.value }))} />
              {(
                [
                  ["can_edit_master", "Edit Master"],
                  ["can_edit_tests", "Edit Tests"],
                  ["can_manage_users", "Manage Users"],
                  ["can_send_outlook", "Send Outlook"],
                ] as const
              ).map(([k, label]) => (
                <label key={k} className="pill" style={{ cursor: "pointer" }}>
                  <input type="checkbox" checked={!!(f as any)[k]} onChange={(e) => setF((p) => ({ ...p, [k]: e.target.checked } as any))} /> {label}
                </label>
              ))}
            </div>
          </>,
          () => !busy && setOpen(false),
        )}
    </>
  );
}
