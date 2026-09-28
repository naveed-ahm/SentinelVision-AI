import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Grid2x2, Grid3x3, Square } from "lucide-react";
import { api, errMessage } from "../api/client";
import type { Camera } from "../api/types";
import { ErrorState, Loading } from "../components/ui";
import { CameraTile } from "../components/CameraTile";

const LAYOUTS = [
  { id: 1, icon: Square, label: "1×1" },
  { id: 4, icon: Grid2x2, label: "2×2" },
  { id: 6, icon: Grid3x3, label: "3×2" },
] as const;

export default function Monitoring() {
  const [params, setParams] = useSearchParams();
  const focusId = params.get("focus") ? Number(params.get("focus")) : null;
  const [cameras, setCameras] = useState<Camera[] | null>(null);
  const [error, setError] = useState("");
  const [layout, setLayout] = useState<number>(6);
  const [onlyOnline, setOnlyOnline] = useState(false);
  const [search, setSearch] = useState("");

  useEffect(() => {
    api
      .get<Camera[]>("/cameras")
      .then((r) => setCameras(r.data))
      .catch((e) => setError(errMessage(e)));
  }, []);

  const filtered = useMemo(() => {
    let list = cameras ?? [];
    if (onlyOnline) list = list.filter((c) => c.status === "online");
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (c) => c.name.toLowerCase().includes(q) || c.code.toLowerCase().includes(q) || c.location_name.toLowerCase().includes(q)
      );
    }
    return list;
  }, [cameras, onlyOnline, search]);

  if (error) return <ErrorState message={error} />;
  if (!cameras) return <Loading label="Loading cameras…" />;

  const focusCam = focusId ? cameras.find((c) => c.id === focusId) : null;
  const grid = focusCam ? [focusCam] : filtered.slice(0, layout);
  const gridClass =
    grid.length === 1 ? "grid-cols-1 max-w-5xl" : grid.length <= 4 ? "grid-cols-1 lg:grid-cols-2" : "grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1 rounded-md border border-slate-300 bg-slate-50 p-1">
          {LAYOUTS.map(({ id, icon: Icon, label }) => (
            <button
              key={id}
              className={`flex items-center gap-1.5 rounded px-2.5 py-1 text-xs ${layout === id && !focusCam ? "bg-accent text-white" : "text-muted hover:text-body"}`}
              onClick={() => {
                setLayout(id);
                if (focusId) setParams({});
              }}
              disabled={!!focusCam}
            >
              <Icon className="h-3.5 w-3.5" /> {label}
            </button>
          ))}
        </div>
        <input className="input max-w-xs" placeholder="Filter cameras…" value={search} onChange={(e) => setSearch(e.target.value)} />
        <label className="flex items-center gap-2 text-xs text-muted">
          <input type="checkbox" checked={onlyOnline} onChange={(e) => setOnlyOnline(e.target.checked)} />
          Online only
        </label>
        {focusCam && (
          <button className="btn-ghost text-xs" onClick={() => setParams({})}>
            ← Back to grid
          </button>
        )}
        <span className="ml-auto text-xs text-muted">
          Showing {grid.length} of {cameras.length} cameras (browser limit — backend caps concurrent sources separately)
        </span>
      </div>

      {grid.length === 0 ? (
        <div className="card p-10 text-center text-sm text-muted">No cameras match the current filters.</div>
      ) : (
        <div className={`grid gap-3 ${gridClass}`}>
          {grid.map((cam) => (
            <CameraTile key={cam.id} camera={cam} openMonitoring={focusCam ? undefined : (id) => setParams({ focus: String(id) })} />
          ))}
        </div>
      )}
    </div>
  );
}
