import { useCallback, useEffect, useState } from "react";
import { api, errMessage } from "../api/client";
import type { AuditLog } from "../api/types";
import { Badge, ErrorState, Loading, Pagination } from "../components/ui";
import { useAuth } from "../context/AuthContext";

interface ComponentHealth {
  component: string;
  status: string;
  detail: string;
  cpu_percent: number;
  memory_percent: number;
  checked_at: string | null;
}

export default function Health() {
  const { user } = useAuth();
  const [comps, setComps] = useState<ComponentHealth[] | null>(null);
  const [logs, setLogs] = useState<AuditLog[] | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");

  const loadComps = useCallback(async () => {
    try {
      const r = await api.get<ComponentHealth[]>("/health");
      setComps(r.data);
      setError("");
    } catch (e) {
      setError(errMessage(e));
    }
  }, []);

  const loadLogs = useCallback(async () => {
    if (user?.role !== "admin") return;
    try {
      const r = await api.get("/audit-logs", { params: { page, page_size: 25 } });
      setLogs(r.data.items);
      setTotal(r.data.total);
    } catch {
      setLogs(null);
    }
  }, [page, user?.role]);

  useEffect(() => {
    loadComps();
    const t = setInterval(loadComps, 15000);
    return () => clearInterval(t);
  }, [loadComps]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  if (error) return <ErrorState message={error} onRetry={loadComps} />;
  if (!comps) return <Loading label="Checking system health…" />;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {comps.map((c) => (
          <div key={c.component} className="card p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold capitalize">{c.component.replace(/_/g, " ")}</p>
              <Badge value={c.status === "online" ? "online" : c.status === "degraded" ? "warning" : "critical"} />
            </div>
            <p className="mt-1 text-xs text-muted break-words">{c.detail || "—"}</p>
            {(c.cpu_percent > 0 || c.memory_percent > 0) && (
              <p className="mt-2 text-[11px] tabular-nums text-muted">
                CPU {c.cpu_percent.toFixed(0)}% · MEM {c.memory_percent.toFixed(0)}%
              </p>
            )}
            <p className="mt-1 text-[11px] text-muted">{c.checked_at ? new Date(c.checked_at).toLocaleString() : ""}</p>
          </div>
        ))}
      </div>

      {user?.role === "admin" && (
        <div className="card">
          <div className="card-header">
            <span className="card-title">Audit trail</span>
            <span className="text-xs text-muted">{total} entries</span>
          </div>
          {!logs ? (
            <Loading label="Loading audit logs…" />
          ) : logs.length === 0 ? (
            <p className="px-4 py-6 text-center text-xs text-muted">No audit entries yet.</p>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200">
                      <th className="table-head px-4 py-2">Time</th>
                      <th className="table-head px-4 py-2">User</th>
                      <th className="table-head px-4 py-2">Action</th>
                      <th className="table-head px-4 py-2">Resource</th>
                      <th className="table-head px-4 py-2">Detail</th>
                      <th className="table-head px-4 py-2">IP</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.map((l) => (
                      <tr key={l.id} className="border-b border-slate-100 hover:bg-slate-50">
                        <td className="px-4 py-2 text-xs tabular-nums">{new Date(l.timestamp).toLocaleString()}</td>
                        <td className="px-4 py-2 text-xs">{l.username}</td>
                        <td className="px-4 py-2 text-xs font-mono">{l.action}</td>
                        <td className="px-4 py-2 text-xs">{l.resource}</td>
                        <td className="px-4 py-2 text-xs text-muted max-w-xs truncate">{l.detail}</td>
                        <td className="px-4 py-2 text-xs text-muted">{l.ip_address}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination page={page} pageSize={25} total={total} onPage={setPage} />
            </>
          )}
        </div>
      )}
    </div>
  );
}
