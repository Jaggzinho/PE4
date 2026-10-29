import { Navigate, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { Settings as SettingsIcon } from "lucide-react";
import { me as apiMe, setToken, setupStatus, type Session } from "./api";
import LoginPage from "./pages/LoginPage";
import SetupPage from "./pages/SetupPage";
import SinotticoPage from "./pages/SinotticoPage";
import CalendarPage from "./pages/CalendarPage";
import LotsPage from "./pages/LotsPage";
import SettingsHubPage from "./pages/SettingsHubPage";
import MaterialSearch from "./components/MaterialSearch";
import { useTheme } from "./theme";

const ChartsPage = lazy(() => import("./pages/ChartsPage"));
const RatingsPage = lazy(() => import("./pages/RatingsPage"));
const CALENDAR_HREF_STORAGE_KEY = "pe3.calendar.href";

function initialCalendarHref(): string {
  const saved = sessionStorage.getItem(CALENDAR_HREF_STORAGE_KEY);
  return saved && (saved === "/calendar" || saved.startsWith("/calendar?")) ? saved : "/calendar";
}

export default function App() {
  const nav = useNavigate();
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();
  const [session, setSession] = useState<Session | null>(null);
  const [needsSetup, setNeedsSetup] = useState(false);
  const [bootError, setBootError] = useState<string | null>(null);
  const [calendarHref, setCalendarHref] = useState(initialCalendarHref);
  const isAuthed = !!session;

  async function boot() {
    setBootError(null);
    try {
      const st = await setupStatus();
      setNeedsSetup(!!st.needs_setup);
      if (st.needs_setup) {
        setSession(null);
        nav("/setup");
        return;
      }
      const s = await apiMe();
      setSession(s);
      setNeedsSetup(false);
    } catch {
      setSession(null);
    }
  }

  useEffect(() => {
    boot().catch((e) => setBootError(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (location.pathname !== "/calendar") return;
    const params = new URLSearchParams(location.search);
    params.delete("test_id");
    const query = params.toString();
    const href = `/calendar${query ? `?${query}` : ""}`;
    sessionStorage.setItem(CALENDAR_HREF_STORAGE_KEY, href);
    setCalendarHref(href);
  }, [location.pathname, location.search]);

  const canEditMaster = !!session?.permissions?.can_edit_master;
  const canManageUsers = !!session?.permissions?.can_manage_users;

  const navItems = useMemo(
    () => [
      { to: "/sinottico", label: "Sinottico", show: true },
      { to: "/lots", label: "Lots / results", show: true },
      { to: "/charts", label: "Charts", show: true },
      { to: "/ratings", label: "Ratings", show: true },
      { to: calendarHref, label: "Calendar", show: true },
    ],
    [calendarHref],
  );

  function logout() {
    setToken(null);
    setSession(null);
    nav("/login");
  }

  if (!isAuthed) {
    return (
      <Routes>
        <Route path="/setup" element={<SetupPage onDone={boot} />} />
        <Route path="/*" element={<LoginPage onLogin={boot} bootError={bootError} needsSetup={needsSetup} />} />
      </Routes>
    );
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">PE3 QC</div>
        <div className="nav">
          {navItems
            .filter((n) => n.show)
            .map((n) => (
              <NavLink key={n.to} to={n.to} className={({ isActive }) => (isActive ? "active" : "")}>
                {n.label}
              </NavLink>
            ))}
        </div>
        <div className="spacer" />
        <div className="card">
          <div style={{ fontWeight: 600 }}>{session.username}</div>
          <div className="muted" style={{ fontSize: 13 }}>
            {session.role_name}
          </div>
          <div style={{ height: 10 }} />
          <button className="btn danger" onClick={logout}>
            Logout
          </button>
        </div>
      </aside>

      <main className="content">
        <div className="topbar">
          <MaterialSearch
            onPick={(m) => {
              nav(`/charts?material_id=${m.material_id}`);
            }}
          />
          <div className="topbar-actions">
            <button
              className={`btn settings-button${location.pathname === "/settings" ? " active" : ""}`}
              type="button"
              onClick={() => nav("/settings")}
              aria-label="Open settings"
              title="Settings"
            >
              <SettingsIcon aria-hidden="true" size={18} strokeWidth={2} />
            </button>
            <button
              className="btn theme-toggle"
              type="button"
              onClick={toggleTheme}
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
              title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
            >
              <span aria-hidden="true">{theme === "dark" ? "☀" : "☾"}</span>
              {theme === "dark" ? "Light mode" : "Dark mode"}
            </button>
          </div>
        </div>
        <div className="page">
          <Suspense fallback={<div className="card muted">Loading page…</div>}>
            <Routes>
              <Route path="/sinottico" element={<SinotticoPage />} />
              <Route path="/lots" element={<LotsPage />} />
              <Route path="/charts" element={<ChartsPage />} />
              <Route path="/ratings" element={<RatingsPage />} />
              <Route path="/calendar" element={<CalendarPage />} />
              <Route path="/import" element={<Navigate to="/settings?section=import" replace />} />
              <Route path="/master-data" element={<Navigate to="/settings?section=master-data" replace />} />
              <Route path="/settings" element={<SettingsHubPage canEditMaster={canEditMaster} canManageUsers={canManageUsers} />} />
              <Route path="*" element={<SinotticoPage />} />
            </Routes>
          </Suspense>
        </div>
      </main>
    </div>
  );
}
