import { useCallback, useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { api, errMessage } from "../api/client";
import type { User } from "../api/types";
import { Badge, ErrorState, Loading, Modal } from "../components/ui";
import { useAuth } from "../context/AuthContext";

const EMPTY = { username: "", email: "", password: "", full_name: "", role: "viewer" };

export default function Users() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState<User[] | null>(null);
  const [error, setError] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);

  const load = useCallback(async () => {
    try {
      const r = await api.get<User[]>("/users");
      setUsers(r.data);
      setError("");
    } catch (e) {
      setError(errMessage(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const create = async () => {
    try {
      await api.post("/users", form);
      setCreateOpen(false);
      setForm(EMPTY);
      load();
    } catch (e) {
      alert(errMessage(e));
    }
  };

  const update = async (u: User, patch: Record<string, unknown>) => {
    try {
      await api.patch(`/users/${u.id}`, patch);
      load();
    } catch (e) {
      alert(errMessage(e));
    }
  };

  const remove = async (u: User) => {
    if (!confirm(`Delete user ${u.username}?`)) return;
    try {
      await api.delete(`/users/${u.id}`);
      load();
    } catch (e) {
      alert(errMessage(e));
    }
  };

  if (!users && !error) return <Loading label="Loading users…" />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted">Administrator, operator and viewer accounts with role-based permissions.</p>
        <button className="btn-primary" onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4" /> Add user
        </button>
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200">
              <th className="table-head px-4 py-3">User</th>
              <th className="table-head px-4 py-3">Email</th>
              <th className="table-head px-4 py-3">Role</th>
              <th className="table-head px-4 py-3">Active</th>
              <th className="table-head px-4 py-3">Last login</th>
              <th className="table-head px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users?.map((u) => (
              <tr key={u.id} className="border-b border-slate-100 hover:bg-slate-50">
                <td className="px-4 py-3">
                  <p className="font-medium">{u.full_name || u.username}</p>
                  <p className="text-[11px] text-muted font-mono">@{u.username}</p>
                </td>
                <td className="px-4 py-3 text-xs">{u.email}</td>
                <td className="px-4 py-3">
                  <select
                    className="input w-32 py-1"
                    value={u.role}
                    disabled={u.id === me?.id}
                    onChange={(e) => update(u, { role: e.target.value })}
                  >
                    <option value="admin">admin</option>
                    <option value="operator">operator</option>
                    <option value="viewer">viewer</option>
                  </select>
                </td>
                <td className="px-4 py-3"><Badge value={u.is_active ? "online" : "disabled"} /></td>
                <td className="px-4 py-3 text-xs text-muted tabular-nums">
                  {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "never"}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-1">
                    <button
                      className="btn-ghost text-xs"
                      onClick={() => {
                        const pw = prompt(`New password for ${u.username} (min 8 chars):`);
                        if (pw) update(u, { password: pw });
                      }}
                    >
                      Reset password
                    </button>
                    <button className="btn-ghost text-xs" onClick={() => update(u, { is_active: !u.is_active })}>
                      {u.is_active ? "Disable" : "Enable"}
                    </button>
                    {u.id !== me?.id && (
                      <button className="btn-ghost text-xs text-crit" onClick={() => remove(u)}>
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

      {createOpen && (
        <Modal title="Add user" onClose={() => setCreateOpen(false)}>
          <div className="space-y-3">
            <div>
              <label className="label">Username</label>
              <input className="input" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
            </div>
            <div>
              <label className="label">Full name</label>
              <input className="input" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
            </div>
            <div>
              <label className="label">Email</label>
              <input className="input" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </div>
            <div>
              <label className="label">Password (min 8 chars)</label>
              <input className="input" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            </div>
            <div>
              <label className="label">Role</label>
              <select className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                <option value="viewer">Viewer — view feeds & events</option>
                <option value="operator">Operator — monitor, search, acknowledge</option>
                <option value="admin">Administrator — full control</option>
              </select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button className="btn-ghost" onClick={() => setCreateOpen(false)}>Cancel</button>
              <button className="btn-primary" onClick={create} disabled={!form.username || !form.email || form.password.length < 8}>
                Create user
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
