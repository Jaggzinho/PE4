import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { qcHref } from "../features/qcLinks";
import {
  listQueue,
  listSinottico,
  queueAdd,
  queueClear,
  queueEmailEmlBlob,
  queueEmailPreview,
  queueFinalize,
  queueRemove,
  searchMaterials,
  type EmailDraft,
  type ApiId,
  type Material,
  type QueueRow,
  type SinotticoRow,
} from "../api";

export default function SinotticoPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const materialId = searchParams.get("material_id") || "";
  const [rows, setRows] = useState<SinotticoRow[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [queue, setQueue] = useState<QueueRow[]>([]);
  const [tab, setTab] = useState<"dash" | "queue">("dash");
  const [draft, setDraft] = useState<EmailDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function refreshAll() {
    const r = await listSinottico();
    setRows(r);
    try {
      const q = await listQueue();
      setQueue(q);
    } catch {
      setQueue([]);
    }
  }

  useEffect(() => {
    let alive = true;
    setErr(null);
    refreshAll().catch((e) => alive && setErr(String(e)));
    searchMaterials("").then((result) => alive && setMaterials(result)).catch(() => alive && setMaterials([]));
    return () => {
      alive = false;
    };
  }, []);

  const materialDescriptions = useMemo(
    () => new Map(materials.map((material) => [material.material_id, material.description])),
    [materials],
  );
  const materialOptions = useMemo(() => Array.from(new Map(rows.filter((row) => row.material_id).map((row) => {
    const id = row.material_id!;
    const code = row.material_code || row.excel_code || row.item_id;
    const description = materialDescriptions.get(id);
    return [id, `${code}${description ? ` — ${description}` : ""}`];
  })).entries()), [rows, materialDescriptions]);
  const dashRows = useMemo(() => materialId ? rows.filter((row) => row.material_id === materialId) : rows, [rows, materialId]);
  const dashGroups = useMemo(() => {
    const groups = new Map<string, { label: string; rows: SinotticoRow[] }>();
    for (const row of dashRows) {
      const label = row.machine_code?.trim() || "—";
      const group = groups.get(label);
      if (group) group.rows.push(row);
      else groups.set(label, { label, rows: [row] });
    }
    return Array.from(groups.entries()).map(([key, group]) => ({ key, ...group }));
  }, [dashRows]);

  async function onAddToQueue(itemId: ApiId) {
    setBusy(true);
    setErr(null);
    try {
      await queueAdd(itemId);
      const q = await listQueue();
      setQueue(q);
      setTab("queue");
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onRemoveFromQueue(itemId: ApiId) {
    setBusy(true);
    setErr(null);
    try {
      await queueRemove(itemId);
      const q = await listQueue();
      setQueue(q);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onClearQueue() {
    setBusy(true);
    setErr(null);
    try {
      await queueClear();
      setQueue([]);
      setDraft(null);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onPreviewDraft() {
    setBusy(true);
    setErr(null);
    try {
      const d = await queueEmailPreview();
      setDraft(d);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onDownloadEml() {
    setBusy(true);
    setErr(null);
    try {
      const blob = await queueEmailEmlBlob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `pe3-sample-request-${new Date().toISOString().slice(0, 10)}.eml`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onFinalize() {
    setBusy(true);
    setErr(null);
    try {
      await queueFinalize();
      await refreshAll();
      setDraft(null);
      setTab("dash");
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h2 className="title">Sinottico</h2>
      <div className="row" style={{ marginBottom: 10 }}>
        <select className="input" aria-label="Filter Sinottico by material" value={materialId} onChange={(event) => {
          const next = new URLSearchParams(searchParams);
          if (event.target.value) next.set("material_id", event.target.value);
          else next.delete("material_id");
          setSearchParams(next);
        }}>
          <option value="">All materials</option>
          {materialOptions.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
        </select>
        <button className="btn" onClick={() => setTab("dash")} disabled={tab === "dash" || busy}>
          Dashboard
        </button>
        <button className="btn" onClick={() => setTab("queue")} disabled={tab === "queue" || busy}>
          Queue ({queue.length})
        </button>
        <div className="spacer" />
        <button className="btn" onClick={() => refreshAll().catch((e) => setErr(String(e)))} disabled={busy}>
          Refresh
        </button>
      </div>

      {err && (
        <div className="pill" style={{ color: "var(--danger)" }}>
          {err}
        </div>
      )}

      {tab === "dash" && (
        <table className="table">
          <thead>
            <tr>
              <th>MAC</th>
              <th>Code</th>
              <th>Description</th>
              <th>Last request</th>
              <th>Rating</th>
              <th />
            </tr>
          </thead>
          {dashGroups.map((group) => (
            <tbody className="sinottico-group" key={group.key}>
              {group.rows.map((r, rowIndex) => (
                <tr key={r.item_id}>
                  {rowIndex === 0 && <td className="sinottico-mac-cell" rowSpan={group.rows.length}>{group.label}</td>}
                  <td>{r.material_id ? <Link to={qcHref("lots", { materialId: r.material_id })}>{r.material_code || r.excel_code || "—"}</Link> : r.material_code || r.excel_code || "—"}</td>
                  <td>{r.description || "—"}</td>
                  <td>{r.last_request_date || "—"}</td>
                  <td>{r.rating_percent == null ? "—" : `${r.rating_percent.toFixed(1)}%`}</td>
                  <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    {r.material_id && <><Link to={qcHref("charts", { materialId: r.material_id })}>Charts</Link>{" · "}<Link to={qcHref("ratings", { materialId: r.material_id })}>Ratings</Link>{" · "}<Link to={qcHref("calendar", { materialId: r.material_id })}>Calendar</Link>{" "}</>}
                    <button className="btn" disabled={busy || !r.item_id || !r.material_id} onClick={() => onAddToQueue(r.item_id)}>
                      Request
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          ))}
          {!dashGroups.length && (
            <tbody>
              <tr>
                <td colSpan={6} className="muted">
                  No data
                </td>
              </tr>
            </tbody>
          )}
        </table>
      )}

      {tab === "queue" && (
        <>
          <div className="row" style={{ marginBottom: 10 }}>
            <button className="btn danger" onClick={onClearQueue} disabled={busy || !queue.length}>
              Clear
            </button>
            <button className="btn" onClick={onPreviewDraft} disabled={busy || !queue.length}>
              Preview
            </button>
            <button className="btn" onClick={onDownloadEml} disabled={busy || !queue.length}>
              Download .eml
            </button>
            <button className="btn" onClick={onFinalize} disabled={busy || !queue.length}>
              Finalize
            </button>
            <div className="muted" style={{ marginLeft: 8 }}>
              Finalize logs sample requests + creates tests, then clears the queue.
            </div>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>MAC</th>
                <th>Code</th>
                <th>Description</th>
                <th>Lastrina</th>
                <th>Last request</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {queue.map((r) => (
                <tr key={r.item_id}>
                  <td>{r.machine_code || "—"}</td>
                  <td>{r.material_code || "—"}</td>
                  <td>{r.description || "—"}</td>
                  <td>{r.lastrina_code || "—"}</td>
                  <td>{r.last_request_date || "—"}</td>
                  <td style={{ textAlign: "right" }}>
                    <button className="btn danger" onClick={() => onRemoveFromQueue(r.item_id)} disabled={busy}>
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
              {!queue.length && (
                <tr>
                  <td colSpan={6} className="muted">
                    Queue is empty
                  </td>
                </tr>
              )}
            </tbody>
          </table>

          {draft && (
            <div style={{ marginTop: 12 }}>
              <div className="pill" style={{ display: "inline-block", marginBottom: 8 }}>
                Draft preview
              </div>
              <pre className="card" style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>
                {`To: ${draft.to_list}\nCc: ${draft.cc_list}\nSubject: ${draft.subject}\n\n${draft.body}`}
              </pre>
            </div>
          )}
        </>
      )}
    </div>
  );
}

