import { useCallback, useEffect, useState } from "react";
import { Activity, Bot, CheckCircle2, Cpu, Radar, ScanLine } from "lucide-react";
import { api, errMessage, mediaUrl } from "../api/client";
import type { AiModulesStatus, Camera, PlateRead, WorkerStatus } from "../api/types";
import { Badge, DemoBadge, EmptyState, ErrorState, Loading, ShieldNote } from "../components/ui";
import { useAuth } from "../context/AuthContext";

export default function Analytics() {
  const { user } = useAuth();
  const canEdit = user?.role === "admin" || user?.role === "operator";
  const [worker, setWorker] = useState<WorkerStatus | null>(null);
  const [review, setReview] = useState<PlateRead[]>([]);
  const [cams, setCams] = useState<Camera[]>([]);
  const [modules, setModules] = useState<AiModulesStatus | null>(null);
  const [error, setError] = useState("");
  const [corrections, setCorrections] = useState<Record<number, string>>({});

  const load = useCallback(async () => {
    try {
      const [w, rv, cs, md] = await Promise.all([
        api.get<WorkerStatus>("/streams/worker/status"),
        api.get<PlateRead[]>("/plate-reads", { params: { needs_review: true, limit: 50 } }),
        api.get<Camera[]>("/cameras"),
        api.get<AiModulesStatus>("/ai-modules/status"),
      ]);
      setWorker(w.data);
      setReview(rv.data);
      setCams(cs.data);
      setModules(md.data);
      setError("");
    } catch (e) {
      setError(errMessage(e));
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  const toggleDetection = async (cam: Camera) => {
    try {
      await api.patch(`/cameras/${cam.id}`, { detection_enabled: !cam.detection_enabled });
      load();
    } catch (e) {
      alert(errMessage(e));
    }
  };

  const submitCorrection = async (pr: PlateRead) => {
    const value = corrections[pr.id];
    if (!value) return;
    try {
      await api.post(`/plate-reads/${pr.id}/correct`, { corrected_text: value });
      setCorrections((c) => {
        const next = { ...c };
        delete next[pr.id];
        return next;
      });
      load();
    } catch (e) {
      alert(errMessage(e));
    }
  };

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!worker) return <Loading label="Loading analytics status…" />;

  return (
    <div className="space-y-4">
      {/* AI pipeline status */}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <div className="card p-4">
          <p className="card-title mb-2 flex items-center gap-2"><Cpu className="h-4 w-4 text-accent-bright" /> Ingestion worker</p>
          <p className="text-2xl font-bold">{worker.running ? "RUNNING" : "NOT RUNNING"}</p>
          <p className="mt-1 text-xs text-muted">
            {Object.values(worker.cameras).filter((s) => s === "online").length} source(s) live ·{" "}
            {Object.keys(worker.cameras).length} managed
          </p>
        </div>
        <div className="card p-4">
          <p className="card-title mb-2 flex items-center gap-2"><Radar className="h-4 w-4 text-accent-bright" /> Vehicle detection (YOLO)</p>
          <p className={`text-2xl font-bold ${worker.detector_ready ? "text-ok" : "text-warn"}`}>
            {worker.detector_ready ? "READY" : "DEGRADED"}
          </p>
          <p className="mt-1 text-xs text-muted">
            {worker.detector_ready ? `Device: ${worker.detector_device}` : "ultralytics/torch not installed — install backend/requirements-ai.txt to enable"}
          </p>
        </div>
        <div className="card p-4">
          <p className="card-title mb-2 flex items-center gap-2"><ScanLine className="h-4 w-4 text-accent-bright" /> ANPR (PaddleOCR)</p>
          <p className={`text-2xl font-bold ${worker.ocr_ready ? "text-ok" : "text-warn"}`}>
            {worker.ocr_ready ? "READY" : "DEGRADED"}
          </p>
          <p className="mt-1 text-xs text-muted">
            {worker.ocr_ready ? "Plate OCR pipeline active" : "paddleocr not installed — plate reads disabled"}
          </p>
        </div>
      </div>

      <ShieldNote>
        <span className="flex items-center gap-1.5 font-semibold"><Bot className="h-3.5 w-3.5" /> AI disclaimer — </span>
        Detections are probabilistic model outputs. ANPR results below the confidence threshold are flagged for human
        review and must not be treated as verified identifications. Person detection records anonymous presence only —
        no face recognition or identity inference is performed.
      </ShieldNote>

      {/* Optional AI modules status (new, additive) */}
      {modules && (
        <div className="card p-4">
          <p className="card-title mb-2 flex items-center gap-2">
            <Activity className="h-4 w-4 text-accent-bright" /> Extended AI modules (optional)
          </p>
          <div className="grid grid-cols-1 gap-2 text-xs md:grid-cols-5">
            {[
              { key: "attributes", label: "Attributes", m: modules.attributes, note: modules.attributes.mode ?? "" },
              { key: "reid", label: "Vehicle Re-ID", m: modules.reid, note: "unconfirmed matches" },
              { key: "person", label: "Person model", m: modules.person, note: modules.person.device ?? "" },
              { key: "quality", label: "Frame quality", m: modules.quality, note: `1/${modules.quality.sample_every_n ?? "-"} frames` },
              { key: "anomaly", label: "Anomaly review", m: modules.anomaly, note: "human review only" },
            ].map(({ key, label, m, note }) => (
              <div key={key} className="rounded-md border border-slate-200 bg-slate-50 p-2.5">
                <p className="font-semibold">{label}</p>
                <p className={`mt-0.5 font-bold ${!m.enabled ? "text-muted" : m.available ? "text-ok" : "text-warn"}`}>
                  {!m.enabled ? "OFF" : m.available ? "ACTIVE" : "DEGRADED"}
                </p>
                <p className="mt-0.5 text-[11px] text-muted">{note || (m.enabled ? "" : "disabled in settings")}</p>
              </div>
            ))}
          </div>
          <p className="mt-2 text-[11px] text-muted">
            Modules are independent — any of them can be disabled or fail without affecting vehicle detection, ANPR or
            the live pipeline. Appearance-based Re-ID matches are always labeled unconfirmed.
          </p>
        </div>
      )}

      {/* ANPR review queue */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">ANPR review queue ({review.length})</span>
        </div>
        {review.length === 0 ? (
          <EmptyState title="No plate reads awaiting review" hint="Low-confidence OCR results appear here for manual correction." />
        ) : (
          <div className="divide-y divide-slate-100">
            {review.map((pr) => (
              <div key={pr.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                {pr.crop_path ? (
                  <img src={mediaUrl(pr.crop_path) ?? ""} alt="plate" className="h-10 rounded border border-slate-600" />
                ) : (
                  <div className="flex h-10 w-20 items-center justify-center rounded bg-slate-50 text-[10px] text-muted">no crop</div>
                )}
                <div className="min-w-0">
                  <p className="font-mono text-sm font-bold">{pr.plate_text || "(empty)"}</p>
                  <p className="text-[11px] text-muted tabular-nums">
                    conf {(pr.ocr_confidence * 100).toFixed(0)}% · {new Date(pr.created_at).toLocaleString()}
                  </p>
                </div>
                <DemoBadge isDemo={pr.is_demo} />
                {canEdit && (
                  <div className="ml-auto flex items-center gap-2">
                    <input
                      className="input w-40 font-mono text-xs"
                      placeholder="Corrected plate"
                      value={corrections[pr.id] ?? ""}
                      onChange={(e) => setCorrections((c) => ({ ...c, [pr.id]: e.target.value.toUpperCase() }))}
                    />
                    <button className="btn-primary text-xs" onClick={() => submitCorrection(pr)} disabled={!corrections[pr.id]}>
                      <CheckCircle2 className="h-3.5 w-3.5" /> Submit
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Per-camera detection toggles */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Detection per camera</span>
        </div>
        <div className="divide-y divide-slate-100">
          {cams.map((cam) => (
            <div key={cam.id} className="flex items-center justify-between px-4 py-2.5">
              <div>
                <p className="text-sm flex items-center gap-2">{cam.name} <Badge value={cam.status} /></p>
                <p className="text-[11px] text-muted font-mono">{cam.code} · {cam.protocol}</p>
              </div>
              {canEdit ? (
                <label className="flex cursor-pointer items-center gap-2 text-xs">
                  <input type="checkbox" checked={cam.detection_enabled} onChange={() => toggleDetection(cam)} />
                  AI detection {cam.detection_enabled ? "on" : "off"}
                </label>
              ) : (
                <span className="text-xs text-muted">{cam.detection_enabled ? "detection on" : "detection off"}</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
