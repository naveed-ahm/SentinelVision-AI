import { useCallback, useEffect, useState } from "react";
import { api, errMessage } from "../api/client";
import type { SettingItem } from "../api/types";
import { ErrorState, Loading, ShieldNote } from "../components/ui";
import { useAuth } from "../context/AuthContext";

interface About {
  app: string;
  environment: string;
  demo_mode: boolean;
  demo_notice: string;
  max_streams: number;
}

export default function Settings() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [items, setItems] = useState<SettingItem[] | null>(null);
  const [about, setAbout] = useState<About | null>(null);
  const [error, setError] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState("");

  const load = useCallback(async () => {
    try {
      const [s, a] = await Promise.all([api.get<SettingItem[]>("/settings"), api.get<About>("/settings/about")]);
      setItems(s.data);
      setAbout(a.data);
      setError("");
    } catch (e) {
      setError(errMessage(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const save = async (item: SettingItem) => {
    const value = drafts[item.key];
    if (value === undefined || value === item.value) return;
    try {
      await api.put(`/settings/${item.key}`, { value });
      setSaved(`${item.key} updated`);
      setTimeout(() => setSaved(""), 3000);
      load();
    } catch (e) {
      alert(errMessage(e));
    }
  };

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!items || !about) return <Loading label="Loading settings…" />;

  return (
    <div className="max-w-3xl space-y-4">
      <div className="card p-4">
        <p className="card-title mb-2">Platform</p>
        <div className="space-y-1 text-sm">
          <p className="flex justify-between"><span className="text-muted">Application</span><span>{about.app}</span></p>
          <p className="flex justify-between"><span className="text-muted">Environment</span><span className="capitalize">{about.environment}</span></p>
          <p className="flex justify-between"><span className="text-muted">Max concurrent streams</span><span className="tabular-nums">{about.max_streams}</span></p>
          <p className="flex justify-between">
            <span className="text-muted">Demonstration mode</span>
            <span className={about.demo_mode ? "text-warn" : "text-ok"}>{about.demo_mode ? "ENABLED" : "disabled"}</span>
          </p>
        </div>
        <div className="mt-3">
          <ShieldNote>{about.demo_notice}</ShieldNote>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">Detection & alert tuning</span>
          {!isAdmin && <span className="text-xs text-muted">read-only (admin required)</span>}
        </div>
        <div className="divide-y divide-slate-100">
          {items.map((item) => (
            <div key={item.key} className="flex flex-wrap items-center gap-3 px-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="font-mono text-sm">{item.key}</p>
                <p className="text-[11px] text-muted">
                  {item.updated_at ? `updated ${new Date(item.updated_at).toLocaleString()} by ${item.updated_by || "—"}` : "default value"}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {["true", "false"].includes(item.value.toLowerCase()) ? (
                  <select
                    className="input w-24 py-1"
                    disabled={!isAdmin}
                    value={drafts[item.key] ?? item.value}
                    onChange={(e) => setDrafts((d) => ({ ...d, [item.key]: e.target.value }))}
                  >
                    <option value="true">true</option>
                    <option value="false">false</option>
                  </select>
                ) : (
                  <input
                    className="input w-32 py-1 font-mono text-xs"
                    disabled={!isAdmin}
                    value={drafts[item.key] ?? item.value}
                    onChange={(e) => setDrafts((d) => ({ ...d, [item.key]: e.target.value }))}
                  />
                )}
                {isAdmin && drafts[item.key] !== undefined && drafts[item.key] !== item.value && (
                  <button className="btn-primary text-xs" onClick={() => save(item)}>Save</button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {saved && <p className="text-xs text-ok">{saved}</p>}
    </div>
  );
}
