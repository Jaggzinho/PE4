import { useEffect, useState } from "react";
import { listEnvironments, login, type Environment } from "../api";
import EnvironmentSelect from "../components/EnvironmentSelect";
import logo from "../assets/logo.png";

export default function LoginPage(props: { onLogin: () => Promise<void>; bootError: string | null; needsSetup: boolean }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [environmentId, setEnvironmentId] = useState(() => sessionStorage.getItem("pe3.environment") || "tcm_ro");
  const [loading, setLoading] = useState(true);
  const [environmentError, setEnvironmentError] = useState<string | null>(null);

  async function loadEnvironments() {
    setLoading(true);
    setEnvironmentError(null);
    try {
      setEnvironments(await listEnvironments());
    } catch (error) {
      setEnvironmentError(String(error));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void loadEnvironments(); }, []);
  const selected = environments.find((item) => item.environment_id === environmentId && item.available);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!selected || loading || environmentError) return;
    setErr(null);
    setBusy(true);
    try {
      await login(username, password, environmentId);
      sessionStorage.setItem("pe3.environment", environmentId);
      await props.onLogin();
    } catch (e2) {
      setErr(String(e2));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ display: "grid", placeItems: "center", height: "100vh", padding: 16 }}>
      <div className="card" style={{ width: 420, maxWidth: "100%" }}>
        <h1 className="title login-brand"><img className="brand-logo" src={logo} alt="PE3 QC" /></h1>
        <div className="muted" style={{ marginBottom: 12 }}>
          Sign in
        </div>
        {props.needsSetup && (
          <div className="pill" style={{ marginBottom: 12 }}>
            First run setup required. Open <span style={{ fontWeight: 700 }}>/setup</span>.
          </div>
        )}
        {props.bootError && (
          <div className="pill" style={{ borderColor: "rgba(255,90,111,0.6)", color: "var(--danger)" }}>
            {props.bootError}
          </div>
        )}
        <form onSubmit={submit} style={{ marginTop: 14, display: "grid", gap: 10 }}>
          <EnvironmentSelect environments={environments} value={environmentId} onChange={setEnvironmentId}
            disabled={busy || loading || !!environmentError || environments.length === 0} />
          {loading && <div role="status">Loading environments…</div>}
          {environmentError && <div role="alert">{environmentError} <button className="btn" type="button" onClick={() => void loadEnvironments()}>Retry</button></div>}
          {!loading && !environmentError && !environments.some((item) => item.available) && <div role="alert">No environments are available.</div>}
          <input className="input" aria-label="Username" autoComplete="username" required placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} />
          <input
            className="input"
            placeholder="Password"
            aria-label="Password"
            autoComplete="current-password"
            required
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <button className="btn primary" disabled={busy || loading || !!environmentError || !selected}>
            {busy ? "Signing in..." : "Login"}
          </button>
        </form>
        {err && (
          <div className="pill" style={{ marginTop: 12, borderColor: "rgba(255,90,111,0.6)", color: "var(--danger)" }}>
            {err}
          </div>
        )}
      </div>
    </div>
  );
}
