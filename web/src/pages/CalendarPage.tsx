import { useEffect, useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { qcHref } from "../features/qcLinks";
import { useQuery } from "@tanstack/react-query";
import { calendarFailures, calendarMonth, type CalendarItem } from "../api/calendar";
import type { ApiId } from "../api/client";
import { EmptyNotice, ErrorNotice, LoadingNotice } from "../components/AsyncState";


const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];


function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}


function validMonth(value: string | null): string {
  if (value && /^\d{4}-(0[1-9]|1[0-2])$/.test(value)) return value;
  return currentMonth();
}


function shiftMonth(value: string, offset: number): string {
  const [year, month] = value.split("-").map(Number);
  const shifted = new Date(year, month - 1 + offset, 1);
  return `${shifted.getFullYear()}-${String(shifted.getMonth() + 1).padStart(2, "0")}`;
}


function localIso(value: Date): string {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
}


function monthDays(value: string): { iso: string; day: number; inMonth: boolean }[] {
  const [year, month] = value.split("-").map(Number);
  const first = new Date(year, month - 1, 1);
  const mondayOffset = (first.getDay() + 6) % 7;
  const start = new Date(year, month - 1, 1 - mondayOffset);
  return Array.from({ length: 42 }, (_, index) => {
    const day = new Date(start.getFullYear(), start.getMonth(), start.getDate() + index);
    return { iso: localIso(day), day: day.getDate(), inMonth: day.getMonth() === month - 1 };
  });
}


function FailureDialog({ testId, returnTo, onClose }: { testId: ApiId; returnTo: string; onClose: () => void }) {
  const reportQuery = useQuery({
    queryKey: ["calendar", "failures", testId],
    queryFn: () => calendarFailures(testId),
  });
  const report = reportQuery.data || null;

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [onClose]);

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="dialog-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="qc-failures-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h3 id="qc-failures-title" style={{ margin: 0 }}>
            QC failures
          </h3>
          <button className="btn" type="button" onClick={onClose} aria-label="Close QC failures">
            Close
          </button>
        </div>
        {reportQuery.isPending && <LoadingNotice>Loading QC failures…</LoadingNotice>}
        {reportQuery.error && <ErrorNotice error={reportQuery.error} />}
        {report && (
          <>
            <div className="muted" style={{ margin: "12px 0" }}>
              {report.material_code} — {report.request_date || "—"} — Test {report.test_id}
            </div>
            <Link to={qcHref("lots", { testId: report.test_id, returnTo })}>Open test in Lots</Link>
            {!report.failures.length ? (
              <div className="muted">No ALARM tolerance failures found for this sample.</div>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>QC Property</th>
                    <th>Actual Value</th>
                  </tr>
                </thead>
                <tbody>
                  {report.failures.map((failure, index) => (
                    <tr key={`${failure.property_name}-${index}`}>
                      <td>{failure.property_name}</td>
                      <td>{failure.actual_value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </section>
    </div>
  );
}


function SampleCard({ item, returnTo, onFailures }: { item: CalendarItem; returnTo: string; onFailures: (testId: ApiId) => void }) {
  const lowRating = item.rating_percent != null && item.rating_percent < 75;
  const subtitle = [item.lastrina_code, item.material_desc].filter(Boolean).join(" — ");
  return (
    <div className="calendar-sample">
      <div style={{ minWidth: 0 }}>
        <div style={{ fontWeight: 700 }}><Link to={qcHref("lots", { materialId: item.material_id, testId: item.test_id, returnTo })}>{item.material_code}</Link></div>
        {subtitle && <div className="muted calendar-sample-subtitle">{subtitle}</div>}
        <div className="muted" style={{ fontSize: 12 }}><Link to={qcHref("charts", { materialId: item.material_id })}>Charts</Link>{" · "}<Link to={qcHref("ratings", { materialId: item.material_id })}>Ratings</Link></div>
      </div>
      {lowRating ? (
        <button
          className="calendar-warning"
          type="button"
          title={`Rating ${item.rating_percent!.toFixed(1)}% (< 75%). Show QC failures.`}
          aria-label={`Show QC failures for ${item.material_code}, rating ${item.rating_percent!.toFixed(1)} percent`}
          onClick={() => onFailures(item.test_id)}
        >
          !
        </button>
      ) : item.rating_percent != null ? (
        <span className="pill">{item.rating_percent.toFixed(0)}%</span>
      ) : null}
    </div>
  );
}


export default function CalendarPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedMonth = validMonth(searchParams.get("month"));
  const materialId = searchParams.get("material_id") || "";
  const failureTestId = searchParams.get("test_id") || null;
  const returnParams = new URLSearchParams(searchParams);
  returnParams.set("month", selectedMonth);
  returnParams.delete("test_id");
  const returnQuery = returnParams.toString();
  const returnTo = `/calendar${returnQuery ? `?${returnQuery}` : ""}`;
  const [year, month] = selectedMonth.split("-").map(Number);
  const monthQuery = useQuery({
    queryKey: ["calendar", "month", year, month],
    queryFn: () => calendarMonth(year, month),
  });
  const data = monthQuery.data || null;
  const busy = monthQuery.isFetching;

  useEffect(() => {
    if (searchParams.get("month") !== selectedMonth) {
      const next = new URLSearchParams(searchParams);
      next.set("month", selectedMonth);
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, selectedMonth, setSearchParams]);

  const days = useMemo(() => monthDays(selectedMonth), [selectedMonth]);
  const itemsByDay = useMemo(() => {
    const grouped = new Map<string, CalendarItem[]>();
    for (const item of data?.items || []) {
      if (materialId && item.material_id !== materialId) continue;
      const items = grouped.get(item.prod_date) || [];
      items.push(item);
      grouped.set(item.prod_date, items);
    }
    return grouped;
  }, [data, materialId]);
  const materialOptions = useMemo(() => Array.from(new Map((data?.items || []).map((item) => [item.material_id, item.material_code])).entries()), [data]);
  const visibleCount = useMemo(() => Array.from(itemsByDay.values()).reduce((count, items) => count + items.length, 0), [itemsByDay]);
  const monthTitle = new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" }).format(
    new Date(year, month - 1, 1),
  );

  function chooseMonth(value: string) {
    const next = new URLSearchParams(searchParams);
    next.set("month", validMonth(value));
    next.delete("test_id");
    setSearchParams(next);
  }

  function setSelection(key: string, value: string) {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next);
  }

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 12 }}>
        <h2 className="title" style={{ margin: 0 }}>
          Calendar
        </h2>
        <div className="row">
          <button className="btn" type="button" onClick={() => chooseMonth(shiftMonth(selectedMonth, -1))} aria-label="Previous month">
            ◀
          </button>
          <button className="btn" type="button" onClick={() => chooseMonth(currentMonth())}>
            Today
          </button>
          <button className="btn" type="button" onClick={() => chooseMonth(shiftMonth(selectedMonth, 1))} aria-label="Next month">
            ▶
          </button>
          <input
            className="input"
            type="month"
            min="1900-01"
            max="9999-12"
            value={selectedMonth}
            aria-label="Calendar month"
            onChange={(event) => chooseMonth(event.target.value)}
          />
          <span className="pill">{busy ? "Loading…" : `${visibleCount} tests`}</span>
        </div>
      </div>
      <h3 style={{ textAlign: "right", margin: "0 0 10px" }}>{monthTitle}</h3>
      <div className="row" style={{ marginBottom: 10 }}>
        <select className="input" aria-label="Filter calendar by material" value={materialId} onChange={(event) => setSelection("material_id", event.target.value)}>
          <option value="">All materials this month</option>
          {materialId && !materialOptions.some(([id]) => id === materialId) && <option value={materialId}>Selected material (no tests this month)</option>}
          {materialOptions.map(([id, code]) => <option key={id} value={id}>{code}</option>)}
        </select>
        {materialId && <>
          <Link to={qcHref("sinottico", { materialId })}>Sinottico</Link>
          <Link to={qcHref("lots", { materialId })}>Lots</Link>
          <Link to={qcHref("charts", { materialId })}>Charts</Link>
          <Link to={qcHref("ratings", { materialId })}>Ratings</Link>
        </>}
      </div>
      {monthQuery.error && <ErrorNotice error={monthQuery.error} />}
      {monthQuery.isPending && <LoadingNotice>Loading calendar…</LoadingNotice>}
      <div className="calendar-scroll">
        <div className="calendar-grid">
          {WEEKDAYS.map((weekday) => (
            <div className="calendar-weekday" key={weekday}>
              {weekday}
            </div>
          ))}
          {days.map((day) => {
            const items = itemsByDay.get(day.iso) || [];
            return (
              <section className={`calendar-day${day.inMonth ? "" : " outside"}`} key={day.iso}>
                <div className="calendar-day-number">{day.day}</div>
                {items.slice(0, 8).map((item) => (
                  <SampleCard key={item.test_id} item={item} returnTo={returnTo} onFailures={(testId) => setSelection("test_id", testId)} />
                ))}
                {items.length > 8 && <div className="muted">+{items.length - 8} more…</div>}
              </section>
            );
          })}
        </div>
      </div>
      {!busy && data && !visibleCount && <EmptyNotice>No production tests for this month and material.</EmptyNotice>}
      {failureTestId != null && <FailureDialog testId={failureTestId} returnTo={returnTo} onClose={() => setSelection("test_id", "")} />}
    </div>
  );
}
