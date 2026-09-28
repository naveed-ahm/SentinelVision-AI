import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity, AlertTriangle, Camera as CameraIcon, CircleDot, Radar, Siren, Video,
} from "lucide-react";
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid, Legend,
} from "recharts";
import { api, errMessage, mediaUrl } from "../api/client";
import type {
  AlertPage, AlertTypeBreakdown, Camera, CameraAvailability, ClassBreakdown, OverviewStats,
  RecentDetection, TimeSeriesPoint,
} from "../api/types";
import { Badge, DemoBadge, ErrorState, Loading, StatCard } from "../components/ui";
import { CameraTile } from "../components/CameraTile";

const CLASS_COLORS: Record<string, string> = {
  car: "#3B82F6", motorcycle: "#A855F7", bus: "#F59E0B", truck: "#F97316", person: "#14B8A6",
};

export default function Overview() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [cameras, setCameras] = useState<Camera[] | null>(null);
  const [recent, setRecent] = useState<RecentDetection[] | null>(null);
  const [alerts, setAlerts] = useState<AlertPage | null>(null);
  const [series, setSeries] = useState<TimeSeriesPoint[]>([]);
  const [classes, setClasses] = useState<ClassBreakdown[]>([]);
  const [availability, setAvailability] = useState<CameraAvailability[]>([]);
  const [alertTypes, setAlertTypes] = useState<AlertTypeBreakdown[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError("");
    try {
      const [s, c, r, a, ts, cb, av, ab] = await Promise.all([
        api.get<OverviewStats>("/analytics/overview"),
        api.get<Camera[]>("/cameras"),
        api.get<RecentDetection[]>("/analytics/recent-detections", { params: { limit: 8 } }),
        api.get<AlertPage>("/alerts", { params: { page_size: 6 } }),
        api.get<TimeSeriesPoint[]>("/analytics/detections-series", { params: { hours: 24, buckets: 24 } }),
        api.get<ClassBreakdown[]>("/analytics/class-breakdown", { params: { hours: 24 } }),
        api.get<CameraAvailability[]>("/analytics/camera-availability"),
        api.get<AlertTypeBreakdown[]>("/analytics/alert-breakdown", { params: { days: 7 } }),
      ]);
      setStats(s.data);
      setCameras(c.data);
      setRecent(r.data);
      setAlerts(a.data);
      setSeries(ts.data.map((p) => ({ ...p, bucket: new Date(p.bucket).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) })));
      setClasses(cb.data);
      setAvailability(av.data);
      setAlertTypes(ab.data);
      setAlertTypes(ab.data);
    } catch (e) {
      setError(errMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [load]);

  if (loading) return <Loading label="Loading command center…" />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div className="space-y-4">
      {stats?.demo_mode && (
        <div className="flex items-center gap-2 rounded-md border border-warn/40 bg-warn/10 px-3 py-2 text-xs text-warn">
          <AlertTriangle className="h-4 w-4" />
          Demonstration mode — camera metadata and event history are synthetic and labeled DEMO. No real CCTV feeds are connected.
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Cameras" value={stats?.cameras_total} icon={CameraIcon} />
        <StatCard label="Online" value={stats?.cameras_online} icon={CircleDot} tone="ok" />
        <StatCard label="Offline" value={stats?.cameras_offline} icon={Video} tone="crit" />
        <StatCard label="Active streams" value={stats?.streams_active} icon={Activity} tone="ok" />
        <StatCard label="Vehicles today" value={stats?.detections_today} icon={Radar} />
        <StatCard label="ANPR reads today" value={stats?.anpr_today} icon={Radar} tone="ok" />
        <StatCard label="Open alerts" value={stats?.alerts_open} icon={Siren} tone={stats?.alerts_open ? "crit" : "muted"} />
        <StatCard label="Total events" value={stats?.events_total} icon={Activity} tone="muted" />
      </div>

      {/* Live previews */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Camera previews</span>
          <button className="btn-ghost text-xs" onClick={() => navigate("/monitoring")}>Open monitoring</button>
        </div>
        <div className="grid grid-cols-1 gap-3 p-4 sm:grid-cols-2 xl:grid-cols-3">
          {(cameras ?? []).slice(0, 6).map((cam) => (
            <CameraTile key={cam.id} camera={cam} compact openMonitoring={(id) => navigate(`/monitoring?focus=${id}`)} />
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {/* Recent detections */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Recent vehicle detections</span>
            <button className="btn-ghost text-xs" onClick={() => navigate("/events")}>Event history</button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200">
                  <th className="table-head px-4 py-2">Vehicle</th>
                  <th className="table-head px-4 py-2">Plate</th>
                  <th className="table-head px-4 py-2">Camera</th>
                  <th className="table-head px-4 py-2">Time</th>
                  <th className="table-head px-4 py-2">Conf.</th>
                </tr>
              </thead>
              <tbody>
                {(recent ?? []).length === 0 && (
                  <tr><td colSpan={5} className="px-4 py-6 text-center text-muted text-xs">No detections recorded yet</td></tr>
                )}
                {(recent ?? []).map((d) => (
                  <tr key={d.id} className="border-b border-slate-100 hover:bg-slate-50">
                    <td className="px-4 py-2">
                      {d.image_path ? (
                        <img src={mediaUrl(d.image_path) ?? ""} alt="" className="h-9 w-14 rounded object-cover" />
                      ) : (
                        <div className="flex h-9 w-14 items-center justify-center rounded bg-slate-100 text-muted"><Video className="h-4 w-4" /></div>
                      )}
                    </td>
                    <td className="px-4 py-2 font-mono text-xs">{d.plate_text ?? <span className="text-muted">—</span>}</td>
                    <td className="px-4 py-2 text-xs">{d.camera_name}</td>
                    <td className="px-4 py-2 text-xs tabular-nums">{new Date(d.timestamp).toLocaleTimeString()}</td>
                    <td className="px-4 py-2"><Badge value={d.object_class} /> <span className="text-xs tabular-nums text-muted">{(d.confidence * 100).toFixed(0)}%</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Recent alerts */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Recent alerts</span>
            <button className="btn-ghost text-xs" onClick={() => navigate("/alerts")}>All alerts</button>
          </div>
          <div className="divide-y divide-slate-100">
            {(alerts?.items.length ?? 0) === 0 && (
              <p className="px-4 py-6 text-center text-xs text-muted">No alerts recorded</p>
            )}
            {alerts?.items.map((a) => (
              <div key={a.id} className="flex items-center justify-between gap-3 px-4 py-2.5 hover:bg-slate-50">
                <div className="min-w-0">
                  <p className="truncate text-sm">{a.title}</p>
                  <p className="text-[11px] text-muted">{new Date(a.created_at).toLocaleString()}</p>
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  <Badge value={a.severity} />
                  <Badge value={a.status} />
                  <DemoBadge isDemo={a.is_demo} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <div className="card p-4">
          <p className="card-title mb-3">Vehicle detections — last 24h</p>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={series}>
                <defs>
                  <linearGradient id="fillBlue" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#2563EB" stopOpacity={0.5} />
                    <stop offset="100%" stopColor="#2563EB" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" />
                <XAxis dataKey="bucket" tick={{ fill: "#64748B", fontSize: 10 }} tickLine={false} axisLine={{ stroke: "#E2E8F0" }} interval={4} />
                <YAxis tick={{ fill: "#64748B", fontSize: 10 }} tickLine={false} axisLine={false} allowDecimals={false} />
                <Tooltip contentStyle={{ background: "#FFFFFF", border: "1px solid #E2E8F0", borderRadius: 8, fontSize: 12 }} />
                <Area type="monotone" dataKey="count" name="Detections" stroke="#3B82F6" fill="url(#fillBlue)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-4">
          <p className="card-title mb-3">Vehicle categories — 24h</p>
          <div className="h-56">
            {(classes.length === 0) ? (
              <p className="flex h-full items-center justify-center text-xs text-muted">No class data yet</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={classes} dataKey="count" nameKey="object_class" innerRadius={50} outerRadius={80} paddingAngle={3}>
                    {classes.map((c) => (
                      <Cell key={c.object_class} fill={CLASS_COLORS[c.object_class] ?? "#64748B"} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: "#FFFFFF", border: "1px solid #E2E8F0", borderRadius: 8, fontSize: 12 }} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        <div className="card p-4">
          <p className="card-title mb-3">Camera availability</p>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={availability} layout="vertical" margin={{ left: 30 }}>
                <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" />
                <XAxis type="number" domain={[0, 100]} tick={{ fill: "#64748B", fontSize: 10 }} tickLine={false} axisLine={false} unit="%" />
                <YAxis type="category" dataKey="name" width={140} tick={{ fill: "#64748B", fontSize: 10 }} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: "#FFFFFF", border: "1px solid #E2E8F0", borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="uptime_pct" name="Uptime" radius={[0, 4, 4, 0]}>
                  {availability.map((c) => (
                    <Cell key={c.camera_id} fill={c.status === "online" ? "#16A34A" : "#DC2626"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-4">
          <p className="card-title mb-3">Alert distribution — 7 days</p>
          <div className="h-56">
            {alertTypes.length === 0 ? (
              <p className="flex h-full items-center justify-center text-xs text-muted">No alerts in the last 7 days</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={alertTypes.map((t) => ({ name: t.alert_type.replace(/_/g, " "), count: t.count, severity: t.severity }))}>
                  <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" />
                  <XAxis dataKey="name" tick={{ fill: "#64748B", fontSize: 10 }} tickLine={false} axisLine={{ stroke: "#E2E8F0" }} />
                  <YAxis allowDecimals={false} tick={{ fill: "#64748B", fontSize: 10 }} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={{ background: "#FFFFFF", border: "1px solid #E2E8F0", borderRadius: 8, fontSize: 12 }} />
                  <Bar dataKey="count" name="Alerts" fill="#F59E0B" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
