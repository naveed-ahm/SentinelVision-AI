import { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup, Polyline, CircleMarker } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Route } from "lucide-react";
import { api, errMessage } from "../api/client";
import type { GisCamera, GisPathPoint, GisSighting } from "../api/types";
import { EmptyState, ErrorState, Loading, ShieldNote } from "../components/ui";

const onlineIcon = L.divIcon({
  className: "",
  html: `<div style="width:16px;height:16px;border-radius:50%;background:#16A34A;border:2px solid #FFFFFF;box-shadow:0 0 6px #16A34A88"></div>`,
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});
const offlineIcon = L.divIcon({
  className: "",
  html: `<div style="width:16px;height:16px;border-radius:50%;background:#DC2626;border:2px solid #FFFFFF"></div>`,
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});
const sightingIcon = L.divIcon({
  className: "",
  html: `<div style="width:12px;height:12px;border-radius:2px;background:#2563EB;border:2px solid #FFFFFF;transform:rotate(45deg)"></div>`,
  iconSize: [12, 12],
  iconAnchor: [6, 6],
});

export default function GisMap() {
  const [cams, setCams] = useState<GisCamera[] | null>(null);
  const [sightings, setSightings] = useState<GisSighting[]>([]);
  const [error, setError] = useState("");
  const [reg, setReg] = useState("");
  const [cameraId, setCameraId] = useState("");
  const [cls, setCls] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [path, setPath] = useState<GisPathPoint | null>(null);
  const [pathLoading, setPathLoading] = useState(false);

  useEffect(() => {
    api
      .get<GisCamera[]>("/gis/cameras")
      .then((r) => setCams(r.data))
      .catch((e) => setError(errMessage(e)));
  }, []);

  useEffect(() => {
    const t = setTimeout(() => {
      api
        .get<GisSighting[]>("/gis/sightings", {
          params: {
            registration_number: reg || undefined,
            camera_id: cameraId || undefined,
            vehicle_class: cls || undefined,
            start: start ? new Date(start).toISOString() : undefined,
            end: end ? new Date(end).toISOString() : undefined,
          },
        })
        .then((r) => setSightings(r.data))
        .catch(() => setSightings([]));
    }, 350);
    return () => clearTimeout(t);
  }, [reg, cameraId, cls, start, end]);

  const center = useMemo<[number, number]>(() => {
    const located = cams?.filter((c) => c.latitude != null) ?? [];
    if (located.length) return [located[0].latitude!, located[0].longitude!];
    return [23.0225, 72.5714]; // Ahmedabad default
  }, [cams]);

  const openPath = async (vehicleId: number) => {
    setPathLoading(true);
    try {
      const r = await api.get<GisPathPoint>(`/gis/paths/${vehicleId}`);
      setPath(r.data);
    } catch (e) {
      alert(errMessage(e));
    } finally {
      setPathLoading(false);
    }
  };

  if (error) return <ErrorState message={error} />;
  if (!cams) return <Loading label="Loading map…" />;

  const located = cams.filter((c) => c.latitude != null && c.longitude != null);

  return (
    <div className="space-y-3">
      <div className="card grid grid-cols-1 gap-3 p-3 md:grid-cols-3 xl:grid-cols-6">
        <input className="input font-mono" placeholder="Registration…" value={reg} onChange={(e) => setReg(e.target.value.toUpperCase())} />
        <select className="input" value={cameraId} onChange={(e) => setCameraId(e.target.value)}>
          <option value="">All cameras</option>
          {cams.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <select className="input" value={cls} onChange={(e) => setCls(e.target.value)}>
          <option value="">All types</option>
          {["car", "motorcycle", "bus", "truck"].map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <input type="datetime-local" className="input" value={start} onChange={(e) => setStart(e.target.value)} />
        <input type="datetime-local" className="input" value={end} onChange={(e) => setEnd(e.target.value)} />
        <button
          className="btn-ghost justify-center"
          disabled={!path && sightings.length === 0}
          onClick={() => path && setPath(null)}
          title="Clear selected path"
        >
          <Route className="h-4 w-4" /> {pathLoading ? "…" : "Clear path"}
        </button>
      </div>

      <div className="card overflow-hidden">
        <MapContainer center={center} zoom={13} className="h-[64vh] w-full" scrollWheelZoom>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {located.map((c) => (
            <Marker key={c.id} position={[c.latitude!, c.longitude!]} icon={c.status === "online" ? onlineIcon : offlineIcon}>
              <Popup>
                <div className="text-slate-900" style={{ minWidth: 200 }}>
                  <p className="font-semibold text-sm">{c.name}</p>
                  <p className="text-xs text-slate-600 font-mono">{c.code}</p>
                  <p className="text-xs mt-1">Status: {c.status}</p>
                  <p className="text-xs">{c.location_name}</p>
                  <p className="text-xs text-slate-500">
                    Last connected: {c.last_connected_at ? new Date(c.last_connected_at).toLocaleString() : "never"}
                  </p>
                  {c.is_demo && <p className="mt-1 text-[10px] font-bold uppercase text-amber-600">demo camera</p>}
                </div>
              </Popup>
            </Marker>
          ))}

          {sightings.map((s) => (
            <Marker key={`s-${s.event_id}`} position={[s.latitude, s.longitude]} icon={sightingIcon}>
              <Popup>
                <div className="text-slate-900" style={{ minWidth: 200 }}>
                  <p className="font-mono text-sm font-semibold">{s.registration_number ?? "Unreadable plate"}</p>
                  <p className="text-xs">{s.object_class} · conf {(100 * (s.confidence ?? 0)).toFixed(0)}%</p>
                  <p className="text-xs">{s.camera_name}</p>
                  <p className="text-xs text-slate-500">{new Date(s.timestamp).toLocaleString()}</p>
                  {s.registration_number && (
                    <button
                      className="mt-1 rounded bg-blue-600 px-2 py-1 text-[11px] text-white"
                      onClick={() => {
                        // resolve vehicle id through search endpoint
                        api
                          .get("/vehicles", { params: { registration_number: s.registration_number, page_size: 1 } })
                          .then((r) => {
                            const items = r.data.items as { id: number }[];
                            if (items.length) openPath(items[0].id);
                          })
                          .catch(() => alert("Could not resolve vehicle"));
                      }}
                    >
                      Show movement path
                    </button>
                  )}
                </div>
              </Popup>
            </Marker>
          ))}

          {path && path.points.length >= 2 && (
            <Polyline positions={path.points.map((p) => [p.latitude, p.longitude])} pathOptions={{ color: "#3B82F6", weight: 3, dashArray: "6 6" }} />
          )}
          {path &&
            path.points.map((p, i) => (
              <CircleMarker key={`p-${p.event_id}`} center={[p.latitude, p.longitude]} radius={5} pathOptions={{ color: "#FFFFFF", fillColor: "#2563EB", fillOpacity: 1, weight: 2 }}>
                <Popup>
                  {i + 1}/{path.points.length}: {p.camera_name} @ {new Date(p.timestamp).toLocaleTimeString()}
                </Popup>
              </CircleMarker>
            ))}
        </MapContainer>
      </div>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <div className="card p-4">
          <p className="card-title mb-2">Sightings timeline ({sightings.length})</p>
          {sightings.length === 0 ? (
            <EmptyState title="No sightings match the filters" />
          ) : (
            <div className="max-h-48 space-y-1.5 overflow-y-auto">
              {sightings.slice(0, 50).map((s) => (
                <div key={s.event_id} className="flex items-center justify-between gap-2 text-xs">
                  <span className="font-mono">{s.registration_number ?? "—"}</span>
                  <span className="text-muted truncate">{s.camera_name}</span>
                  <span className="tabular-nums text-muted">{new Date(s.timestamp).toLocaleString()}</span>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="card p-4 space-y-2">
          <p className="card-title">Legend & data policy</p>
          <p className="flex items-center gap-2 text-xs"><span className="h-3 w-3 rounded-full bg-ok" /> Online camera</p>
          <p className="flex items-center gap-2 text-xs"><span className="h-3 w-3 rounded-full bg-crit" /> Offline camera</p>
          <p className="flex items-center gap-2 text-xs"><span className="h-2.5 w-2.5 rotate-45 bg-accent-bright" /> Vehicle sighting (plate read)</p>
          <p className="flex items-center gap-2 text-xs"><span className="h-0.5 w-6 border-t-2 border-dashed border-accent-bright" /> Recorded movement sequence</p>
          <ShieldNote>
            Markers appear only where cameras have coordinates and sightings were actually recorded. Lines connect
            recorded sightings in time order; they do not represent an inferred route between them.
          </ShieldNote>
        </div>
      </div>
    </div>
  );
}
