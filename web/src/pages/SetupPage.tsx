import { useState } from "react";
import { setupFirstAdmin } from "../api";

export default function SetupPage(props: { onDone: () => Promise<void> }) {
  const [token, setToken] = useState("");
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await setupFirstAdmin(token, username, password, password2);
      await props.onDone();
    } catch (e2) {
      setErr(String(e2));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ display: "grid", placeItems: "center", height: "100vh", padding: 16 }}>
      <div className="card" style={{ width: 520, maxWidth: "100%" }}>
        <h1 className="title">First Run Setup</h1>
        <div className="muted" style={{ marginBottom: 12 }}>
          Create the first Admin user (only possible when the database has 0 users).
        </div>

        <form onSubmit={submit} style={{ display: "grid", gap: 10 }}>
          <input
            className="input"
            placeholder="Setup token (X-PE3-SETUP-TOKEN)"
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
          <input className="input" placeholder="Admin username" value={username} onChange={(e) => setUsername(e.target.value)} />
          <input
            className="input"
            placeholder="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <input
            className="input"
            placeholder="Repeat password"
            type="password"
            value={password2}
            onChange={(e) => setPassword2(e.target.value)}
          />
          <button className="btn primary" disabled={busy}>
            {busy ? "Creating..." : "Create Admin"}
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

