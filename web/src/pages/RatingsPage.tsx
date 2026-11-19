import { getEnvironmentId } from "../api/client";
import { DateInput } from "../components/DateInput";
import Plot from "react-plotly.js";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { qcHref } from "../features/qcLinks";
import { useComparison, ComparisonControls, ComparisonLegend, materialCode, materialDescription, materialColors, toggleMaterial } from "../features/materialComparison";
import { ratingColor } from "../features/ratingColor";
import { useQueries, useQuery } from "@tanstack/react-query";
import { searchMaterials } from "../api/materials";
import { ratingsOverview } from "../api/ratings";
import { EmptyNotice, ErrorNotice, LoadingNotice } from "../components/AsyncState";
import { chartTheme, useTheme } from "../theme";


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
  const comparison = useComparison();
  const { materialId, searchParams, setSearchParams, ids, extras, comparing } = comparison;
  const dateFrom = searchParams.get("date_from") || "";
  const dateTo = searchParams.get("date_to") || "";
  const [smooth, setSmooth] = useState(true);
  const materialsQuery = useQuery({
    queryKey: [getEnvironmentId(), "materials", "active"],
    queryFn: () => searchMaterials(""),
  });
  const materials = (materialsQuery.data || []).filter((material) => material.active);
  const [hidden, setHidden] = useState<Set<string>>(() => new Set());
  const queries = useQueries({ queries: ids.map(id => ({
    queryKey: [getEnvironmentId(), "ratings", id, dateFrom, dateTo, comparing],
    queryFn: () => ratingsOverview(id, dateFrom || undefined, dateTo || undefined, comparing),
  })) });
  const entries = ids.map((id, index) => ({
    id, name: materialCode(materials, id), color: materialColors[index], query: queries[index],
  }));
  const plotted = entries.filter(({ query }) => query.data?.configured && query.data.points.length);
  const data = comparing ? null : queries[0]?.data ?? null;
  const busy = materialsQuery.isPending || queries.some(query => query.isFetching);
  const queryError = materialsQuery.error || (!comparing && queries[0]?.error);

  useEffect(() => {
    if (data && ((!dateFrom && data.date_from) || (!dateTo && data.date_to))) {
      const next = new URLSearchParams(searchParams);
      if (!dateFrom && data.date_from) next.set("date_from", data.date_from);
      if (!dateTo && data.date_to) next.set("date_to", data.date_to);
      setSearchParams(next, { replace: true });
    }
  }, [data, dateFrom, dateTo, searchParams, setSearchParams]);

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
          <select className="input" value={materialId} onChange={(event) => {
            if (comparing) comparison.update(event.target.value, extras);
            else setSearchParams({ material_id: event.target.value });
          }}>
            <option value="">Select material…</option>
            {materials.map((material) => (
              <option key={material.material_id} value={material.material_id}>
                {material.code}{material.description ? ` — ${material.description}` : ""}
              </option>
            ))}
          </select>
        </label>
        <ComparisonControls selection={comparison} materials={materials} />
        <label>
          <span className="muted" style={{ display: "block", fontSize: 12, marginBottom: 4 }}>
            From
          </span>
          <DateInput
            className="input"
            min={data?.date_min || undefined}
            max={data?.date_max || undefined}
            aria-label="From"
            value={dateFrom}
            onValueChange={(iso) => setDate("date_from", iso)}
          />
        </label>
        <label>
          <span className="muted" style={{ display: "block", fontSize: 12, marginBottom: 4 }}>
            To
          </span>
          <DateInput
            className="input"
            min={data?.date_min || undefined}
            max={data?.date_max || undefined}
            aria-label="To"
            value={dateTo}
            onValueChange={(iso) => setDate("date_to", iso)}
          />
        </label>
        <label className="pill" style={{ cursor: "pointer" }}>
          <input type="checkbox" checked={smooth} onChange={(event) => setSmooth(event.target.checked)} style={{ marginRight: 6 }} />
          Smoothing
        </label>
        <span className="pill">{busy ? "Loading…" : `${comparing ? plotted.reduce((total, entry) => total + (entry.query.data?.points.length ?? 0), 0) : points.length} tests`}</span>
      </div>

      {materialId && <div className="row" style={{ marginBottom: 12 }}>
        <Link to={qcHref("sinottico", { materialId })}>Sinottico</Link>
        <Link to={qcHref("lots", { materialId })}>Lots</Link>
        <Link to={comparison.link("charts")}>Charts</Link>
        <Link to={qcHref("calendar", { materialId })}>Calendar</Link>
      </div>}

      {queryError && <ErrorNotice error={queryError} />}
      {!comparing && busy && !data && <LoadingNotice>Loading ratings…</LoadingNotice>}
      {!materialsQuery.isPending && !materialId && <EmptyNotice>Select a material to load ratings.</EmptyNotice>}
      {data && !data.configured && (
        <EmptyNotice>No property has a positive rating weight. Set a weight in Application settings to enable ratings.</EmptyNotice>
      )}
      {data?.configured && !busy && !points.length && (
        <EmptyNotice>No rated tests are available for this date range.</EmptyNotice>
      )}

      {comparing && (
        <table className="table" style={{ width: "100%", marginBottom: 12 }}>
          <thead><tr><th scope="col">Material</th><th scope="col">Last test</th><th scope="col">Average</th></tr></thead>
          <tbody>{entries.map(({ id, query }) => {
            const summary = query.data;
            const status = query.isPending ? "Loading…" : summary && !summary.configured
              ? "Ratings not configured" : summary && !summary.points.length ? "No rated tests in this date range" : null;
            return <tr key={id}>
              <th scope="row">{materialDescription(materials, id)}{status && <div className="muted">{status}</div>}
                {query.error && <ErrorNotice error={query.error} />}
              </th>
              <td>{summary?.latest_rating == null ? "—" : `${summary.latest_rating.toFixed(1)}%`}</td>
              <td>{summary?.average_rating == null ? "—" : `${summary.average_rating.toFixed(1)}%`}</td>
            </tr>;
          })}</tbody>
        </table>
      )}
      {(comparing ? plotted.length > 0 : data?.configured && points.length > 0) && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(280px, 1fr))", gap: 12 }}>
          {data && <>
            <RatingGauge title="Last test" value={data.latest_rating} />
            <RatingGauge title="Average" value={data.average_rating} />
          </>}
          <div className="card" style={{ gridColumn: "1 / -1" }}>
            <h3 style={{ margin: 0 }}>Overall</h3>
            <Plot
              data={comparing ? plotted.map(({ id, name, color, query }) => {
                const materialPoints = query.data?.points ?? [];
                return {
                  type: "scatter" as const, mode: "lines+markers" as const, name,
                  visible: hidden.has(id) ? "legendonly" as const : true,
                  x: materialPoints.map(point => point.date),
                  y: materialPoints.map(point => point.rating_percent),
                  line: { color, width: 2, shape: smooth && materialPoints.length >= 3 ? "spline" as const : "linear" as const, smoothing: 0.6 },
                  marker: { color, size: 8 },
                  hovertemplate: "%{x|%d-%m-%Y}<br>%{y:.1f}%<extra>%{fullData.name}</extra>",
                };
              }) : [
                {
                  type: "scatter",
                  mode: "lines+markers",
                  name: "Rating",
                  x: points.map((point) => point.date),
                  y: points.map((point) => point.rating_percent),
                  line: { color: "#4f86ff", width: 2, shape: smooth && points.length >= 3 ? "spline" : "linear", smoothing: 0.6 },
                  marker: { color: points.map((point) => ratingColor(point.rating_percent)), size: 8 },
                  hovertemplate: "%{x|%d-%m-%Y}<br>%{y:.1f}%<extra></extra>",
                },
              ] as any}
              layout={{
                autosize: true,
                paper_bgcolor: "rgba(0,0,0,0)",
                plot_bgcolor: "rgba(0,0,0,0)",
                font: { color: colors.text },
                margin: { l: 50, r: 20, t: 20, b: 45 },
                xaxis: { gridcolor: colors.grid, type: "date", tickformat: "%d-%m-%Y", hoverformat: "%d-%m-%Y", title: { text: "Request date" } },
                yaxis: { gridcolor: colors.grid, range: [0, 100], ticksuffix: "%" },
                showlegend: false,
              } as any}
              style={{ width: "100%", height: 380 }}
              config={{ displaylogo: false, responsive: true }}
            />
          </div>
        </div>
      )}
      {comparing && <ComparisonLegend items={plotted} materials={materials} hidden={hidden}
        toggle={id => setHidden(current => toggleMaterial(current, id))} />}
    </div>
  );
}
