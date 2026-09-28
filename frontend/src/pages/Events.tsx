import { useCallback, useEffect, useState } from "react";
import { api, errMessage, mediaUrl } from "../api/client";
import type { Camera, EventPage, PlateRead } from "../api/types";
import { DemoBadge, EmptyState, ErrorState, Loading, Modal, Pagination, ShieldNote } from "../components/ui";

interface EventDetail {
  event: EventPage["items"][number];
  camera: { id: number; name: string; code: string; location_name: string } | null;
  plate_read: PlateRead | null;
  vehicle: { id: number; registration_number: string } | null;
}

export default function Events() {
  const [page, setPage] = useState(1);
  const [data, setData] = useState<EventPage | null>(null);
  const [cams, setCams] = useState<Camera[]>([]);
  const [error, setError] = useState("");
  const [cameraId, setCameraId] = useState("");
  const [cls, setCls] = useState("");
  const [plate, setPlate] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [detail, setDetail] = useState<EventDetail | null>(null);
  const pageSize = 25;

  useEffect(() => {
    api.get<Camera[]>("/cameras").then((r) => setCams(r.data)).catch(() => setCams([]));
  }, []);

  const load = useCallback(async () => {
    setError("");
    try {
      const r = await api.get<EventPage>("/events", {
        params: {
          page,
          page_size: pageSize,
          camera_id: cameraId || undefined,
          object_class: cls || undefined,
          plate_text: plate || undefined,
          start: start ? new Date(start).toISOString() : undefined,
          end: end ? new Date(end).toISOString() : undefined,
        },
      });
      setData(r.data);
    } catch (e) {
      setError(errMessage(e));
    }
  }, [page, cameraId, cls, plate, start, end]);

  useEffect(() => {
    load();
  }, [load]);

  const openDetail = async (id: number) => {
    try {
      const r = await api.get<EventDetail>(`/events/${id}`);
      setDetail(r.data);
    } catch (e) {
      alert(errMessage(e));
    }
  };

  return (
    <div className="space-y-4">
      <div className="card grid grid-cols-1 gap-3 p-4 md:grid-cols-3 xl:grid-cols-6">
        <select className="input" value={cameraId} onChange={(e) => { setCameraId(e.target.value); setPage(1); }}>
          <option value="">All cameras</option>
          {cams.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <select className="input" value={cls} onChange={(e) => { setCls(e.target.value); setPage(1); }}>
          <option value="">All classes</option>
          {["car", "motorcycle", "bus", "truck", "person"].map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <input className="input font-mono" placeholder="Plate contains…" value={plate} onChange={(e) => { setPlate(e.target.value.toUpperCase()); setPage(1); }} />
        <input type="datetime-local" className="input" value={start} onChange={(e) => { setStart(e.target.value); setPage(1); }} />
        <input type="datetime-local" className="input" value={end} onChange={(e) => { setEnd(e.target.value); setPage(1); }} />
        <button
          className="btn-ghost justify-center"
          onClick={() => { setCameraId(""); setCls(""); setPlate(""); setStart(""); setEnd(""); setPage(1); }}
        >
          Clear filters
        </button>
      </div>

      {error && <ErrorState message={error} onRetry={load} />}
      {!data && !error && <Loading label="Loading events…" />}

      {data && (
        <div className="card">
          {data.items.length === 0 ? (
            <EmptyState title="No events match the filters" hint="Events appear when the ingestion worker records AI detections." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200">
                    <th className="table-head px-4 py-3">Image</th>
                    <th className="table-head px-4 py-3">Time</th>
                    <th className="table-head px-4 py-3">Class</th>
                    <th className="table-head px-4 py-3">Camera</th>
                    <th className="table-head px-4 py-3">Conf.</th>
                    <th className="table-head px-4 py-3">Track</th>
                    <th className="table-head px-4 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((ev) => (
                    <tr key={ev.id} className="border-b border-slate-100 hover:bg-slate-50">
                      <td className="px-4 py-2">
                        {ev.image_path ? (
                          <img src={mediaUrl(ev.image_path) ?? ""} alt="" className="h-10 w-16 rounded object-cover" />
                        ) : (
                          <div className="h-10 w-16 rounded bg-slate-50" />
                        )}
                      </td>
                      <td className="px-4 py-2 text-xs tabular-nums">{new Date(ev.timestamp).toLocaleString()}</td>
                      <td className="px-4 py-2 text-xs capitalize">{ev.object_class}</td>
                      <td className="px-4 py-2 text-xs">{cams.find((c) => c.id === ev.camera_id)?.name ?? `#${ev.camera_id}`}</td>
                      <td className="px-4 py-2 text-xs tabular-nums">{(ev.confidence * 100).toFixed(0)}%</td>
                      <td className="px-4 py-2 text-xs tabular-nums text-muted">{ev.track_id ?? "—"}</td>
                      <td className="px-4 py-2 text-right">
                        <button className="btn-ghost text-xs" onClick={() => openDetail(ev.id)}>Details</button>
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

      {detail && (
        <Modal title={`Event #${detail.event.id}`} onClose={() => setDetail(null)} wide>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              {detail.event.image_path ? (
                <img src={mediaUrl(detail.event.image_path) ?? ""} alt="detection" className="w-full rounded-md border border-slate-300" />
              ) : (
                <div className="flex h-40 items-center justify-center rounded-md bg-slate-50 text-xs text-muted">
                  No image stored for this event
                </div>
              )}
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <p className="font-semibold capitalize">{detail.event.object_class}</p>
                <DemoBadge isDemo={detail.event.is_demo} />
              </div>
              <p className="text-xs text-muted">Camera: {detail.camera?.name ?? "—"}</p>
              <p className="text-xs text-muted tabular-nums">{new Date(detail.event.timestamp).toLocaleString()}</p>
              <p className="text-xs tabular-nums">Confidence: {(detail.event.confidence * 100).toFixed(1)}%</p>
              <p className="text-xs tabular-nums">Track ID: {detail.event.track_id ?? "—"}</p>
              <p className="text-[11px] font-mono text-muted">
                bbox: ({detail.event.bbox_x.toFixed(0)}, {detail.event.bbox_y.toFixed(0)}) {detail.event.bbox_w?.toFixed(0)}×{detail.event.bbox_h.toFixed(0)}
              </p>
              {detail.vehicle && (
                <p className="text-xs">Vehicle: <span className="font-mono font-semibold">{detail.vehicle.registration_number}</span></p>
              )}
            </div>
          </div>
          {detail.plate_read && (
            <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold">ANPR read</p>
                {detail.plate_read.needs_review && (
                  <span className="badge bg-warn/15 text-warn border border-warn/30">needs review</span>
                )}
              </div>
              <div className="mt-2 flex items-center gap-3">
                {detail.plate_read.crop_path && (
                  <img src={mediaUrl(detail.plate_read.crop_path) ?? ""} alt="plate" className="h-10 rounded border border-slate-600" />
                )}
                <div>
                  <p className="font-mono text-lg font-bold">{detail.plate_read.corrected_text ?? (detail.plate_read.plate_text || "unreadable")}</p>
                  <p className="text-[11px] text-muted tabular-nums">
                    OCR confidence {(detail.plate_read.ocr_confidence * 100).toFixed(0)}%
                    {detail.plate_read.corrected_text ? " · manually corrected" : ""}
                  </p>
                </div>
              </div>
              <div className="mt-2">
                <ShieldNote>
                  OCR output is not guaranteed correct. Low-confidence or malformed reads are flagged and must be
                  verified by an authorized operator before operational use.
                </ShieldNote>
              </div>
            </div>
          )}
        </Modal>
      )}
    </div>
  );
}
