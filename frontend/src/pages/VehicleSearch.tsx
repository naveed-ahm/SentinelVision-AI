import { useCallback, useEffect, useState } from "react";
import { api, errMessage, mediaUrl } from "../api/client";
import type { Camera, Vehicle, VehicleAttribute, VehicleDetail as Detail, VehiclePage, WatchlistCheck } from "../api/types";
import { DemoBadge, EmptyState, ErrorState, Loading, Modal, Pagination, ShieldNote } from "../components/ui";
import { Search, ShieldAlert } from "lucide-react";

export default function VehicleSearch() {
  const [page, setPage] = useState(1);
  const [data, setData] = useState<VehiclePage | null>(null);
  const [cams, setCams] = useState<Camera[]>([]);
  const [error, setError] = useState("");
  const [reg, setReg] = useState("");
  const [cameraId, setCameraId] = useState("");
  const [cls, setCls] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [detail, setDetail] = useState<Detail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailAttrs, setDetailAttrs] = useState<Record<number, VehicleAttribute>>({});
  const [watchFlag, setWatchFlag] = useState<WatchlistCheck | null>(null);
  const pageSize = 20;

  useEffect(() => {
    api.get<Camera[]>("/cameras").then((r) => setCams(r.data)).catch(() => setCams([]));
  }, []);

  const load = useCallback(async () => {
    setError("");
    try {
      const r = await api.get<VehiclePage>("/vehicles", {
        params: {
          page,
          page_size: pageSize,
          registration_number: reg || undefined,
          camera_id: cameraId || undefined,
          vehicle_class: cls || undefined,
          start: start ? new Date(start).toISOString() : undefined,
          end: end ? new Date(end).toISOString() : undefined,
        },
      });
      setData(r.data);
    } catch (e) {
      setError(errMessage(e));
    }
  }, [page, reg, cameraId, cls, start, end]);

  useEffect(() => {
    load();
  }, [load]);

  const openDetail = async (v: Vehicle) => {
    setDetailLoading(true);
    setDetailAttrs({});
    setWatchFlag(null);
    try {
      const r = await api.get<Detail>(`/vehicles/${v.id}`);
      setDetail(r.data);
      // Optional watchlist status for this plate (best effort, never blocks).
      api
        .get<WatchlistCheck>(`/watchlist/check/${encodeURIComponent(v.registration_number)}`)
        .then((wr) => setWatchFlag(wr.data))
        .catch(() => setWatchFlag(null));
      // Optional AI-module attributes for each recorded sighting (best effort).
      try {
        const attrs = await Promise.all(
          r.data.sightings.map((s) =>
            api.get<VehicleAttribute[]>(`/ai-modules/events/${s.event_id}/attributes`).then((ar) => ar.data).catch(() => [] as VehicleAttribute[])
          )
        );
        const map: Record<number, VehicleAttribute> = {};
        r.data.sightings.forEach((s, i) => {
          if (attrs[i]?.length) map[s.event_id] = attrs[i][0];
        });
        setDetailAttrs(map);
      } catch {
        /* attributes are optional; never block the sightings modal */
      }
    } catch (e) {
      alert(errMessage(e));
    } finally {
      setDetailLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="card p-4 grid grid-cols-1 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <div className="xl:col-span-2 relative">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted" />
          <input className="input pl-9 font-mono" placeholder="Registration number…" value={reg}
            onChange={(e) => { setReg(e.target.value.toUpperCase()); setPage(1); }} />
        </div>
        <select className="input" value={cameraId} onChange={(e) => { setCameraId(e.target.value); setPage(1); }}>
          <option value="">All cameras</option>
          {cams.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <select className="input" value={cls} onChange={(e) => { setCls(e.target.value); setPage(1); }}>
          <option value="">All types</option>
          {["car", "motorcycle", "bus", "truck"].map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <input type="datetime-local" className="input" value={start} onChange={(e) => { setStart(e.target.value); setPage(1); }} />
        <input type="datetime-local" className="input" value={end} onChange={(e) => { setEnd(e.target.value); setPage(1); }} />
      </div>

      {error && <ErrorState message={error} onRetry={load} />}
      {!data && !error && <Loading label="Searching vehicles…" />}

      {data && (
        <div className="card">
          {(data.items.length === 0) ? (
            <EmptyState title="No vehicles match the filters" hint="Try a different plate fragment, camera or date range." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200">
                    <th className="table-head px-4 py-3">Registration</th>
                    <th className="table-head px-4 py-3">Type</th>
                    <th className="table-head px-4 py-3">First seen</th>
                    <th className="table-head px-4 py-3">Last seen</th>
                    <th className="table-head px-4 py-3">Sightings</th>
                    <th className="table-head px-4 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((v) => (
                    <tr key={v.id} className="border-b border-slate-100 hover:bg-slate-50">
                      <td className="px-4 py-3 font-mono font-semibold flex items-center gap-2">
                        {v.registration_number} <DemoBadge isDemo={v.is_demo} />
                      </td>
                      <td className="px-4 py-3 text-xs capitalize">{v.vehicle_class || "—"}</td>
                      <td className="px-4 py-3 text-xs tabular-nums">{new Date(v.first_seen_at).toLocaleString()}</td>
                      <td className="px-4 py-3 text-xs tabular-nums">{new Date(v.last_seen_at).toLocaleString()}</td>
                      <td className="px-4 py-3 tabular-nums">{v.total_sightings}</td>
                      <td className="px-4 py-3 text-right">
                        <button className="btn-ghost text-xs" onClick={() => openDetail(v)}>Sightings</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <Pagination page={page} pageSize={pageSize} total={data.total} onPage={setPage} />
        </div>
      )}

      {detailLoading && <Loading label="Loading sightings…" />}
      {detail && (
        <Modal title={`Vehicle ${detail.vehicle.registration_number}`} onClose={() => setDetail(null)} wide>
          {watchFlag?.on_watchlist && (
            <div className="mb-3 flex items-center gap-2 rounded-md border border-crit/40 bg-crit/10 px-3 py-2 text-xs font-semibold text-crit">
              <ShieldAlert className="h-4 w-4" />
              ON WATCHLIST — {watchFlag.entries.map((e) => `${e.category.replace(/_/g, " ")} (${e.title || e.display_value})`).join(", ")}
            </div>
          )}
          <div className="mb-3 flex gap-4 text-xs text-muted">
            <span>Type: <span className="capitalize text-body">{detail.vehicle.vehicle_class || "—"}</span></span>
            <span>Sightings: <span className="text-body">{detail.vehicle.total_sightings}</span></span>
          </div>
          <div className="space-y-2">
            {detail.sightings.length === 0 && <EmptyState title="No sightings recorded" />}
            {detail.sightings.map((s) => (
              <div key={s.id} className="flex items-center gap-3 rounded-md border border-slate-200 bg-slate-50 p-2.5">
                {s.image_path ? (
                  <img src={mediaUrl(s.image_path) ?? ""} alt="" className="h-12 w-20 rounded object-cover" />
                ) : (
                  <div className="h-12 w-20 rounded bg-slate-50" />
                )}
                <div className="min-w-0 flex-1">
                  <p className="text-sm">{s.camera_name ?? `Camera #${s.camera_id}`}</p>
                  <p className="text-[11px] text-muted tabular-nums">{new Date(s.timestamp).toLocaleString()}</p>
                </div>
                <div className="text-right text-xs">
                  <p className="capitalize text-body">{s.object_class ?? "—"}</p>
                  <p className="text-muted tabular-nums">
                    {s.ocr_confidence != null ? `OCR ${(s.ocr_confidence * 100).toFixed(0)}%` : ""}
                  </p>
                </div>
              </div>
            ))}
            {Object.keys(detailAttrs).length > 0 && (
              <div className="flex flex-wrap items-center gap-2 rounded-md border border-slate-200 bg-slate-50 p-2.5 text-xs">
                <span className="font-semibold text-slate-600">AI attributes (appearance model, unverified):</span>
                {Object.values(detailAttrs).map((a) => (
                  <span key={a.id} className="badge border border-accent/30 bg-accent/10 text-accent-bright">
                    {a.color || "?"} {a.vehicle_type} · {(a.color_confidence * 100).toFixed(0)}%
                  </span>
                ))}
              </div>
            )}
          </div>
          <div className="mt-4">
            <ShieldNote>
              This timeline lists only cameras where the vehicle was actually recorded. No unobserved path is implied
              between sightings.
            </ShieldNote>
          </div>
        </Modal>
      )}
    </div>
  );
}
