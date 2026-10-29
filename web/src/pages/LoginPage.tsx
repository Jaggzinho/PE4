import { useState } from "react";
import { login } from "../api";

export default function LoginPage(props: { onLogin: () => Promise<void>; bootError: string | null; needsSetup: boolean }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await login(username, password);
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
        <h1 className="title">PE3 QC</h1>
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
          <button className="btn primary" disabled={busy}>
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
