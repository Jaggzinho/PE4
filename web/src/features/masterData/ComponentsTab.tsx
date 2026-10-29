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
  type ApiId,
  type Contact,
  type EmailTemplate,
  type Material,
  type Property,
  type Tolerance,
} from "../../api";
import { modalFrame } from "../ModalFrame";
import { confirmDelete } from "../confirmAction";

export function ComponentsTab({
  rows,
  types,
  busy,
  onWork,
}: {
  rows: Component[];
  types: ComponentType[];
  busy: boolean;
  onWork: (fn: () => Promise<void>) => void;
}) {
  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState<Component | null>(null);
  const [f, setF] = useState<{ type_id: ApiId; code: string; description: string; unit: string; active: boolean }>({
    type_id: "",
    code: "",
    description: "",
    unit: "",
    active: true,
  });

  function startNew() {
    const first = types[0];
    setEdit(null);
    setF({ type_id: first ? first.type_id : "", code: "", description: "", unit: "", active: true });
    setOpen(true);
  }
  function startEdit(r: Component) {
    setEdit(r);
    setF({ type_id: r.type_id, code: r.code, description: r.description || "", unit: r.unit || "", active: r.active });
    setOpen(true);
  }

  return (
    <>
      <div className="row" style={{ marginBottom: 10 }}>
        <button className="btn primary" onClick={startNew} disabled={busy || !types.length}>
          Add
        </button>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th>Type</th>
            <th>Code</th>
            <th>Description</th>
            <th>Unit</th>
            <th>Active</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.component_id}>
              <td>{r.type_name}</td>
              <td>{r.code}</td>
              <td>{r.description || "—"}</td>
              <td>{r.unit || "—"}</td>
              <td>{r.active ? "Yes" : "No"}</td>
              <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                <button className="btn" disabled={busy} onClick={() => startEdit(r)}>
                  Edit
                </button>{" "}
                <button className="btn danger" disabled={busy} onClick={() => confirmDelete("component", r.code) && onWork(async () => mdDeleteComponent(r.component_id))}>
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
              <div style={{ fontWeight: 700 }}>{edit ? `Edit ${edit.code}` : "New component"}</div>
              <div className="spacer" />
              <button className="btn" disabled={busy} onClick={() => setOpen(false)}>
                Close
              </button>
              <button
                className="btn primary"
                disabled={busy || !f.code.trim() || !f.type_id}
                onClick={() =>
                  onWork(async () => {
                    await mdUpsertComponent(edit ? edit.component_id : null, {
                      type_id: f.type_id,
                      code: f.code,
                      description: f.description || null,
                      unit: f.unit || null,
                      active: f.active,
                    } as any);
                    setOpen(false);
                  })
                }
              >
                Save
              </button>
            </div>
            <div className="row">
              <select className="input" aria-label="Component type" required value={f.type_id} onChange={(e) => setF((p) => ({ ...p, type_id: e.target.value }))}>
                <option value="">Select type…</option>
                {types.map((t) => (
                  <option key={t.type_id} value={t.type_id}>
                    {t.name}
                  </option>
                ))}
              </select>
              <input className="input" aria-label="Component code" required placeholder="Code" value={f.code} onChange={(e) => setF((p) => ({ ...p, code: e.target.value }))} />
              <input
                className="input"
                placeholder="Description"
                aria-label="Component description"
                value={f.description}
                onChange={(e) => setF((p) => ({ ...p, description: e.target.value }))}
              />
              <input className="input" aria-label="Component unit" placeholder="Unit" value={f.unit} onChange={(e) => setF((p) => ({ ...p, unit: e.target.value }))} />
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
