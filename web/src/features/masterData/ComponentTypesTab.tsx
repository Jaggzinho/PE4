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

export function ComponentTypesTab({ rows, busy, onWork }: { rows: ComponentType[]; busy: boolean; onWork: (fn: () => Promise<void>) => void }) {
  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState<ComponentType | null>(null);
  const [f, setF] = useState<Omit<ComponentType, "type_id">>({ name: "", slot_key: "", active: true });

  function startNew() {
    setEdit(null);
    setF({ name: "", slot_key: "", active: true });
    setOpen(true);
  }
  function startEdit(r: ComponentType) {
    setEdit(r);
    setF({ name: r.name, slot_key: r.slot_key || "", active: r.active });
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
            <th>Slot key</th>
            <th>Active</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.type_id}>
              <td>{r.name}</td>
              <td>{r.slot_key || "—"}</td>
              <td>{r.active ? "Yes" : "No"}</td>
              <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                <button className="btn" disabled={busy} onClick={() => startEdit(r)}>
                  Edit
                </button>{" "}
                <button className="btn danger" disabled={busy} onClick={() => confirmDelete("component type", r.name) && onWork(async () => mdDeleteComponentType(r.type_id))}>
                  Delete
                </button>
              </td>
            </tr>
          ))}
          {!rows.length && (
            <tr>
              <td colSpan={4} className="muted">
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
              <div style={{ fontWeight: 700 }}>{edit ? `Edit ${edit.name}` : "New component type"}</div>
              <div className="spacer" />
              <button className="btn" disabled={busy} onClick={() => setOpen(false)}>
                Close
              </button>
              <button
                className="btn primary"
                disabled={busy || !f.name.trim()}
                onClick={() =>
                  onWork(async () => {
                    await mdUpsertComponentType(edit ? edit.type_id : null, { ...f, slot_key: (f.slot_key || "").trim() || null } as any);
                    setOpen(false);
                  })
                }
              >
                Save
              </button>
            </div>
            <div className="row">
              <input className="input" aria-label="Component type name" required placeholder="Name" value={f.name} onChange={(e) => setF((p) => ({ ...p, name: e.target.value }))} />
              <input
                className="input"
                placeholder="Slot key"
                aria-label="Slot key"
                value={f.slot_key || ""}
                onChange={(e) => setF((p) => ({ ...p, slot_key: e.target.value }))}
              />
              <label className="pill" style={{ cursor: "pointer" }}>
                <input type="checkbox" checked={!!f.active} onChange={(e) => setF((p) => ({ ...p, active: e.target.checked }))} /> Active
              </label>
            </div>
          </>,
          () => !busy && setOpen(false),
        )}
    </>
  );
}
