import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Eye, EyeOff, ListFilter, Plus, ShieldAlert, Trash2 } from "lucide-react";
import { api, errMessage, mediaUrl } from "../api/client";
import type { WatchlistCategory, WatchlistCheck, WatchlistEntry, WatchlistHit } from "../api/types";
import { Badge, DemoBadge, EmptyState, ErrorState, Loading, Modal, ShieldNote } from "../components/ui";
import { useAuth } from "../context/AuthContext";

const CATEGORIES: { value: WatchlistCategory; label: string }[] = [
  { value: "stolen_vehicle", label: "Stolen vehicle" },
  { value: "wanted_person", label: "Wanted person" },
  { value: "missing_person", label: "Missing person" },
  { value: "blacklist", label: "Blacklisted vehicle" },
  { value: "custom", label: "Custom" },
];

interface EntryForm {
  category: WatchlistCategory;
  identifier_value: string;
  title: string;
  notes: string;
  severity: "info" | "warning" | "critical";
}

const EMPTY_FORM: EntryForm = { category: "stolen_vehicle", identifier_value: "", title: "", notes: "", severity: "warning" };

export default function Watchlist() {
  const { user } = useAuth();
  const canEdit = user?.role === "admin" || user?.role === "operator";
  const [entries, setEntries] = useState<WatchlistEntry[] | null>(null);
  const [hits, setHits] = useState<WatchlistHit[]>([]);
  const [error, setError] = useState("");
  const [category, setCategory] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<WatchlistEntry | null>(null);
  const [form, setForm] = useState<EntryForm>(EMPTY_FORM);
  const [checkPlate, setCheckPlate] = useState("");
  const [checkResult, setCheckResult] = useState<WatchlistCheck | null>(null);

  const load = useCallback(async () => {
    try {
      const [e, h] = await Promise.all([
        api.get<WatchlistEntry[]>("/watchlist", { params: { category: category || undefined } }),
        api.get<WatchlistHit[]>("/watchlist/hits", { params: { limit: 50 } }),
      ]);
      setEntries(e.data);
      setHits(h.data);
      setError("");
    } catch (err) {
      setError(errMessage(err));
    }
  }, [category]);

  useEffect(() => {
    load();
  }, [load]);

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setShowForm(true);
  };

  const openEdit = (entry: WatchlistEntry) => {
    setEditing(entry);
    setForm({
      category: entry.category,
      identifier_value: entry.display_value,
      title: entry.title,
      notes: entry.notes,
      severity: entry.severity,
    });
    setShowForm(true);
  };

  const submitForm = async () => {
    if (!form.identifier_value.trim()) return;
    try {
      if (editing) {
        await api.patch(`/watchlist/${editing.id}`, {
          category: form.category,
          title: form.title,
          notes: form.notes,
          severity: form.severity,
        });
      } else {
        await api.post("/watchlist", form);
      }
      setShowForm(false);
      load();
    } catch (err) {
      alert(errMessage(err));
    }
  };

  const toggleActive = async (entry: WatchlistEntry) => {
    try {
      await api.patch(`/watchlist/${entry.id}`, { active: !entry.active });
      load();
    } catch (err) {
      alert(errMessage(err));
    }
  };

  const remove = async (entry: WatchlistEntry) => {
    if (!window.confirm(`Delete watchlist entry ${entry.display_value}? Deleting this entry also removes its recorded hits.`)) return;
    try {
      await api.delete(`/watchlist/${entry.id}`);
      load();
    } catch (err) {
      alert(errMessage(err));
    }
  };

  const runCheck = async () => {
    if (!checkPlate.trim()) return;
    try {
      const r = await api.get<WatchlistCheck>(`/watchlist/check/${encodeURIComponent(checkPlate.trim())}`);
      setCheckResult(r.data);
    } catch (err) {
      alert(errMessage(err));
    }
  };

  return (
    <div className="space-y-4">
      <ShieldNote>
        <span className="flex items-center gap-1.5 font-semibold"><ShieldAlert className="h-3.5 w-3.5" /> Watchlist policy — </span>
        Matches are generated from <strong>ANPR plate reads only</strong> and always require human verification before any
        action. Entries marked <em>demo</em> are representative records for this hackathon demonstration, not real cases.
      </ShieldNote>

      {/* Quick lookup */}
      <div className="card p-4">
        <div className="flex flex-wrap items-center gap-3">
          <ListFilter className="h-4 w-4 text-muted" />
          <input
            className="input w-64 font-mono"
            placeholder="Check a plate against the watchlist…"
            value={checkPlate}
            onChange={(e) => setCheckPlate(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && runCheck()}
          />
          <button className="btn-primary text-xs" onClick={runCheck} disabled={!checkPlate.trim()}>Check</button>
          {checkResult && (
            <span className={`badge ${checkResult.on_watchlist ? "bg-crit/10 text-crit border border-crit/30" : "bg-ok/10 text-ok border border-ok/30"}`}>
              {checkResult.on_watchlist ? `MATCH — ${checkResult.entries.map((e) => e.category.replace(/_/g, " ")).join(", ")}` : "not on watchlist"}
            </span>
          )}
          {canEdit && (
            <button className="btn-primary ml-auto text-xs" onClick={openCreate}>
              <Plus className="h-3.5 w-3.5" /> Add entry
            </button>
          )}
        </div>
      </div>

      {error && <ErrorState message={error} onRetry={load} />}
      {!entries && !error && <Loading label="Loading watchlist…" />}

      {entries && (
        <div className="card">
          <div className="card-header">
            <span className="card-title">Watchlist entries ({entries.length})</span>
            <select className="input w-44 text-xs" value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">All categories</option>
              {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </div>
          {entries.length === 0 ? (
            <EmptyState title="No watchlist entries" hint={canEdit ? "Add a plate to start automatic matching on ANPR reads." : "Entries appear here once an operator adds them."} />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200">
                    <th className="table-head px-4 py-3">Identifier</th>
                    <th className="table-head px-4 py-3">Category</th>
                    <th className="table-head px-4 py-3">Title / notes</th>
                    <th className="table-head px-4 py-3">Severity</th>
                    <th className="table-head px-4 py-3">Hits</th>
                    <th className="table-head px-4 py-3">Status</th>
                    <th className="table-head px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((entry) => (
                    <tr key={entry.id} className="border-b border-slate-100 hover:bg-slate-50">
                      <td className="px-4 py-3 font-mono font-semibold flex items-center gap-2">
                        {entry.display_value || entry.identifier_value} <DemoBadge isDemo={entry.is_demo} />
                      </td>
                      <td className="px-4 py-3 text-xs capitalize">{entry.category.replace(/_/g, " ")}</td>
                      <td className="px-4 py-3 text-xs max-w-xs truncate" title={entry.notes}>{entry.title || entry.notes || "—"}</td>
                      <td className="px-4 py-3"><Badge value={entry.severity} /></td>
                      <td className="px-4 py-3 tabular-nums">{entry.hit_count}</td>
                      <td className="px-4 py-3"><Badge value={entry.active ? "active" : "disabled"} /></td>
                      <td className="px-4 py-3 text-right">
                        {canEdit && (
                          <div className="flex justify-end gap-1">
                            <button className="btn-ghost text-xs" onClick={() => toggleActive(entry)} title={entry.active ? "Deactivate" : "Activate"}>
                              {entry.active ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                            </button>
                            <button className="btn-ghost text-xs" onClick={() => openEdit(entry)}>Edit</button>
                            <button className="btn-ghost text-xs text-crit" onClick={() => remove(entry)}><Trash2 className="h-3.5 w-3.5" /></button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Recent hits */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Recent hits ({hits.length})</span>
        </div>
        {hits.length === 0 ? (
          <EmptyState title="No watchlist hits yet" hint="When a watched plate is read by ANPR, the match appears here and raises an alert." />
        ) : (
          <div className="divide-y divide-slate-100">
            {hits.map((hit) => (
              <div key={hit.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                {hit.evidence_path ? (
                  <img src={mediaUrl(hit.evidence_path) ?? ""} alt="evidence" className="h-10 w-16 rounded border border-slate-200 object-cover" />
                ) : (
                  <div className="flex h-10 w-16 items-center justify-center rounded bg-slate-50 text-[10px] text-muted">no image</div>
                )}
                <div className="min-w-0">
                  <p className="font-mono text-sm font-bold">{hit.plate_text}</p>
                  <p className="text-[11px] text-muted tabular-nums">
                    OCR {(hit.ocr_confidence * 100).toFixed(0)}% · {new Date(hit.timestamp).toLocaleString()} · camera #{hit.camera_id ?? "—"}
                  </p>
                </div>
                <DemoBadge isDemo={hit.is_demo} />
                <div className="ml-auto flex items-center gap-2">
                  {hit.acknowledged ? (
                    <Badge value="acknowledged" />
                  ) : (
                    canEdit && (
                      <button
                        className="btn-ghost text-xs"
                        onClick={async () => {
                          try {
                            await api.post(`/watchlist/hits/${hit.id}/ack`);
                            load();
                          } catch (err) {
                            alert(errMessage(err));
                          }
                        }}
                      >
                        <CheckCircle2 className="h-3.5 w-3.5" /> Ack
                      </button>
                    )
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {showForm && (
        <Modal title={editing ? `Edit entry — ${editing.display_value}` : "Add watchlist entry"} onClose={() => setShowForm(false)}>
          <div className="space-y-3">
            {!editing && (
              <div>
                <label className="mb-1 block text-xs font-semibold text-muted">Plate / identifier</label>
                <input
                  className="input font-mono"
                  placeholder="e.g. GJ01AB1234"
                  value={form.identifier_value}
                  onChange={(e) => setForm({ ...form, identifier_value: e.target.value.toUpperCase() })}
                />
              </div>
            )}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs font-semibold text-muted">Category</label>
                <select className="input" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value as WatchlistCategory })}>
                  {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-semibold text-muted">Severity</label>
                <select className="input" value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value as EntryForm["severity"] })}>
                  <option value="info">Info</option>
                  <option value="warning">Warning</option>
                  <option value="critical">Critical</option>
                </select>
              </div>
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-muted">Title</label>
              <input className="input" placeholder="Short title for alerts" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-muted">Notes</label>
              <textarea className="input min-h-20" placeholder="Case reference, description…" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </div>
            <p className="text-[11px] text-muted">
              Matching runs on confirmed ANPR plate reads above the configured confidence threshold. The identifier is
              normalized (uppercase, separators removed) on both sides.
            </p>
            <div className="flex justify-end gap-2">
              <button className="btn-ghost text-xs" onClick={() => setShowForm(false)}>Cancel</button>
              <button className="btn-primary text-xs" onClick={submitForm} disabled={!form.identifier_value.trim()}>
                {editing ? "Save changes" : "Add to watchlist"}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
