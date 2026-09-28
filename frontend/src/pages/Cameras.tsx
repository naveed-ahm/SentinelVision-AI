import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Pencil, Plus, PlugZap, Power, Search, Trash2 } from "lucide-react";
import { api, errMessage } from "../api/client";
import type { Camera, CameraInput, CameraTestResult } from "../api/types";
import { Badge, DemoBadge, ErrorState, Loading, Modal } from "../components/ui";
import { CameraFormModal } from "../components/CameraFormModal";
import { useAuth } from "../context/AuthContext";

export default function Cameras() {
  const { user } = useAuth();
  const canEdit = user?.role === "admin" || user?.role === "operator";
  const [cams, setCams] = useState<Camera[] | null>(null);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [sort, setSort] = useState("name");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Camera | null>(null);
  const [detail, setDetail] = useState<Camera | null>(null);
  const [testResult, setTestResult] = useState<Record<number, CameraTestResult>>({});
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await api.get<Camera[]>("/cameras", {
        params: { search: search || undefined, status: status || undefined, sort, order: "asc" },
      });
      setCams(r.data);
      setError("");
    } catch (e) {
      setError(errMessage(e));
    }
  }, [search, status, sort]);

  useEffect(() => {
    load();
  }, [load]);

  const save = async (payload: CameraInput) => {
    if (editing) {
      await api.patch(`/cameras/${editing.id}`, payload);
    } else {
      await api.post("/cameras", payload);
    }
    setFormOpen(false);
    setEditing(null);
    load();
  };

  const remove = async (cam: Camera) => {
    if (!confirm(`Delete camera ${cam.code}? This also removes its events and media.`)) return;
    try {
      await api.delete(`/cameras/${cam.id}`);
      load();
    } catch (e) {
      alert(errMessage(e));
    }
  };

  const toggleEnabled = async (cam: Camera) => {
    try {
      await api.post(`/cameras/${cam.id}/${cam.enabled ? "disable" : "enable"}`);
      load();
    } catch (e) {
      alert(errMessage(e));
    }
  };

  const test = async (cam: Camera) => {
    setBusy(true);
    try {
      const r = await api.post<CameraTestResult>(`/cameras/${cam.id}/test`);
      setTestResult((t) => ({ ...t, [cam.id]: r.data }));
    } catch (e) {
      alert(errMessage(e));
    } finally {
      setBusy(false);
    }
  };

  if (!cams && !error) return <Loading label="Loading cameras…" />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted" />
          <input className="input pl-9 w-64" placeholder="Search name / code / location…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <select className="input w-40" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="online">Online</option>
          <option value="offline">Offline</option>
          <option value="error">Error</option>
          <option value="disabled">Disabled</option>
        </select>
        <select className="input w-40" value={sort} onChange={(e) => setSort(e.target.value)}>
          <option value="name">Sort: Name</option>
          <option value="code">Sort: Code</option>
          <option value="status">Sort: Status</option>
          <option value="created_at">Sort: Created</option>
        </select>
        {canEdit && (
          <button className="btn-primary ml-auto" onClick={() => { setEditing(null); setFormOpen(true); }}>
            <Plus className="h-4 w-4" /> Register camera
          </button>
        )}
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200">
              <th className="table-head px-4 py-3">Camera</th>
              <th className="table-head px-4 py-3">Location</th>
              <th className="table-head px-4 py-3">Protocol</th>
              <th className="table-head px-4 py-3">Status</th>
              <th className="table-head px-4 py-3">Last connected</th>
              <th className="table-head px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {cams?.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-xs text-muted">No cameras registered yet.</td></tr>
            )}
            {cams?.map((cam) => (
              <tr key={cam.id} className="border-b border-slate-100 hover:bg-slate-50">
                <td className="px-4 py-3">
                  <button className="text-left" onClick={() => setDetail(cam)}>
                    <p className="font-medium flex items-center gap-1.5">
                      {cam.name} <DemoBadge isDemo={cam.is_demo} />
                    </p>
                    <p className="text-[11px] text-muted font-mono">{cam.code}</p>
                  </button>
                </td>
                <td className="px-4 py-3 text-xs">{cam.location_name || "—"}</td>
                <td className="px-4 py-3 text-xs uppercase">{cam.protocol}</td>
                <td className="px-4 py-3"><Badge value={cam.status} /></td>
                <td className="px-4 py-3 text-xs tabular-nums text-muted">
                  {cam.last_connected_at ? new Date(cam.last_connected_at).toLocaleString() : "never"}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-1">
                    <button className="btn-ghost text-xs" title="Test connection" disabled={busy} onClick={() => test(cam)}>
                      <PlugZap className="h-3.5 w-3.5" /> Test
                    </button>
                    {canEdit && (
                      <>
                        <button className="btn-ghost text-xs" title={cam.enabled ? "Disable" : "Enable"} onClick={() => toggleEnabled(cam)}>
                          <Power className={`h-3.5 w-3.5 ${cam.enabled ? "text-ok" : "text-muted"}`} />
                        </button>
                        <button className="btn-ghost text-xs" title="Edit" onClick={() => { setEditing(cam); setFormOpen(true); }}>
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                      </>
                    )}
                    {user?.role === "admin" && (
                      <button className="btn-ghost text-xs text-crit" title="Delete" onClick={() => remove(cam)}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Test result inline messages */}
      {Object.entries(testResult).map(([id, res]) => (
        <p key={id} className={`text-xs ${res.ok ? "text-ok" : "text-warn"}`}>
          {cams?.find((c) => c.id === Number(id))?.code}: {res.message}
          {res.latency_ms != null && ` (${res.latency_ms.toFixed(0)} ms)`}
        </p>
      ))}

      {formOpen && (
        <CameraFormModal camera={editing} onClose={() => { setFormOpen(false); setEditing(null); }} onSubmit={save} />
      )}

      {detail && (
        <Modal title={`Camera — ${detail.code}`} onClose={() => setDetail(null)} wide>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div><p className="label">Name</p><p>{detail.name}</p></div>
            <div><p className="label">Code</p><p className="font-mono">{detail.code}</p></div>
            <div><p className="label">Location</p><p>{detail.location_name || "—"}</p></div>
            <div>
              <p className="label">Coordinates</p>
              <p className="tabular-nums">
                {detail.latitude != null ? `${detail.latitude.toFixed(5)}, ${detail.longitude?.toFixed(5)}` : "not set"}
              </p>
            </div>
            <div><p className="label">Manufacturer</p><p>{detail.manufacturer || "—"}</p></div>
            <div><p className="label">Model</p><p>{detail.model || "—"}</p></div>
            <div><p className="label">Protocol</p><p className="uppercase">{detail.protocol}</p></div>
            <div><p className="label">Status</p><Badge value={detail.status} /></div>
            <div className="col-span-2"><p className="label">Stream URL (redacted)</p><p className="font-mono text-xs break-all">{detail.rtsp_url || "—"}</p></div>
            <div><p className="label">Last health check</p><p className="text-xs">{detail.last_health_check ? new Date(detail.last_health_check).toLocaleString() : "never"}</p></div>
            <div><p className="label">Last error</p><p className="text-xs text-crit">{detail.last_error || "—"}</p></div>
            <div className="col-span-2"><p className="label">Description</p><p className="text-xs">{detail.description || "—"}</p></div>
          </div>
          <div className="mt-4 flex justify-end gap-2">
            <Link className="btn-ghost" to={`/monitoring?focus=${detail.id}`}>Open in monitoring</Link>
            <Link className="btn-ghost" to={`/map?camera=${detail.id}`}>Show on map</Link>
          </div>
        </Modal>
      )}
    </div>
  );
}
