import { useCallback, useEffect, useState } from "react";
import { MapPin, Route, Sparkles } from "lucide-react";
import { api, errMessage } from "../api/client";
import type { Vehicle, VehiclePage } from "../api/types";
import { DemoBadge, EmptyState, ErrorState, Loading, ShieldNote } from "../components/ui";

interface AttrInfo {
  vehicle_type: string;
  color: string;
  body_style: string;
  color_confidence: number;
}

interface Timeline {
  registration_number: string;
  total_sightings: number;
  first_seen: string | null;
  last_seen: string | null;
  camera_sequence: {
    camera_id: number;
    camera_name: string;
    location: string;
    latitude: number | null;
    longitude: number | null;
    timestamp: string;
  }[];
  note: string;
}

export default function Tracking() {
  const [vehicles, setVehicles] = useState<VehiclePage | null>(null);
  const [error, setError] = useState("");
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [attrs, setAttrs] = useState<Record<string, AttrInfo>>({});

  const loadAttrs = useCallback(async () => {
    // Optional AI-module attributes (single batched request; never blocking).
    try {
      const r = await api.get<Record<string, AttrInfo>>("/ai-modules/attributes/recent-by-vehicle");
      setAttrs(r.data ?? {});
    } catch {
      setAttrs({}); // attributes are optional
    }
  }, []);

  useEffect(() => {
    api
      .get<Vehicle[]>("/vehicles/tracked", { params: { limit: 30 } })
      .then((r) => {
        setVehicles({ items: r.data, total: r.data.length, page: 1, page_size: 30 });
        loadAttrs();
      })
      .catch((e) => setError(errMessage(e)));
  }, [loadAttrs]);

  const openTimeline = async (v: Vehicle) => {
    try {
      const r = await api.get<Timeline>(`/vehicles/${v.id}/timeline`);
      setTimeline(r.data);
    } catch (e) {
      alert(errMessage(e));
    }
  };

  if (error) return <ErrorState message={error} />;
  if (!vehicles) return <Loading label="Loading tracked vehicles…" />;

  return (
    <div className="space-y-4">
      <ShieldNote>
        Cross-camera correlation is built from <strong>confirmed plate reads only</strong> (OCR confidence ≥ threshold).
        Vehicles without a recognized plate are tracked within a single camera (tracking ID) but are never linked
        across cameras by appearance alone.
      </ShieldNote>

      {vehicles.items.length === 0 ? (
        <EmptyState title="No tracked vehicles yet" hint="Vehicles appear here after confirmed ANPR reads." />
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {vehicles.items.map((v) => (
            <div key={v.id} className="card p-4">
              <div className="flex items-center justify-between">
                <p className="font-mono text-sm font-bold flex items-center gap-2">
                  {v.registration_number} <DemoBadge isDemo={v.is_demo} />
                </p>
                <span className="badge bg-accent/15 text-accent-bright border border-accent/30">{v.total_sightings} sightings</span>
              </div>
              <p className="mt-1 text-xs text-muted capitalize">{v.vehicle_class || "unknown type"}</p>
              {attrs[String(v.id)]?.color && (
                <p className="mt-1 flex items-center gap-1 text-[11px] text-accent-bright">
                  <Sparkles className="h-3 w-3" /> AI: {attrs[String(v.id)].color} {attrs[String(v.id)].vehicle_type}
                  {(attrs[String(v.id)].color_confidence ?? 0) > 0 &&
                    ` · ${(attrs[String(v.id)].color_confidence * 100).toFixed(0)}%`}
                </p>
              )}
              <p className="text-[11px] text-muted tabular-nums">Last seen {new Date(v.last_seen_at).toLocaleString()}</p>
              <button className="btn-ghost mt-3 w-full justify-center text-xs" onClick={() => openTimeline(v)}>
                <Route className="h-3.5 w-3.5" /> Camera sequence
              </button>
            </div>
          ))}
        </div>
      )}

      {timeline && (
        <div className="card p-4" onClick={() => setTimeline(null)}>
          <p className="card-title mb-3 flex items-center gap-2">
            <MapPin className="h-4 w-4 text-accent-bright" />
            Camera sequence — {timeline.registration_number}
          </p>
          <ol className="relative ml-3 border-l border-slate-600">
            {timeline.camera_sequence.map((s, i) => (
              <li key={`${s.camera_id}-${i}`} className="mb-4 ml-6">
                <span className="absolute -left-[7px] flex h-3.5 w-3.5 items-center justify-center rounded-full bg-accent ring-4 ring-accent/20" />
                <p className="text-sm font-medium">{s.camera_name}</p>
                <p className="text-[11px] text-muted">
                  {s.location} · {new Date(s.timestamp).toLocaleString()}
                </p>
              </li>
            ))}
          </ol>
          <p className="text-[11px] text-muted">{timeline.note}</p>
        </div>
      )}
    </div>
  );
}
