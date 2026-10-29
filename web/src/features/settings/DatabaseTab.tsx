import { useEffect, useState, type FormEvent } from "react";
import { settingsGetDatabaseSource, settingsSetDatabaseSource, type DatabaseSource } from "../../api/settings";
import { ErrorNotice, LoadingNotice } from "../../components/AsyncState";

export function DatabaseTab() {
  const [source, setSource] = useState<DatabaseSource | null>(null);
  const [path, setPath] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    settingsGetDatabaseSource().then((value) => {
      setSource(value);
      setPath(value.configured_next_path || value.active_path);
    }).catch(setError).finally(() => setLoading(false));
  }, []);

  async function save(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setNotice("");
    try {
      const result = await settingsSetDatabaseSource(path.trim());
      setSource(result);
      setPath(result.configured_next_path || result.active_path);
      setNotice(result.override_active
        ? "Saved locally. A command-line or environment path currently takes precedence; remove that override and restart to use this path."
        : result.restart_required ? "Saved for the next startup. Restart PE3 to use this database." : "Saved. This is already the active database path.");
    } catch (cause) {
      setError(cause);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section aria-labelledby="database-title">
      <h3 id="database-title">Database source</h3>
      {loading && <LoadingNotice>Loading database source…</LoadingNotice>}
      {error != null && <ErrorNotice error={error} />}
      {source && <>
        <p>Active path: <code style={{ overflowWrap: "anywhere" }}>{source.active_path}</code></p>
        <p>Active source: <strong>{source.active_source.replaceAll("_", " ")}</strong></p>
        {source.configured_next_path && <p>Saved web path: <code style={{ overflowWrap: "anywhere" }}>{source.configured_next_path}</code></p>}
        <p className="muted">Choose an existing, readable .duckdb file. This only changes local startup configuration; the current database connection and data are not moved or switched. Snapshot distribution is a separate legacy workflow.</p>
        {source.override_active && <p role="status">An explicit launch path currently takes precedence over this saved web path.</p>}
        {source.restart_required && <p role="status">Restart required to apply the saved path (after removing any explicit launch override).</p>}
        <form onSubmit={save}>
          <label htmlFor="next-database-path">Database path for next startup</label>
          <div className="row">
            <input id="next-database-path" type="text" value={path} onChange={(event) => setPath(event.target.value)} required disabled={saving} style={{ minWidth: 350, flex: 1 }} />
            <button className="btn" type="submit" disabled={saving || !path.trim()}>{saving ? "Validating…" : "Save next-startup path"}</button>
          </div>
        </form>
        {notice && <p role="status">{notice}</p>}
      </>}
      {!loading && !source && error == null && <p>No database source is available.</p>}
    </section>
  );
}
