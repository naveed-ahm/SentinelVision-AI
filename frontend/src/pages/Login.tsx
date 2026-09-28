import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Radio } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { errMessage } from "../api/client";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(username, password);
      navigate("/");
    } catch (err) {
      setError(errMessage(err) || "Login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-full items-center justify-center p-4">
      <div className="card w-full max-w-sm p-8">
        <div className="mb-6 flex flex-col items-center gap-2">
          <div className="rounded-xl bg-accent/15 p-3">
            <Radio className="h-8 w-8 text-accent-bright" />
          </div>
          <h1 className="text-lg font-bold">SentinelVision AI</h1>
          <p className="text-xs text-muted text-center">Integrated CCTV Management & Video Analytics</p>
        </div>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="label" htmlFor="username">Username</label>
            <input id="username" className="input" value={username} autoComplete="username"
              onChange={(e) => setUsername(e.target.value)} autoFocus required />
          </div>
          <div>
            <label className="label" htmlFor="password">Password</label>
            <input id="password" type="password" className="input" value={password} autoComplete="current-password"
              onChange={(e) => setPassword(e.target.value)} required />
          </div>
          {error && <p className="text-sm text-crit">{error}</p>}
          <button className="btn-primary w-full justify-center" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <div className="mt-6 rounded-md border border-slate-200 bg-slate-50 p-3 text-[11px] leading-relaxed text-muted">
          <p className="font-semibold text-body">Demonstration accounts</p>
          <p>admin / Admin@12345 — full control</p>
          <p>operator / Operator@12345 — monitoring</p>
          <p>viewer / Viewer@12345 — read-only</p>
        </div>
      </div>
    </div>
  );
}
