import { useEffect, useMemo, useState } from "react";
import { importJob, me, recentImportJobs, submitImport, type ImportJob, type Session } from "../api";

export default function ImportPage() {
  const [session, setSession] = useState<Session | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [job, setJob] = useState<ImportJob | null>(null);
  const [history, setHistory] = useState<ImportJob[]>([]);
  const [historyError, setHistoryError] = useState("");

  async function refreshHistory() {
    try {
      setHistory(await recentImportJobs());
      setHistoryError("");
    } catch (error) {
      setHistoryError(String(error));
    }
  }

  useEffect(() => {
    me().then(setSession).catch(() => setSession(null));
    refreshHistory();
  }, []);

  useEffect(() => {
    if (!job || (job.status !== "queued" && job.status !== "running")) return;
    const timer = window.setInterval(() => {
      importJob(job.job_id).then((current) => {
        setJob(current);
        if (current.status === "succeeded" || current.status === "failed") {
          setBusy(false);
          refreshHistory();
        }
      }).catch((error) => { setErr(String(error)); setBusy(false); });
    }, 750);
    return () => window.clearInterval(timer);
  }, [job?.job_id, job?.status]);

  const canImport = useMemo(() => !!session?.permissions?.can_edit_master, [session]);

  async function runImport() {
    if (!file) return;
    setBusy(true);
    setErr(null);
    setJob(null);
    try {
      const created = await submitImport(file);
      const current = await importJob(created.job_id);
      setJob(current);
      await refreshHistory();
      if (current.status === "succeeded" || current.status === "failed") setBusy(false);
    } catch (e) {
      setErr(String(e));
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h2 className="title">Import</h2>
      {!canImport && (
        <div className="muted" style={{ marginBottom: 10 }}>
          Your role cannot import workbooks.
        </div>
      )}
      <div className="row" style={{ marginBottom: 10 }}>
        <input
          className="input"
          type="file"
          accept=".xlsm,.xlsx"
          disabled={!canImport || busy}
          onChange={(e) => setFile(e.target.files?.[0] || null)}
        />
        <button className="btn" disabled={!canImport || busy || !file} onClick={runImport}>
          {busy ? "Importing…" : "Import"}
        </button>
      </div>
      {err && (
        <div className="pill" style={{ color: "var(--danger)" }}>
          {err}
        </div>
      )}
      {job && (
        <div style={{ marginTop: 10 }}>
          <div className="pill" style={{ display: "inline-block", marginBottom: 8 }}>
            {job.status === "succeeded" && job.result
              ? `Imported: ${job.result.materials} materials, ${job.result.tests} tests, ${job.result.measurements} measurements`
              : `Import ${job.status}: ${job.progress}%`}
          </div>
          <div
            role="progressbar"
            aria-label="Import progress"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={job.progress}
            style={{ height: 8, background: "var(--border)", borderRadius: 4, overflow: "hidden", marginBottom: 8 }}
          >
            <div style={{ width: `${job.progress}%`, height: "100%", background: "var(--accent)" }} />
          </div>
          <pre className="card" style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>
            {(job.messages || []).join("\n")}
          </pre>
          {job.status === "failed" && <div className="card" role="alert" style={{ color: "var(--danger)" }}>
            <strong>Import failed.</strong> {job.error || "No failure detail was recorded."}
          </div>}
        </div>
      )}
      <section aria-labelledby="import-history-title" style={{ marginTop: 20 }}>
        <div className="row"><h3 id="import-history-title">Recent import jobs</h3><button className="btn" onClick={refreshHistory}>Refresh history</button></div>
        {historyError && <div role="alert" style={{ color: "var(--danger)" }}>{historyError}</div>}
        {!historyError && history.length === 0 && <p className="muted">No import jobs recorded yet.</p>}
        {history.length > 0 && <div className="table-wrap"><table><thead><tr><th>Started</th><th>Status</th><th>Details</th><th /></tr></thead><tbody>
          {history.map((entry) => <tr key={entry.job_id}>
            <td>{new Date(entry.created_at).toLocaleString()}</td>
            <td>{entry.status}</td>
            <td>{entry.status === "failed" ? entry.error || "No failure detail recorded" : entry.status === "succeeded" ? "Completed" : `${entry.progress}%`}</td>
            <td><button className="btn" onClick={() => setJob(entry)}>View</button></td>
          </tr>)}
        </tbody></table></div>}
      </section>
    </div>
  );
}
