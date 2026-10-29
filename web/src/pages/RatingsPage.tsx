import Plot from "react-plotly.js";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { qcHref } from "../features/qcLinks";
import { useQuery } from "@tanstack/react-query";
import type { ApiId } from "../api/client";
import { searchMaterials } from "../api/materials";
import { ratingsOverview } from "../api/ratings";
import { EmptyNotice, ErrorNotice, LoadingNotice } from "../components/AsyncState";
import { chartTheme, useTheme } from "../theme";


function ratingColor(value: number): string {
  if (value < 50) return "#ff5a6f";
  if (value < 75) return "#ffd24d";
  return "#55d6a7";
}


function RatingGauge({ title, value }: { title: string; value: number | null }) {
  const { theme } = useTheme();
  const colors = chartTheme(theme);
  if (value == null) {
    return (
      <div className="card" style={{ minHeight: 260 }}>
        <h3 style={{ margin: 0 }}>{title}</h3>
        <div className="muted" style={{ marginTop: 90, textAlign: "center" }}>
          No data
        </div>
      </div>
    );
  }

  const bounded = Math.max(0, Math.min(100, value));
  return (
    <div className="card" style={{ minHeight: 260 }}>
      <h3 style={{ margin: 0 }}>{title}</h3>
      <Plot
        data={[
          {
            type: "pie",
            values: [bounded, 100 - bounded],
            labels: ["Rating", "Remaining"],
            hole: 0.72,
            sort: false,
            direction: "clockwise",
            textinfo: "none",
            hoverinfo: "label+value",
            marker: { colors: [ratingColor(bounded), colors.remainder] },
          },
        ] as any}
        layout={{
          autosize: true,
          paper_bgcolor: "rgba(0,0,0,0)",
          plot_bgcolor: "rgba(0,0,0,0)",
          font: { color: colors.text },
          showlegend: false,
          margin: { l: 15, r: 15, t: 10, b: 10 },
          annotations: [
            {
              text: `<b>${value.toFixed(1)}%</b>`,
              showarrow: false,
              font: { color: colors.text, size: 24 },
            },
          ],
        } as any}
        style={{ width: "100%", height: 210 }}
        config={{ displayModeBar: false, displaylogo: false, responsive: true }}
      />
    </div>
  );
}


export default function RatingsPage() {
  const { theme } = useTheme();
  const colors = chartTheme(theme);
  const [searchParams, setSearchParams] = useSearchParams();
  const materialId = searchParams.get("material_id") || "";
  const dateFrom = searchParams.get("date_from") || "";
  const dateTo = searchParams.get("date_to") || "";
  const [smooth, setSmooth] = useState(true);
  const materialsQuery = useQuery({
    queryKey: ["materials", "active"],
    queryFn: () => searchMaterials(""),
  });
  const materials = (materialsQuery.data || []).filter((material) => material.active);
  const ratingsQuery = useQuery({
    queryKey: ["ratings", materialId, dateFrom, dateTo],
    queryFn: () => ratingsOverview(materialId, dateFrom || undefined, dateTo || undefined),
    enabled: materialId.length > 0,
  });
  const data = ratingsQuery.data || null;
  const busy = materialsQuery.isPending || ratingsQuery.isFetching;
  const queryError = materialsQuery.error || ratingsQuery.error;

  useEffect(() => {
    if (!materialId && materials.length) {
      setSearchParams({ material_id: String(materials[0].material_id) }, { replace: true });
    }
  }, [materialId, materials, setSearchParams]);

  useEffect(() => {
    if (data && ((!dateFrom && data.date_from) || (!dateTo && data.date_to))) {
      const next = new URLSearchParams(searchParams);
      if (!dateFrom && data.date_from) next.set("date_from", data.date_from);
      if (!dateTo && data.date_to) next.set("date_to", data.date_to);
      setSearchParams(next, { replace: true });
    }
  }, [data, dateFrom, dateTo, searchParams, setSearchParams]);

  function selectMaterial(nextMaterialId: ApiId) {
    if (!nextMaterialId) {
      setSearchParams({});
      return;
    }
    setSearchParams({ material_id: String(nextMaterialId) });
  }

  function setDate(key: "date_from" | "date_to", value: string) {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next);
  }

  const points = data?.points || [];
  return (
    <div className="card">
      <h2 className="title">Ratings</h2>
      <div className="row" style={{ marginBottom: 14 }}>
        <label>
          <span className="muted" style={{ display: "block", fontSize: 12, marginBottom: 4 }}>
            Material
          </span>
          <select className="input" value={materialId} onChange={(event) => selectMaterial(event.target.value)}>
            <option value="">Select material…</option>
            {materials.map((material) => (
              <option key={material.material_id} value={material.material_id}>
                {material.code}{material.description ? ` — ${material.description}` : ""}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="muted" style={{ display: "block", fontSize: 12, marginBottom: 4 }}>
            From
          </span>
          <input
            className="input"
            type="date"
            min={data?.date_min || undefined}
            max={data?.date_max || undefined}
            value={dateFrom}
            onChange={(event) => setDate("date_from", event.target.value)}
          />
        </label>
        <label>
          <span className="muted" style={{ display: "block", fontSize: 12, marginBottom: 4 }}>
            To
          </span>
          <input
            className="input"
            type="date"
            min={data?.date_min || undefined}
            max={data?.date_max || undefined}
            value={dateTo}
            onChange={(event) => setDate("date_to", event.target.value)}
          />
        </label>
        <label className="pill" style={{ cursor: "pointer" }}>
          <input type="checkbox" checked={smooth} onChange={(event) => setSmooth(event.target.checked)} style={{ marginRight: 6 }} />
          Smoothing
        </label>
        <span className="pill">{busy ? "Loading…" : `${points.length} tests`}</span>
      </div>

      {materialId && <div className="row" style={{ marginBottom: 12 }}>
        <Link to={qcHref("sinottico", { materialId })}>Sinottico</Link>
        <Link to={qcHref("lots", { materialId })}>Lots</Link>
        <Link to={qcHref("charts", { materialId })}>Charts</Link>
        <Link to={qcHref("calendar", { materialId })}>Calendar</Link>
      </div>}

      {queryError && <ErrorNotice error={queryError} />}
      {busy && !data && <LoadingNotice>Loading ratings…</LoadingNotice>}
      {!materialsQuery.isPending && !materialId && <EmptyNotice>Select a material to load ratings.</EmptyNotice>}
      {data && !data.configured && (
        <EmptyNotice>No rating rule or saved tolerance has a positive property weight.</EmptyNotice>
      )}
      {data?.configured && !busy && !points.length && (
        <EmptyNotice>No rated tests are available for this date range.</EmptyNotice>
      )}

      {data?.configured && points.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(280px, 1fr))", gap: 12 }}>
          <RatingGauge title="Last test" value={data.latest_rating} />
          <RatingGauge title="Average" value={data.average_rating} />
          <div className="card" style={{ gridColumn: "1 / -1" }}>
            <h3 style={{ margin: 0 }}>Overall</h3>
            <Plot
              data={[
                {
                  type: "scatter",
                  mode: "lines+markers",
                  name: "Rating",
                  x: points.map((point) => point.date),
                  y: points.map((point) => point.rating_percent),
                  line: { color: "#4f86ff", width: 2, shape: smooth && points.length >= 3 ? "spline" : "linear", smoothing: 0.6 },
                  marker: { color: points.map((point) => ratingColor(point.rating_percent)), size: 8 },
                  hovertemplate: "%{x}<br>%{y:.1f}%<extra></extra>",
                },
              ] as any}
              layout={{
                autosize: true,
                paper_bgcolor: "rgba(0,0,0,0)",
                plot_bgcolor: "rgba(0,0,0,0)",
                font: { color: colors.text },
                margin: { l: 50, r: 20, t: 20, b: 45 },
                xaxis: { gridcolor: colors.grid, type: "date" },
                yaxis: { gridcolor: colors.grid, range: [0, 100], ticksuffix: "%" },
                showlegend: false,
              } as any}
              style={{ width: "100%", height: 380 }}
              config={{ displaylogo: false, responsive: true }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
