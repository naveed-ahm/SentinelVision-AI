import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, ListFilter } from "lucide-react";
import { api, errMessage } from "../api/client";
import type { AlertPage } from "../api/types";
import { Badge, DemoBadge, EmptyState, ErrorState, Loading, Pagination } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useLive } from "../context/LiveContext";

export default function Alerts() {
  const { user } = useAuth();
  const canAct = user?.role === "admin" || user?.role === "operator";
  const { lastAlert, refreshKey } = useLive();
  const [page, setPage] = useState(1);
  const [data, setData] = useState<AlertPage | null>(null);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [severity, setSeverity] = useState("");
  const [type, setType] = useState("");
  const pageSize = 20;

  const load = useCallback(async () => {
    try {
      const r = await api.get<AlertPage>("/alerts", {
        params: { page, page_size: pageSize, status: status || undefined, severity: severity || undefined, alert_type: type || undefined },
      });
      setData(r.data);
      setError("");
    } catch (e) {
      setError(errMessage(e));
    }
  }, [page, status, severity, type]);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  const act = async (id: number, action: "acknowledge" | "resolve") => {
    try {
      await api.post(`/alerts/${id}/${action}`);
      load();
    } catch (e) {
      alert(errMessage(e));
    }
  };

  return (
    <div className="space-y-4">
      {lastAlert && (
        <div className={`flex items-center gap-2 rounded-md border px-3 py-2 text-xs ${lastAlert.severity === "critical" ? "border-crit/40 bg-crit/10 text-crit" : lastAlert.severity === "warning" ? "border-warn/40 bg-warn/10 text-warn" : "border-accent/40 bg-accent/10 text-accent-bright"}`}>
          <span className="relative flex h-2 w-2"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-60" /><span className="relative inline-flex h-2 w-2 rounded-full bg-current" /></span>
          LIVE — {lastAlert.title} · {lastAlert.created_at ? new Date(lastAlert.created_at).toLocaleTimeString() : ""}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <ListFilter className="h-4 w-4 text-muted" />
        <select className="input w-40" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="acknowledged">Acknowledged</option>
          <option value="resolved">Resolved</option>
        </select>
        <select className="input w-40" value={severity} onChange={(e) => { setSeverity(e.target.value); setPage(1); }}>
          <option value="">All severities</option>
          <option value="critical">Critical</option>
          <option value="warning">Warning</option>
          <option value="info">Info</option>
        </select>
        <input className="input w-56" placeholder="Alert type (e.g. camera_offline)" value={type} onChange={(e) => { setType(e.target.value); setPage(1); }} />
      </div>

      {error && <ErrorState message={error} onRetry={load} />}
      {!data && !error && <Loading label="Loading alerts…" />}

      {data && (
        <div className="card">
          {data.items.length === 0 ? (
            <EmptyState title="No alerts match the filters" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200">
                    <th className="table-head px-4 py-3">Alert</th>
                    <th className="table-head px-4 py-3">Type</th>
                    <th className="table-head px-4 py-3">Severity</th>
                    <th className="table-head px-4 py-3">Status</th>
                    <th className="table-head px-4 py-3">Time</th>
                    <th className="table-head px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((a) => (
                    <tr key={a.id} className="border-b border-slate-100 hover:bg-slate-50">
                      <td className="px-4 py-3">
                        <p className="font-medium flex items-center gap-2">{a.title} <DemoBadge isDemo={a.is_demo} /></p>
                        <p className="text-[11px] text-muted max-w-md truncate">{a.description}</p>
                      </td>
                      <td className="px-4 py-3 text-xs">{a.alert_type.replace(/_/g, " ")}</td>
                      <td className="px-4 py-3"><Badge value={a.severity} /></td>
                      <td className="px-4 py-3"><Badge value={a.status} /></td>
                      <td className="px-4 py-3 text-xs tabular-nums text-muted">{new Date(a.created_at).toLocaleString()}</td>
                      <td className="px-4 py-3 text-right">
                        {canAct && a.status === "open" ? (
                          <div className="flex justify-end gap-1">
                            <button className="btn-ghost text-xs" onClick={() => act(a.id, "acknowledge")}>
                              <CheckCircle2 className="h-3.5 w-3.5" /> Ack
                            </button>
                            <button className="btn-ghost text-xs" onClick={() => act(a.id, "resolve")}>Resolve</button>
                          </div>
                        ) : (
                          <span className="text-[11px] text-muted">{a.acknowledged_at ? `ack ${new Date(a.acknowledged_at).toLocaleTimeString()}` : "—"}</span>
                        )}
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
    </div>
  );
}
