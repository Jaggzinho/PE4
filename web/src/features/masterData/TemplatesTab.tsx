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

export function TemplatesTab({ rows, busy, onWork }: { rows: EmailTemplate[]; busy: boolean; onWork: (fn: () => Promise<void>) => void }) {
  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState<EmailTemplate | null>(null);
  const [f, setF] = useState<Omit<EmailTemplate, "template_id">>({
    name: "",
    to_group: "",
    cc_group: "",
    subject_tmpl: "",
    body_tmpl: "",
    is_html: false,
    active: true,
  });

  function startNew() {
    setEdit(null);
    setF({ name: "", to_group: "", cc_group: "", subject_tmpl: "", body_tmpl: "", is_html: false, active: true });
    setOpen(true);
  }
  function startEdit(r: EmailTemplate) {
    setEdit(r);
    setF({
      name: r.name,
      to_group: r.to_group || "",
      cc_group: r.cc_group || "",
      subject_tmpl: r.subject_tmpl,
      body_tmpl: r.body_tmpl,
      is_html: r.is_html,
      active: r.active,
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
            <th>To group</th>
            <th>Cc group</th>
            <th>HTML</th>
            <th>Active</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.template_id}>
              <td>{r.name}</td>
              <td>{r.to_group || "—"}</td>
              <td>{r.cc_group || "—"}</td>
              <td>{r.is_html ? "Yes" : "No"}</td>
              <td>{r.active ? "Yes" : "No"}</td>
              <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                <button className="btn" disabled={busy} onClick={() => startEdit(r)}>
                  Edit
                </button>{" "}
                <button className="btn danger" disabled={busy} onClick={() => confirmDelete("template", r.name) && onWork(async () => mdDeleteTemplate(r.template_id))}>
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
              <div style={{ fontWeight: 700 }}>{edit ? `Edit ${edit.name}` : "New template"}</div>
              <div className="spacer" />
              <button className="btn" disabled={busy} onClick={() => setOpen(false)}>
                Close
              </button>
              <button
                className="btn primary"
                disabled={busy || !f.name.trim() || !f.subject_tmpl.trim() || !f.body_tmpl.trim()}
                onClick={() =>
                  onWork(async () => {
                    await mdUpsertTemplate(edit ? edit.template_id : null, {
                      ...f,
                      to_group: (f.to_group || "").trim() || null,
                      cc_group: (f.cc_group || "").trim() || null,
                    } as any);
                    setOpen(false);
                  })
                }
              >
                Save
              </button>
            </div>
            <div className="row" style={{ marginBottom: 10 }}>
              <input className="input" aria-label="Template name" required placeholder="Name" value={f.name} onChange={(e) => setF((p) => ({ ...p, name: e.target.value }))} />
              <input
                className="input"
                placeholder="To group"
                aria-label="To group"
                value={f.to_group || ""}
                onChange={(e) => setF((p) => ({ ...p, to_group: e.target.value }))}
              />
              <input
                className="input"
                placeholder="Cc group"
                aria-label="Cc group"
                value={f.cc_group || ""}
                onChange={(e) => setF((p) => ({ ...p, cc_group: e.target.value }))}
              />
              <label className="pill" style={{ cursor: "pointer" }}>
                <input type="checkbox" checked={!!f.is_html} onChange={(e) => setF((p) => ({ ...p, is_html: e.target.checked }))} /> HTML
              </label>
              <label className="pill" style={{ cursor: "pointer" }}>
                <input type="checkbox" checked={!!f.active} onChange={(e) => setF((p) => ({ ...p, active: e.target.checked }))} /> Active
              </label>
            </div>
            <div className="row" style={{ alignItems: "flex-start" }}>
              <textarea
                className="input"
                style={{ minWidth: 440, minHeight: 80 }}
                placeholder="Subject template"
                aria-label="Subject template"
                required
                value={f.subject_tmpl}
                onChange={(e) => setF((p) => ({ ...p, subject_tmpl: e.target.value }))}
              />
              <textarea
                className="input"
                style={{ minWidth: 440, minHeight: 240 }}
                placeholder="Body template"
                aria-label="Body template"
                required
                value={f.body_tmpl}
                onChange={(e) => setF((p) => ({ ...p, body_tmpl: e.target.value }))}
              />
            </div>
          </>,
          () => !busy && setOpen(false),
        )}
    </>
  );
}
