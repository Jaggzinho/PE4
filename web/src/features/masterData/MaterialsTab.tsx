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

export function MaterialsTab({ rows, busy, onWork }: { rows: Material[]; busy: boolean; onWork: (fn: () => Promise<void>) => void }) {
  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState<Material | null>(null);
  const [f, setF] = useState<Omit<Material, "material_id" | "component_defaults">>({ code: "", description: "", lastrina_code: "", lastrina_desc: "", active: true });

  function startNew() {
    setEdit(null);
    setF({ code: "", description: "", lastrina_code: "", lastrina_desc: "", active: true });
    setOpen(true);
  }
  function startEdit(r: Material) {
    setEdit(r);
    setF({ code: r.code, description: r.description, lastrina_code: r.lastrina_code, lastrina_desc: r.lastrina_desc, active: r.active });
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
            <th>Code</th>
            <th>Description</th>
            <th>Lastrina</th>
            <th>Active</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.material_id}>
              <td>{r.code}</td>
              <td>{r.description || "—"}</td>
              <td>{r.lastrina_code || "—"}</td>
              <td>{r.active ? "Yes" : "No"}</td>
              <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                <button className="btn" disabled={busy} onClick={() => startEdit(r)}>
                  Edit
                </button>{" "}
                <button className="btn danger" disabled={busy} onClick={() => confirmDelete("material", r.code) && onWork(async () => mdDeleteMaterial(r.material_id))}>
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
              <div style={{ fontWeight: 700 }}>{edit ? `Edit ${edit.code}` : "New material"}</div>
              <div className="spacer" />
              <button className="btn" disabled={busy} onClick={() => setOpen(false)}>
                Close
              </button>
              <button
                className="btn primary"
                disabled={busy || !f.code.trim()}
                onClick={() =>
                  onWork(async () => {
                    await mdUpsertMaterial(edit ? edit.material_id : null, f);
                    setOpen(false);
                  })
                }
              >
                Save
              </button>
            </div>
            <div className="row">
              <input className="input" aria-label="Material code" required placeholder="Code" value={f.code} onChange={(e) => setF((p) => ({ ...p, code: e.target.value }))} />
              <input
                className="input"
                placeholder="Description"
                aria-label="Material description"
                value={f.description || ""}
                onChange={(e) => setF((p) => ({ ...p, description: e.target.value }))}
              />
              <input
                className="input"
                placeholder="Lastrina code"
                aria-label="Lastrina code"
                value={f.lastrina_code || ""}
                onChange={(e) => setF((p) => ({ ...p, lastrina_code: e.target.value }))}
              />
              <input
                className="input"
                placeholder="Lastrina desc"
                aria-label="Lastrina description"
                value={f.lastrina_desc || ""}
                onChange={(e) => setF((p) => ({ ...p, lastrina_desc: e.target.value }))}
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
