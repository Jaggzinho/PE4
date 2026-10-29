import { useEffect, useMemo, useState } from "react";
import {
  mdDeleteComponent,
  mdDeleteComponentType,
  mdDeleteContact,
  mdDeleteMaterial,
  mdDeleteProperty,
  mdDeleteTolerance,
  mdDeleteTemplate,
  mdListComponentTypes,
  mdListComponents,
  mdListContacts,
  mdListMaterials,
  mdListProperties,
  mdListTolerances,
  mdListTemplates,
  mdUpsertComponent,
  mdUpsertComponentType,
  mdUpsertContact,
  mdUpsertMaterial,
  mdUpsertProperty,
  mdUpsertTolerance,
  mdUpsertTemplate,
  type Component,
  type ComponentType,
  type Contact,
  type EmailTemplate,
  type Material,
  type Property,
  type Tolerance,
} from "../../api";
import { modalFrame } from "../ModalFrame";
import { confirmDelete } from "../confirmAction";

export function ContactsTab({ rows, busy, onWork }: { rows: Contact[]; busy: boolean; onWork: (fn: () => Promise<void>) => void }) {
  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState<Contact | null>(null);
  const [f, setF] = useState<Omit<Contact, "contact_id">>({ name: "", email: "", group_name: "", active: true });
  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(f.email.trim());

  function startNew() {
    setEdit(null);
    setF({ name: "", email: "", group_name: "", active: true });
    setOpen(true);
  }
  function startEdit(r: Contact) {
    setEdit(r);
    setF({ name: r.name, email: r.email, group_name: r.group_name, active: r.active });
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
            <th>Group</th>
            <th>Email</th>
            <th>Name</th>
            <th>Active</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.contact_id}>
              <td>{r.group_name}</td>
              <td>{r.email}</td>
              <td>{r.name || "—"}</td>
              <td>{r.active ? "Yes" : "No"}</td>
              <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                <button className="btn" disabled={busy} onClick={() => startEdit(r)}>
                  Edit
                </button>{" "}
                <button className="btn danger" disabled={busy} onClick={() => confirmDelete("contact", r.email) && onWork(async () => mdDeleteContact(r.contact_id))}>
                  Delete
                </button>
              </td>
            </tr>
          ))}
          {!rows.length && (
            <tr>
              <td colSpan={5} className="muted">
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
              <div style={{ fontWeight: 700 }}>{edit ? `Edit ${edit.email}` : "New contact"}</div>
              <div className="spacer" />
              <button className="btn" disabled={busy} onClick={() => setOpen(false)}>
                Close
              </button>
              <button
                className="btn primary"
                disabled={busy || !emailValid || !f.group_name.trim()}
                onClick={() =>
                  onWork(async () => {
                    await mdUpsertContact(edit ? edit.contact_id : null, f);
                    setOpen(false);
                  })
                }
              >
                Save
              </button>
            </div>
            <div className="row">
              <input
                className="input"
                placeholder="Group name"
                aria-label="Contact group name"
                required
                value={f.group_name}
                onChange={(e) => setF((p) => ({ ...p, group_name: e.target.value }))}
              />
              <input className="input" type="email" aria-label="Contact email" required aria-invalid={!!f.email && !emailValid} placeholder="Email" value={f.email} onChange={(e) => setF((p) => ({ ...p, email: e.target.value }))} />
              <input className="input" aria-label="Contact name" placeholder="Name" value={f.name || ""} onChange={(e) => setF((p) => ({ ...p, name: e.target.value }))} />
              <label className="pill" style={{ cursor: "pointer" }}>
                <input type="checkbox" checked={!!f.active} onChange={(e) => setF((p) => ({ ...p, active: e.target.checked }))} /> Active
              </label>
            </div>
            {!!f.email && !emailValid && <p role="alert">Enter a valid email address.</p>}
          </>,
          () => !busy && setOpen(false),
        )}
    </>
  );
}
