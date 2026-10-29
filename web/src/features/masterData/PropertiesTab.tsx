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

export function PropertiesTab({ rows, busy, onWork }: { rows: Property[]; busy: boolean; onWork: (fn: () => Promise<void>) => void }) {
  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState<Property | null>(null);
  const [f, setF] = useState<Omit<Property, "property_id">>({ name: "", unit: "", active: true, sort_order: null });
  const sortOrderInvalid = f.sort_order != null && !Number.isInteger(f.sort_order);

  function startNew() {
    setEdit(null);
    setF({ name: "", unit: "", active: true, sort_order: null });
    setOpen(true);
  }
  function startEdit(r: Property) {
    setEdit(r);
    setF({ name: r.name, unit: r.unit || "", active: r.active, sort_order: r.sort_order });
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
            <th>Unit</th>
            <th>Sort</th>
            <th>Active</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.property_id}>
              <td>{r.name}</td>
              <td>{r.unit || "—"}</td>
              <td>{r.sort_order == null ? "—" : r.sort_order}</td>
              <td>{r.active ? "Yes" : "No"}</td>
              <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                <button className="btn" disabled={busy} onClick={() => startEdit(r)}>
                  Edit
                </button>{" "}
                <button className="btn danger" disabled={busy} onClick={() => confirmDelete("property", r.name) && onWork(async () => mdDeleteProperty(r.property_id))}>
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
              <div style={{ fontWeight: 700 }}>{edit ? `Edit ${edit.name}` : "New property"}</div>
              <div className="spacer" />
              <button className="btn" disabled={busy} onClick={() => setOpen(false)}>
                Close
              </button>
              <button
                className="btn primary"
                disabled={busy || !f.name.trim() || sortOrderInvalid}
                onClick={() =>
                  onWork(async () => {
                    await mdUpsertProperty(edit ? edit.property_id : null, { ...f, unit: (f.unit || "").trim() || null } as any);
                    setOpen(false);
                  })
                }
              >
                Save
              </button>
            </div>
            <div className="row">
              <input className="input" aria-label="Property name" required placeholder="Name" value={f.name} onChange={(e) => setF((p) => ({ ...p, name: e.target.value }))} />
              <input className="input" aria-label="Property unit" placeholder="Unit" value={f.unit || ""} onChange={(e) => setF((p) => ({ ...p, unit: e.target.value }))} />
              <input
                className="input"
                placeholder="Sort order"
                aria-label="Sort order"
                type="number"
                step={1}
                value={f.sort_order == null ? "" : String(f.sort_order)}
                aria-invalid={sortOrderInvalid}
                onChange={(e) => setF((p) => ({ ...p, sort_order: e.target.value.trim() ? Number(e.target.value) : null }))}
              />
              <label className="pill" style={{ cursor: "pointer" }}>
                <input type="checkbox" checked={!!f.active} onChange={(e) => setF((p) => ({ ...p, active: e.target.checked }))} /> Active
              </label>
            </div>
            {sortOrderInvalid && <p role="alert">Sort order must be a whole number.</p>}
          </>,
          () => !busy && setOpen(false),
        )}
    </>
  );
}
