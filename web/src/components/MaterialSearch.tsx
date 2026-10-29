import { useEffect, useMemo, useState } from "react";
import { searchMaterials, type Material } from "../api";

export default function MaterialSearch(props: { onPick: (m: Material) => void }) {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<Material[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const preview = useMemo(() => items.slice(0, 8), [items]);

  useEffect(() => {
    let alive = true;
    const t = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await searchMaterials(q);
        if (!alive) return;
        setItems(res);
      } catch {
        if (!alive) return;
        setItems([]);
      } finally {
        if (alive) setLoading(false);
      }
    }, 250);
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [q]);

  return (
    <div style={{ position: "relative", width: 520, maxWidth: "100%" }}>
      <input
        className="input"
        style={{ width: "100%" }}
        placeholder="Search material..."
        value={q}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onChange={(e) => setQ(e.target.value)}
      />
      {open && (
        <div
          className="card material-search-dropdown"
          style={{
            position: "absolute",
            top: 44,
            left: 0,
            right: 0,
            padding: 8,
            zIndex: 10,
          }}
        >
          <div className="muted" style={{ fontSize: 12, padding: "6px 8px" }}>
            {loading ? "Loading..." : `${items.length} result(s)`}
          </div>
          {preview.map((m) => (
            <button
              key={m.material_id}
              className="btn"
              style={{ width: "100%", textAlign: "left", marginBottom: 6 }}
              onMouseDown={(e) => {
                e.preventDefault();
                props.onPick(m);
              }}
            >
              <div style={{ fontWeight: 600 }}>{m.code}</div>
              <div className="muted" style={{ fontSize: 12 }}>
                {(m.description || "").slice(0, 120)}
              </div>
            </button>
          ))}
          {!preview.length && !loading && <div className="muted" style={{ padding: 8 }}>No matches</div>}
        </div>
      )}
    </div>
  );
}
