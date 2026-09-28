import { useState } from "react";
import { Download, FileText } from "lucide-react";
import { api, errMessage, getToken, API_BASE } from "../api/client";
void api;
import { Loading, ShieldNote } from "../components/ui";

export default function Reports() {
  const [start, setStart] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 1);
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  });
  const [end, setEnd] = useState(() => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16));
  const [title, setTitle] = useState("Operations report");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const download = async () => {
    setError("");
    if (!start || !end || new Date(end) <= new Date(start)) {
      setError("End must be after start.");
      return;
    }
    setBusy(true);
    try {
      const params = new URLSearchParams({
        start: new Date(start).toISOString(),
        end: new Date(end).toISOString(),
        title,
      });
      // fetch as blob so the browser downloads with auth header
      const res = await fetch(`${API_BASE}/reports/csv?${params}`, {
        headers: { Authorization: `Bearer ${getToken() ?? ""}` },
      });
      if (!res.ok) throw new Error(`Report failed (${res.status})`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `sentinelvision_report_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(errMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="card max-w-2xl p-6">
        <p className="card-title mb-4 flex items-center gap-2">
          <FileText className="h-4 w-4 text-accent-bright" /> Generate CSV report
        </p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className="label">From (local time)</label>
            <input type="datetime-local" className="input" value={start} onChange={(e) => setStart(e.target.value)} />
          </div>
          <div>
            <label className="label">To (local time)</label>
            <input type="datetime-local" className="input" value={end} onChange={(e) => setEnd(e.target.value)} />
          </div>
          <div className="sm:col-span-2">
            <label className="label">Report title</label>
            <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
        </div>
        {error && <p className="mt-3 text-sm text-crit">{error}</p>}
        <button className="btn-primary mt-4" onClick={download} disabled={busy}>
          {busy ? <Loading label="" /> : <><Download className="h-4 w-4" /> Download CSV</>}
        </button>
        <div className="mt-4">
          <ShieldNote>
            Reports contain only events actually recorded in the database for the selected period — detection and alert
            summaries, camera status and the top vehicles by confirmed sightings. Nothing is synthesized. Requires
            operator or admin role.
          </ShieldNote>
        </div>
      </div>
    </div>
  );
}
