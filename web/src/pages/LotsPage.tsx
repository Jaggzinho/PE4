import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { qcHref } from "../features/qcLinks";
import {
  createLot,
  deleteLot,
  getLotDetails,
  listLots,
  me,
  searchMaterials,
  updateLot,
  type LotDetails,
  type LotUpsert,
  type LotsRow,
  type LotsDateField,
  type LotsSortKey,
  type LotsStatus,
  type Material,
  type Session,
  type ApiId,
} from "../api";

const COMPONENT_TYPES = ["ISO", "POL", "CAT", "ADD1", "ADD2", "ADD3", "ADD4", "EXT"] as const;

type QcSortKey = "durezza" | "carico_rottura" | "allungamento" | "lacerazione_ba" | "lacerazione_ca" | "abrasione" | "resistivita_superficiale";
type ComponentFilterKey = "iso" | "pol" | "cat" | "add1" | "add2";
type ColumnKey = Exclude<LotsSortKey, "latest">;

const QC_FIELDS: { key: QcSortKey; label: string }[] = [
  { key: "durezza", label: "Durezza" },
  { key: "carico_rottura", label: "Carico di rottura" },
  { key: "allungamento", label: "Allungamento" },
  { key: "lacerazione_ba", label: "Lacerazione B_a" },
  { key: "lacerazione_ca", label: "Lacerazione C_a" },
  { key: "abrasione", label: "Abrasione" },
  { key: "resistivita_superficiale", label: "Resistività Superficiale" },
];

const LOTS_SORT_KEYS: readonly LotsSortKey[] = [
  "latest", "request_date", "prod_date", "analysis_date", "material", "lastrina",
  "iso", "pol", "cat", "add1", "add2", ...QC_FIELDS.map((field) => field.key),
];

const COLUMN_DEFS: Array<{ key: ColumnKey; label: string }> = [
  { key: "request_date", label: "Request" }, { key: "prod_date", label: "Prod" },
  { key: "analysis_date", label: "Analysis" }, { key: "material", label: "Material" },
  { key: "lastrina", label: "Lastrina" }, { key: "iso", label: "ISO" },
  { key: "pol", label: "POL" }, { key: "cat", label: "CAT" },
  { key: "add1", label: "ADD1" }, { key: "add2", label: "ADD2" }, ...QC_FIELDS,
];
const COLUMN_STORAGE_KEY = "pe3.lots.visible-columns";

function SortHeader({ label, sortKey, current, direction, onSort }: {
  label: string;
  sortKey: LotsSortKey;
  current: LotsSortKey;
  direction: "asc" | "desc";
  onSort: (key: LotsSortKey) => void;
}) {
  const active = current === sortKey;
  return (
    <th aria-sort={active ? (direction === "asc" ? "ascending" : "descending") : "none"}>
      <button className="table-sort-button" type="button" onClick={() => onSort(sortKey)}>
        {label}<span aria-hidden="true">{active ? (direction === "asc" ? " ↑" : " ↓") : " ↕"}</span>
      </button>
    </th>
  );
}

type ModalState =
  | { open: false }
  | { open: true; mode: "new" }
  | { open: true; mode: "edit"; testId: ApiId };

function emptyUpsert(materialId: ApiId): LotUpsert {
  const components: any = {};
  for (const t of COMPONENT_TYPES) components[t] = { code: "", desc: "", lot: "" };
  const qc: any = {};
  for (const f of QC_FIELDS) qc[f.key] = "";
  return {
    material_id: materialId,
    request_date: "",
    prod_date: "",
    analysis_date: "",
    components,
    qc,
  };
}

function withMaterialDefaults(upsert: LotUpsert, material?: Material): LotUpsert {
  if (!material) return upsert;
  const components = { ...(upsert.components || {}) };
  for (const type of COMPONENT_TYPES) {
    const current = components[type] || { code: "", desc: "", lot: "" };
    const defaults = material.component_defaults?.[type];
    const currentCode = current.code?.trim() || "";
    const currentDesc = current.desc?.trim() || "";
    const defaultCode = defaults?.code?.trim() || "";
    const defaultDesc = defaults?.desc?.trim() || "";

    if (!currentCode && !currentDesc) {
      components[type] = { ...current, code: defaultCode, desc: defaultDesc };
    } else if (currentCode === defaultCode && !currentDesc && defaultDesc) {
      components[type] = { ...current, desc: defaultDesc };
    }
  }
  return { ...upsert, components };
}

export default function LotsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const materialId = searchParams.get("material_id") || "";
  const selectedTestId = searchParams.get("test_id") || "";
  const rawPage = Number(searchParams.get("page") || 1);
  const page = Number.isFinite(rawPage) ? Math.max(1, Math.floor(rawPage)) : 1;
  const rawPageSize = Number(searchParams.get("page_size") || 50);
  const pageSize = rawPageSize === 25 || rawPageSize === 100 ? rawPageSize : 50;
  const query = searchParams.get("q") || "";
  const rawDateField = searchParams.get("date_field");
  const dateField: LotsDateField = rawDateField === "prod_date" || rawDateField === "analysis_date" ? rawDateField : "request_date";
  const dateFrom = searchParams.get("date_from") || "";
  const dateTo = searchParams.get("date_to") || "";
  const rawStatus = searchParams.get("status");
  const status: LotsStatus = rawStatus === "completed" || rawStatus === "awaiting_production" || rawStatus === "awaiting_analysis" ? rawStatus : "all";
  const requestedSort = searchParams.get("sort_by") as LotsSortKey | null;
  const sortBy: LotsSortKey = requestedSort && LOTS_SORT_KEYS.includes(requestedSort) ? requestedSort : "latest";
  const sortDir = searchParams.get("sort_dir") === "asc" ? "asc" : "desc";
  const componentFilters = Object.fromEntries(
    (["iso", "pol", "cat", "add1", "add2"] as ComponentFilterKey[]).map((key) => [key, searchParams.get(key) || ""]),
  ) as Record<ComponentFilterKey, string>;
  const requestedQcField = searchParams.get("qc_field") as QcSortKey | null;
  const qcField = requestedQcField && QC_FIELDS.some((field) => field.key === requestedQcField) ? requestedQcField : "";
  const qcMinText = searchParams.get("qc_min") || "";
  const qcMaxText = searchParams.get("qc_max") || "";
  const parsedQcMin = qcMinText === "" ? undefined : Number(qcMinText);
  const parsedQcMax = qcMaxText === "" ? undefined : Number(qcMaxText);
  const [session, setSession] = useState<Session | null>(null);
  const [rows, setRows] = useState<LotsRow[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [queryInput, setQueryInput] = useState(query);
  const includeDeleted = searchParams.get("include_deleted") === "true";
  const [hasNext, setHasNext] = useState(false);
  const [total, setTotal] = useState(0);
  const [visibleColumns, setVisibleColumns] = useState<Set<ColumnKey>>(() => {
    try {
      const stored = JSON.parse(localStorage.getItem(COLUMN_STORAGE_KEY) || "[]") as string[];
      const valid = stored.filter((key): key is ColumnKey => COLUMN_DEFS.some((column) => column.key === key));
      if (valid.length) return new Set(valid);
    } catch { /* Use all columns when the saved preference is invalid. */ }
    return new Set(COLUMN_DEFS.map((column) => column.key));
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [modal, setModal] = useState<ModalState>({ open: false });
  const [form, setForm] = useState<LotUpsert>(() => emptyUpsert(""));

  const canEdit = !!session?.permissions?.can_edit_tests;

  function setSelection(key: string, value: string) {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "page") next.delete("page");
    setSearchParams(next);
  }

  async function refresh() {
    setErr(null);
    const r = await listLots({
      limit: pageSize,
      offset: (page - 1) * pageSize,
      includeDeleted,
      materialId: materialId || undefined,
      testId: selectedTestId || undefined,
      q: query || undefined,
      dateField,
      dateFrom: dateFrom || undefined,
      dateTo: dateTo || undefined,
      status,
      sortBy,
      sortDir,
      components: componentFilters,
      qcField: qcField || undefined,
      qcMin: parsedQcMin != null && Number.isFinite(parsedQcMin) ? parsedQcMin : undefined,
      qcMax: parsedQcMax != null && Number.isFinite(parsedQcMax) ? parsedQcMax : undefined,
    });
    setHasNext(r.has_next);
    setTotal(r.total);
    setRows(r.items);
  }

  useEffect(() => {
    me().then(setSession).catch(() => setSession(null));
    searchMaterials("").then(setMaterials).catch(() => setMaterials([]));
  }, []);

  useEffect(() => {
    refresh().catch((e) => setErr(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includeDeleted, materialId, selectedTestId, page, pageSize, query, dateField, dateFrom, dateTo, status, sortBy, sortDir, componentFilters.iso, componentFilters.pol, componentFilters.cat, componentFilters.add1, componentFilters.add2, qcField, qcMinText, qcMaxText]);

  useEffect(() => setQueryInput(query), [query]);

  useEffect(() => {
    if (queryInput === query) return;
    const timer = window.setTimeout(() => setSelection("q", queryInput.trim()), 300);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryInput, query]);

  useEffect(() => {
    if (selectedTestId) openEdit(selectedTestId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTestId]);

  function closeModal() {
    setModal({ open: false });
    const returnTo = searchParams.get("return_to");
    if (selectedTestId && returnTo && (returnTo === "/calendar" || returnTo.startsWith("/calendar?"))) {
      navigate(returnTo, { replace: true });
      return;
    }
    if (selectedTestId) setSelection("test_id", "");
  }

  function changeSort(nextSort: LotsSortKey) {
    const next = new URLSearchParams(searchParams);
    const nextDirection = sortBy === nextSort && sortDir === "asc" ? "desc" : "asc";
    next.set("sort_by", nextSort);
    next.set("sort_dir", nextDirection);
    next.delete("page");
    setSearchParams(next);
  }

  function clearBrowseFilters() {
    const next = new URLSearchParams(searchParams);
    ["material_id", "q", "date_field", "date_from", "date_to", "status", "include_deleted", "sort_by", "sort_dir", "page", "iso", "pol", "cat", "add1", "add2", "qc_field", "qc_min", "qc_max"].forEach((key) => next.delete(key));
    setSearchParams(next);
  }

  function toggleColumn(key: ColumnKey) {
    setVisibleColumns((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        if (next.size > 1) next.delete(key);
      } else next.add(key);
      localStorage.setItem(COLUMN_STORAGE_KEY, JSON.stringify([...next]));
      return next;
    });
  }

  async function openNew() {
    const first = materials.find((m) => m.material_id === materialId) || materials.find((m) => m.active) || materials[0];
    setForm(withMaterialDefaults(emptyUpsert(first?.material_id || ""), first));
    setModal({ open: true, mode: "new" });
  }

  function selectNewMaterial(nextMaterialId: ApiId) {
    setForm((current) => {
      const reset = emptyUpsert(nextMaterialId);
      reset.request_date = current.request_date;
      reset.prod_date = current.prod_date;
      reset.analysis_date = current.analysis_date;
      reset.qc = current.qc;
      return withMaterialDefaults(reset, materials.find((material) => material.material_id === nextMaterialId));
    });
  }

  async function openEdit(testId: ApiId) {
    setBusy(true);
    setErr(null);
    try {
      const d = await getLotDetails(testId);
      const payload: LotUpsert = {
        material_id: d.material_id,
        request_date: d.request_date || "",
        prod_date: d.prod_date || "",
        analysis_date: d.analysis_date || "",
        components: { ...d.components },
        qc: { ...d.qc },
      };
      for (const t of COMPONENT_TYPES) payload.components![t] = payload.components![t] || { code: "", desc: "", lot: "" };
      for (const f of QC_FIELDS) payload.qc![f.key] = payload.qc![f.key] || "";
      setForm(payload);
      setModal({ open: true, mode: "edit", testId });
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onSave() {
    if (!canEdit) return;
    setBusy(true);
    setErr(null);
    try {
      const payload: LotUpsert = {
        ...form,
        request_date: form.request_date || null,
        prod_date: form.prod_date || null,
        analysis_date: form.analysis_date || null,
      };

      let _res: LotDetails;
      if (modal.open && modal.mode === "edit") _res = await updateLot(modal.testId, payload);
      else _res = await createLot(payload);
      closeModal();
      await refresh();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(testId: ApiId) {
    if (!canEdit) return;
    if (!confirm(`Delete test ${testId}? This cannot be undone.`)) return;
    setBusy(true);
    setErr(null);
    try {
      await deleteLot(testId);
      await refresh();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  function clearFilter(keys: string[]) {
    const next = new URLSearchParams(searchParams);
    keys.forEach((key) => next.delete(key));
    next.delete("page");
    setSearchParams(next);
  }

  const activeFilters: Array<{ key: string; label: string; clear: string[] }> = [];
  if (query) activeFilters.push({ key: "q", label: `Search: ${query}`, clear: ["q"] });
  if (materialId) activeFilters.push({ key: "material", label: `Material: ${materials.find((item) => item.material_id === materialId)?.code || materialId}`, clear: ["material_id"] });
  if (dateFrom || dateTo) activeFilters.push({ key: "dates", label: `${dateField.replace("_date", "").replace("prod", "production")}: ${dateFrom || "…"} – ${dateTo || "…"}`, clear: ["date_field", "date_from", "date_to"] });
  if (status !== "all") activeFilters.push({ key: "status", label: status.replaceAll("_", " "), clear: ["status"] });
  (Object.entries(componentFilters) as Array<[ComponentFilterKey, string]>).forEach(([key, value]) => {
    if (value) activeFilters.push({ key, label: `${key.toUpperCase()}: ${value}`, clear: [key] });
  });
  if (qcField && (qcMinText || qcMaxText)) {
    const label = QC_FIELDS.find((field) => field.key === qcField)?.label || qcField;
    activeFilters.push({ key: "qc", label: `${label}: ${qcMinText || "−∞"} – ${qcMaxText || "+∞"}`, clear: ["qc_field", "qc_min", "qc_max"] });
  }
  if (includeDeleted) activeFilters.push({ key: "deleted", label: "Including deleted", clear: ["include_deleted"] });

  return (
    <div className="card">
      <h2 className="title">Lots / results</h2>
      <div className="row" style={{ marginBottom: 10 }}>
        <button className="btn" onClick={() => refresh().catch((e) => setErr(String(e)))} disabled={busy}>
          Refresh
        </button>
        <button className="btn primary" onClick={openNew} disabled={!canEdit || busy || !materials.length}>
          Add
        </button>
        <label className="pill" style={{ cursor: "pointer" }}>
          <input
            style={{ marginRight: 6 }}
            type="checkbox"
            checked={includeDeleted}
            onChange={(e) => setSelection("include_deleted", e.target.checked ? "true" : "")}
            disabled={busy}
          />
          Include deleted
        </label>
        <select className="input" aria-label="Filter by material" value={materialId} onChange={(e) => setSelection("material_id", e.target.value)}>
          <option value="">All materials</option>
          {materials.map((m) => (
            <option key={m.material_id} value={m.material_id}>
              {m.code}{m.description ? ` — ${m.description}` : ""}
            </option>
          ))}
        </select>
        <input className="input" type="search" aria-label="Search all lots" placeholder="Search all lots…" value={queryInput} onChange={(e) => setQueryInput(e.target.value)} />
        {!canEdit && <span className="muted">Read-only</span>}
      </div>

      <div className="row lots-filter-row" aria-label="Advanced filters">
        <select className="input" aria-label="Date field" value={dateField} onChange={(e) => setSelection("date_field", e.target.value)}>
          <option value="request_date">Request date</option>
          <option value="prod_date">Production date</option>
          <option value="analysis_date">Analysis date</option>
        </select>
        <label className="date-filter-label">From <input className="input" type="date" aria-label="Date from" value={dateFrom} onChange={(e) => setSelection("date_from", e.target.value)} /></label>
        <label className="date-filter-label">To <input className="input" type="date" aria-label="Date to" value={dateTo} onChange={(e) => setSelection("date_to", e.target.value)} /></label>
        <select className="input" aria-label="Completion status" value={status} onChange={(e) => setSelection("status", e.target.value)}>
          <option value="all">All statuses</option>
          <option value="completed">Completed</option>
          <option value="awaiting_production">Awaiting production</option>
          <option value="awaiting_analysis">Awaiting analysis</option>
        </select>
        {(Object.keys(componentFilters) as ComponentFilterKey[]).map((key) => (
          <input
            key={key}
            className="input component-filter-input"
            aria-label={`${key.toUpperCase()} code`}
            placeholder={`${key.toUpperCase()} code`}
            value={componentFilters[key]}
            onChange={(e) => setSelection(key, e.target.value)}
          />
        ))}
        <select className="input" aria-label="QC property" value={qcField} onChange={(e) => setSelection("qc_field", e.target.value)}>
          <option value="">QC property…</option>
          {QC_FIELDS.map((field) => <option key={field.key} value={field.key}>{field.label}</option>)}
        </select>
        <input className="input qc-range-input" type="number" step="any" aria-label="QC minimum" placeholder="QC min" value={qcMinText} disabled={!qcField} onChange={(e) => setSelection("qc_min", e.target.value)} />
        <input className="input qc-range-input" type="number" step="any" aria-label="QC maximum" placeholder="QC max" value={qcMaxText} disabled={!qcField} onChange={(e) => setSelection("qc_max", e.target.value)} />
        <button className="btn" type="button" onClick={clearBrowseFilters}>Clear filters</button>
      </div>

      <div className="row lots-table-tools">
        {activeFilters.length > 0 && <div className="active-filter-list" aria-label="Active filters">
          {activeFilters.map((filter) => (
            <button key={filter.key} className="pill active-filter" type="button" onClick={() => clearFilter(filter.clear)} aria-label={`Remove ${filter.label} filter`}>
              {filter.label} <span aria-hidden="true">×</span>
            </button>
          ))}
        </div>}
        <div className="spacer" />
        <details className="column-picker">
          <summary className="btn">Columns</summary>
          <div className="card column-picker-menu">
            {COLUMN_DEFS.map((column) => (
              <label key={column.key}>
                <input type="checkbox" checked={visibleColumns.has(column.key)} onChange={() => toggleColumn(column.key)} /> {column.label}
              </label>
            ))}
          </div>
        </details>
      </div>

      {err && (
        <div className="pill" style={{ color: "var(--danger)" }}>
          {err}
        </div>
      )}

      <div style={{ overflowX: "auto" }}>
        <table className="table lots-results-table">
          <thead>
            <tr>
              {visibleColumns.has("request_date") && <SortHeader label="Request" sortKey="request_date" current={sortBy} direction={sortDir} onSort={changeSort} />}
              {visibleColumns.has("prod_date") && <SortHeader label="Prod" sortKey="prod_date" current={sortBy} direction={sortDir} onSort={changeSort} />}
              {visibleColumns.has("analysis_date") && <SortHeader label="Analysis" sortKey="analysis_date" current={sortBy} direction={sortDir} onSort={changeSort} />}
              {visibleColumns.has("material") && <SortHeader label="Material" sortKey="material" current={sortBy} direction={sortDir} onSort={changeSort} />}
              {visibleColumns.has("lastrina") && <SortHeader label="Lastrina" sortKey="lastrina" current={sortBy} direction={sortDir} onSort={changeSort} />}
              {visibleColumns.has("iso") && <SortHeader label="ISO" sortKey="iso" current={sortBy} direction={sortDir} onSort={changeSort} />}
              {visibleColumns.has("pol") && <SortHeader label="POL" sortKey="pol" current={sortBy} direction={sortDir} onSort={changeSort} />}
              {visibleColumns.has("cat") && <SortHeader label="CAT" sortKey="cat" current={sortBy} direction={sortDir} onSort={changeSort} />}
              {visibleColumns.has("add1") && <SortHeader label="ADD1" sortKey="add1" current={sortBy} direction={sortDir} onSort={changeSort} />}
              {visibleColumns.has("add2") && <SortHeader label="ADD2" sortKey="add2" current={sortBy} direction={sortDir} onSort={changeSort} />}
              {QC_FIELDS.filter((f) => visibleColumns.has(f.key)).map((f) => (
                <SortHeader key={f.key} label={f.label} sortKey={f.key} current={sortBy} direction={sortDir} onSort={changeSort} />
              ))}
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.test_id}>
                {visibleColumns.has("request_date") && <td>{r.request_date || "—"}</td>}
                {visibleColumns.has("prod_date") && <td>{r.prod_date || "—"}</td>}
                {visibleColumns.has("analysis_date") && <td>{r.analysis_date || "—"}</td>}
                {visibleColumns.has("material") && <td title={r.material_desc || undefined}>{r.material_code}</td>}
                {visibleColumns.has("lastrina") && <td>{r.lastrina_code || "—"}</td>}
                {visibleColumns.has("iso") && <td>{r.iso_code || "—"}</td>}
                {visibleColumns.has("pol") && <td>{r.pol_code || "—"}</td>}
                {visibleColumns.has("cat") && <td>{r.cat_code || "—"}</td>}
                {visibleColumns.has("add1") && <td>{r.add1_code || "—"}</td>}
                {visibleColumns.has("add2") && <td>{r.add2_code || "—"}</td>}
                {visibleColumns.has("durezza") && <td>{r.durezza || "—"}</td>}
                {visibleColumns.has("carico_rottura") && <td>{r.carico_rottura || "—"}</td>}
                {visibleColumns.has("allungamento") && <td>{r.allungamento || "—"}</td>}
                {visibleColumns.has("lacerazione_ba") && <td>{r.lacerazione_ba || "—"}</td>}
                {visibleColumns.has("lacerazione_ca") && <td>{r.lacerazione_ca || "—"}</td>}
                {visibleColumns.has("abrasione") && <td>{r.abrasione || "—"}</td>}
                {visibleColumns.has("resistivita_superficiale") && <td>{r.resistivita_superficiale || "—"}</td>}
                <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                  <button className="btn" disabled={busy} onClick={() => setSelection("test_id", r.test_id)}>
                    View
                  </button>{" "}
                  <Link to={qcHref("charts", { materialId: r.material_id })}>Charts</Link>{" · "}
                  <Link to={qcHref("ratings", { materialId: r.material_id })}>Ratings</Link>{" · "}
                  <Link to={qcHref("calendar", { materialId: r.material_id, testId: r.test_id, prodDate: r.prod_date })}>Calendar</Link>{" "}
                  <button className="btn danger" disabled={busy || !canEdit} onClick={() => onDelete(r.test_id)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
            {!rows.length && (
              <tr>
                <td colSpan={visibleColumns.size + 1} className="muted">
                  No data
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="row" style={{ marginTop: 10 }}>
        <button className="btn" disabled={page <= 1} onClick={() => setSelection("page", String(page - 1))}>Previous</button>
        <span className="pill">Page {page} of {Math.max(1, Math.ceil(total / pageSize))}</span>
        <button className="btn" disabled={!hasNext} onClick={() => setSelection("page", String(page + 1))}>Next</button>
        <span className="muted">{total === 0 ? "No matching tests" : `Showing ${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} of ${total}`}</span>
        <label className="date-filter-label">Rows
          <select className="input page-size-select" aria-label="Rows per page" value={pageSize} onChange={(e) => setSelection("page_size", e.target.value)}>
            <option value="25">25</option><option value="50">50</option><option value="100">100</option>
          </select>
        </label>
      </div>

      {modal.open && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 20,
          }}
          onClick={() => !busy && closeModal()}
        >
          <div className="card lot-modal" role="dialog" aria-modal="true" aria-label={modal.mode === "new" ? "New lot or result" : `Edit test ${modal.testId}`} style={{ width: "min(1100px, 95vw)", maxHeight: "90vh", overflow: "auto" }} onClick={(e) => e.stopPropagation()}>
            <div className="row" style={{ marginBottom: 10 }}>
              <div style={{ fontWeight: 700, fontSize: 16 }}>
                {modal.mode === "new" ? "New lot/result" : `Edit ${modal.testId}`}
              </div>
              <div className="spacer" />
              <button className="btn" disabled={busy} onClick={closeModal}>
                Close
              </button>
              <button className="btn primary" disabled={busy || !canEdit || !form.material_id} onClick={onSave}>
                Save
              </button>
            </div>

            <div className="row" style={{ marginBottom: 10 }}>
              <select
                className="input"
                value={form.material_id || ""}
                onChange={(e) => {
                  const nextMaterialId = e.target.value;
                  if (modal.mode === "new") selectNewMaterial(nextMaterialId);
                  else setForm((p) => ({ ...p, material_id: nextMaterialId }));
                }}
                disabled={busy || !canEdit}
              >
                <option value="">Select material…</option>
                {materials
                  .filter((m) => m.active)
                  .map((m) => (
                    <option key={m.material_id} value={m.material_id}>
                      {m.code}
                      {m.description ? ` — ${m.description}` : ""}
                    </option>
                  ))}
              </select>
              <label className="date-filter-label">
                Request
                <input
                  className="input"
                  type="date"
                  value={(form.request_date as any) || ""}
                  onChange={(e) => setForm((p) => ({ ...p, request_date: e.target.value }))}
                  disabled={busy || !canEdit}
                />
              </label>
              <label className="date-filter-label">
                Prod
                <input
                  className="input"
                  type="date"
                  value={(form.prod_date as any) || ""}
                  onChange={(e) => setForm((p) => ({ ...p, prod_date: e.target.value }))}
                  disabled={busy || !canEdit}
                />
              </label>
              <label className="date-filter-label">
                Analysis
                <input
                  className="input"
                  type="date"
                  value={(form.analysis_date as any) || ""}
                  onChange={(e) => setForm((p) => ({ ...p, analysis_date: e.target.value }))}
                  disabled={busy || !canEdit}
                />
              </label>
            </div>

            <div className="row" style={{ marginBottom: 10, alignItems: "flex-start" }}>
              <div style={{ flex: 1 }}>
                <div className="pill" style={{ marginBottom: 8 }}>
                  Components
                </div>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Type</th>
                      <th>Code</th>
                      <th>Description</th>
                      <th>Lot</th>
                    </tr>
                  </thead>
                  <tbody>
                    {COMPONENT_TYPES.map((t) => (
                      <tr key={t}>
                        <td>{t}</td>
                        <td>
                          <input
                            className="input"
                            style={{ minWidth: 120 }}
                            value={(form.components?.[t]?.code as any) || ""}
                            onChange={(e) =>
                              setForm((p) => ({
                                ...p,
                                components: { ...(p.components || {}), [t]: { ...(p.components?.[t] || {}), code: e.target.value } },
                              }))
                            }
                            disabled={busy || !canEdit}
                          />
                        </td>
                        <td>
                          <input
                            className="input"
                            style={{ minWidth: 320 }}
                            value={(form.components?.[t]?.desc as any) || ""}
                            onChange={(e) =>
                              setForm((p) => ({
                                ...p,
                                components: { ...(p.components || {}), [t]: { ...(p.components?.[t] || {}), desc: e.target.value } },
                              }))
                            }
                            disabled={busy || !canEdit}
                          />
                        </td>
                        <td>
                          <input
                            className="input"
                            style={{ minWidth: 160 }}
                            value={(form.components?.[t]?.lot as any) || ""}
                            onChange={(e) =>
                              setForm((p) => ({
                                ...p,
                                components: { ...(p.components || {}), [t]: { ...(p.components?.[t] || {}), lot: e.target.value } },
                              }))
                            }
                            disabled={busy || !canEdit}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div style={{ flex: 1 }}>
                <div className="pill" style={{ marginBottom: 8 }}>
                  QC
                </div>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Property</th>
                      <th>Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {QC_FIELDS.map((f) => (
                      <tr key={f.key}>
                        <td>{f.label}</td>
                        <td>
                          <input
                            className="input"
                            style={{ minWidth: 180 }}
                            value={(form.qc?.[f.key] as any) || ""}
                            onChange={(e) => setForm((p) => ({ ...p, qc: { ...(p.qc || {}), [f.key]: e.target.value } }))}
                            disabled={busy || !canEdit}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {!canEdit && <div className="muted">Your role cannot edit tests.</div>}
          </div>
        </div>
      )}
    </div>
  );
}
