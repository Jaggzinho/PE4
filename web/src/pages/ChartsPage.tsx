import { DateInput } from "../components/DateInput";
import Plot from "react-plotly.js";
import type { Data } from "plotly.js";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { qcHref } from "../features/qcLinks";
import { useMaterialSelection } from "../features/useMaterialSelection";
import { chartsPanels, searchMaterials, type ChartPanel, type ChartsPanels, type Material } from "../api";
import { chartTheme, useTheme } from "../theme";

function todayIso(): string {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

type XRange = { from: string; to: string } | null;

function panelColor(kind: string, averageColor: string): string {
  if (kind === "avg") return averageColor;
  if (kind === "reference") return "rgba(91, 196, 154, 0.95)";
  if (kind === "warn") return "rgba(255, 210, 77, 0.85)";
  if (kind === "alarm") return "rgba(255, 90, 111, 0.90)";
  return "rgba(79, 134, 255, 0.95)";
}

function panelDash(kind: string): "solid" | "dash" | "dot" {
  if (kind === "warn") return "dash";
  if (kind === "alarm") return "solid";
  if (kind === "avg") return "dot";
  if (kind === "reference") return "dot";
  return "solid";
}

export default function ChartsPage() {
  const { theme } = useTheme();
  const colors = chartTheme(theme);
  const { materialId, searchParams, setSearchParams } = useMaterialSelection("charts");
  const dateFrom = searchParams.get("date_from") || "";
  const dateTo = searchParams.get("date_to") || todayIso();
  const [materials, setMaterials] = useState<Material[]>([]);

  function setSelection(key: string, value: string) {
    const next = new URLSearchParams(searchParams);
    if (value || key === "material_id") next.set(key, value);
    else next.delete(key);
    setSearchParams(next);
  }

  const [smooth, setSmooth] = useState(true);
  const [avg, setAvg] = useState(true);
  const [tolerances, setTolerances] = useState(true);

  const [data, setData] = useState<ChartsPanels | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [hoverX, setHoverX] = useState<string | null>(null);
  const [xRange, setXRange] = useState<XRange>(null);
  const [hiddenTraces, setHiddenTraces] = useState<Set<string>>(() => new Set());
  const relayoutGuard = useRef(false);

  useEffect(() => {
    searchMaterials("").then(setMaterials).catch(() => setMaterials([]));
  }, []);

  useEffect(() => {
    if (!materialId) return;
    let alive = true;
    setBusy(true);
    setErr(null);
    chartsPanels({
      material_id: materialId,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      smooth,
      avg,
      tolerances,
    })
      .then((r) => alive && setData(r))
      .catch((e) => alive && setErr(String(e)))
      .finally(() => alive && setBusy(false));
    return () => {
      alive = false;
    };
  }, [materialId, dateFrom, dateTo, smooth, avg, tolerances]);

  const panels: ChartPanel[] = useMemo(() => data?.panels || [], [data]);
  const legendTraces = useMemo(() => {
    const traces = new Map<string, ChartPanel["traces"][number]>();
    for (const panel of panels) {
      for (const trace of panel.traces) {
        traces.set(`${trace.kind}:${trace.name}`, trace);
      }
    }
    return [...traces.entries()];
  }, [panels]);

  function toggleTrace(key: string) {
    setHiddenTraces((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function sharedLayout(panel: ChartPanel) {
    const shapes: any[] = [];
    if (hoverX) {
      shapes.push({
        type: "line",
        x0: hoverX,
        x1: hoverX,
        y0: 0,
        y1: 1,
        xref: "x",
        yref: "paper",
        line: { color: colors.guide, width: 1, dash: "dot" },
      });
    }
    return {
      autosize: true,
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { color: colors.text },
      xaxis: {
        gridcolor: colors.grid,
        type: "date",
        tickformat: "%d-%m-%Y",
        hoverformat: "%d-%m-%Y",
        title: { text: "Request date" },
        range: xRange ? [xRange.from, xRange.to] : undefined,
      },
      yaxis: { gridcolor: colors.grid },
      showlegend: false,
      margin: { l: 50, r: 20, t: 20, b: 40 },
      shapes,
      title: { text: panel.title, font: { size: 13 } },
    };
  }

  function plotData(panel: ChartPanel) {
    return (panel.traces || []).flatMap<Data>((t) => {
      const visible = hiddenTraces.has(`${t.kind}:${t.name}`) ? "legendonly" as const : true;
      const lineTrace = {
        type: "scatter" as const,
        mode: "lines" as const,
        name: t.name,
        visible,
        x: t.x,
        y: t.y,
        line: { color: panelColor(t.kind, colors.average), dash: panelDash(t.kind), width: t.kind === "series" ? 2 : 1.5 },
        marker: { color: panelColor(t.kind, colors.average), size: 6, symbol: "circle" as const },
        hoverinfo: t.kind === "series" ? "skip" as const : "x+y+name" as const,
      };
      if (t.kind !== "series") return [lineTrace];
      return [lineTrace, {
        ...lineTrace,
        mode: "markers" as const,
        x: t.measured_x,
        y: t.measured_y,
        hoverinfo: "x+y+name" as const,
      }];
    });
  }

  function onHover(ev: any) {
    const pt = ev?.points?.[0];
    if (!pt) return;
    const x = String(pt.x || "");
    if (!x) return;
    setHoverX(x);
  }

  function onUnhover() {
    setHoverX(null);
  }

  function onRelayout(ev: any) {
    if (!ev || relayoutGuard.current) return;
    const from = ev["xaxis.range[0]"] || ev["xaxis.range"]?.[0];
    const to = ev["xaxis.range[1]"] || ev["xaxis.range"]?.[1];
    if (from && to) {
      relayoutGuard.current = true;
      setXRange({ from: String(from), to: String(to) });
      setTimeout(() => {
        relayoutGuard.current = false;
      }, 0);
    }
    if (ev["xaxis.autorange"]) setXRange(null);
  }

  return (
    <div className="card">
      <h2 className="title">Charts</h2>
      <div className="row" style={{ marginBottom: 12 }}>
        <select className="input" aria-label="Chart material" value={materialId} onChange={(e) => setSelection("material_id", e.target.value)}>
          <option value="">Select material…</option>
          {materials
            .filter((m) => m.active)
            .map((m) => (
              <option key={m.material_id} value={m.material_id}>
                {m.code}{m.description ? ` — ${m.description}` : ""}
              </option>
            ))}
        </select>
        <DateInput className="input" aria-label="Chart from date"  value={dateFrom} onValueChange={(iso) => setSelection("date_from", iso)} />
        <DateInput className="input" aria-label="Chart to date"  value={dateTo} onValueChange={(iso) => setSelection("date_to", iso)} />
        <label className="pill" style={{ cursor: "pointer" }}>
          <input style={{ marginRight: 6 }} type="checkbox" checked={smooth} onChange={(e) => setSmooth(e.target.checked)} /> Smoothing
        </label>
        <label className="pill" style={{ cursor: "pointer" }}>
          <input style={{ marginRight: 6 }} type="checkbox" checked={avg} onChange={(e) => setAvg(e.target.checked)} /> Average
        </label>
        <label className="pill" style={{ cursor: "pointer" }}>
          <input style={{ marginRight: 6 }} type="checkbox" checked={tolerances} onChange={(e) => setTolerances(e.target.checked)} /> Tolerances
        </label>
        <span className="pill">{busy ? "Loading…" : "Plotly"}</span>
        <button className="btn" disabled={!xRange} onClick={() => setXRange(null)}>
          Reset zoom
        </button>
      </div>
      {materialId && <div className="row" style={{ marginBottom: 10 }}>
        <Link to={qcHref("sinottico", { materialId })}>Sinottico</Link>
        <Link to={qcHref("lots", { materialId })}>Lots</Link>
        <Link to={qcHref("ratings", { materialId })}>Ratings</Link>
        <Link to={qcHref("calendar", { materialId })}>Calendar</Link>
      </div>}
      {err && (
        <div className="pill" style={{ color: "var(--danger)" }}>
          {err}
        </div>
      )}
      {!materialId && <div className="muted">Pick a material to load chart panels.</div>}

      {!!materialId && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, minmax(280px, 1fr))",
            gap: 10,
          }}
        >
          {panels.map((p, idx) => (
            <div key={`${p.title}-${idx}`} className="card" style={{ padding: 8 }}>
              <Plot
                data={plotData(p) as any}
                layout={sharedLayout(p) as any}
                style={{ width: "100%", height: "260px" }}
                config={{ displaylogo: false, responsive: true }}
                onHover={onHover as any}
                onUnhover={onUnhover as any}
                onRelayout={onRelayout as any}
              />
            </div>
          ))}
        </div>
      )}
      {!!materialId && legendTraces.length > 0 && (
        <div role="group" aria-label="Chart legend" style={{ marginTop: 10, fontSize: 12, display: "flex", flexWrap: "wrap", justifyContent: "center", gap: "8px 20px" }}>
          {legendTraces.map(([key, trace]) => (
            <button
              key={key}
              type="button"
              aria-pressed={!hiddenTraces.has(key)}
              title={`Show or hide ${trace.name} across all charts`}
              onClick={() => toggleTrace(key)}
              style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "4px 6px", border: 0, background: "transparent", color: colors.text, font: "inherit", cursor: "pointer", opacity: hiddenTraces.has(key) ? 0.45 : 1 }}
            >
              <svg width="32" height="12" aria-hidden="true">
                <line x1="1" y1="6" x2="31" y2="6" stroke={panelColor(trace.kind, colors.average)} strokeWidth={trace.kind === "series" ? 2 : 1.5} strokeDasharray={panelDash(trace.kind) === "dash" ? "9 9" : panelDash(trace.kind) === "dot" ? "3 3" : undefined} />
                {trace.kind === "series" && <circle cx="16" cy="6" r="3" fill={panelColor(trace.kind, colors.average)} />}
              </svg>
              {trace.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
