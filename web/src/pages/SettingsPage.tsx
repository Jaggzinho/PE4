import { useEffect, useMemo, useState } from "react";
import {
  settingsGetChartsTolerancePct,
  settingsListRatings,
  settingsListRoles,
  settingsListUsers,
  settingsSetChartsTolerancePct,
  type ChartsTolerancePct,
  type RatingRow,
  type Role,
  type User,
} from "../api";

import {
  ChartsTab,
  RatingsTab,
  RolesTab,
  UsersTab,
  OutlookTab,
  DatabaseTab,
} from "../features/settings";
import { ErrorNotice, LoadingNotice } from "../components/AsyncState";

type Tab = "charts" | "ratings" | "roles" | "users" | "outlook" | "database";

export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>("charts");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadedTab, setLoadedTab] = useState<Tab | null>(null);
  const [err, setErr] = useState<unknown>(null);

  const [chartsTol, setChartsTol] = useState<ChartsTolerancePct | null>(null);
  const [ratings, setRatings] = useState<RatingRow[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [users, setUsers] = useState<User[]>([]);

  async function refresh() {
    setErr(null);
    if (tab === "charts") setChartsTol(await settingsGetChartsTolerancePct());
    if (tab === "ratings") setRatings(await settingsListRatings());
    if (tab === "roles") setRoles(await settingsListRoles());
    if (tab === "users") {
      const [rs, us] = await Promise.all([settingsListRoles(), settingsListUsers()]);
      setRoles(rs);
      setUsers(us);
    }
    setLoadedTab(tab);
  }

  useEffect(() => {
    setLoading(true);
    refresh().catch(setErr).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  async function doWork(fn: () => Promise<void>) {
    setBusy(true);
    setErr(null);
    try {
      await fn();
      await refresh();
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  }

  const roleOptions = useMemo(() => roles.slice().sort((a, b) => a.name.localeCompare(b.name)), [roles]);
  const unavailable = busy || loading;

  return (
    <div className="card">
      <h2 className="title">Application settings</h2>
      <div className="row" style={{ marginBottom: 10 }}>
        <button className="btn" onClick={() => setTab("charts")} disabled={unavailable || tab === "charts"}>
          Charts
        </button>
        <button className="btn" onClick={() => setTab("ratings")} disabled={unavailable || tab === "ratings"}>
          Ratings
        </button>
        <button className="btn" onClick={() => setTab("roles")} disabled={unavailable || tab === "roles"}>
          Roles
        </button>
        <button className="btn" onClick={() => setTab("users")} disabled={unavailable || tab === "users"}>
          Users
        </button>
        <button className="btn" onClick={() => setTab("outlook")} disabled={unavailable || tab === "outlook"}>
          Outlook
        </button>
        <button className="btn" onClick={() => setTab("database")} disabled={unavailable || tab === "database"}>
          Database
        </button>
        <div className="spacer" />
        <button className="btn" onClick={() => { setLoading(true); refresh().catch(setErr).finally(() => setLoading(false)); }} disabled={unavailable}>
          Refresh
        </button>
      </div>

      {err != null && <ErrorNotice error={err} />}
      {loading && <LoadingNotice>Loading settings…</LoadingNotice>}
      {busy && <div role="status" className="muted">Saving changes…</div>}

      {!loading && loadedTab === tab && tab === "charts" && chartsTol && <ChartsTab busy={busy} value={chartsTol} onSave={(v) => doWork(async () => void (await settingsSetChartsTolerancePct(v)))} />}
      {!loading && loadedTab === tab && tab === "ratings" && <RatingsTab busy={busy} rows={ratings} onWork={doWork} />}
      {!loading && loadedTab === tab && tab === "roles" && <RolesTab busy={busy} rows={roles} onWork={doWork} />}
      {!loading && loadedTab === tab && tab === "users" && <UsersTab busy={busy} rows={users} roles={roleOptions} onWork={doWork} />}
      {!loading && loadedTab === tab && tab === "outlook" && <OutlookTab />}
      {!loading && loadedTab === tab && tab === "database" && <DatabaseTab />}
    </div>
  );
}
