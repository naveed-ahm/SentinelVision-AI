import { useState } from "react";
import type { Camera, CameraInput } from "../api/types";
import { Modal, ShieldNote } from "./ui";

interface Props {
  camera?: Camera | null;
  onClose: () => void;
  onSubmit: (payload: CameraInput) => Promise<void>;
}

export function CameraFormModal({ camera, onClose, onSubmit }: Props) {
  const [form, setForm] = useState({
    name: camera?.name ?? "",
    code: camera?.code ?? "",
    location_name: camera?.location_name ?? "",
    latitude: camera?.latitude?.toString() ?? "",
    longitude: camera?.longitude?.toString() ?? "",
    manufacturer: camera?.manufacturer ?? "",
    model: camera?.model ?? "",
    protocol: camera?.protocol ?? "rtsp",
    rtsp_url: camera?.rtsp_url ?? "",
    description: camera?.description ?? "",
    enabled: camera?.enabled ?? true,
    detection_enabled: camera?.detection_enabled ?? true,
    cred_username: "",
    cred_secret: "",
    cred_channel: "",
  });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const set = (k: string, v: string | boolean) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    setError("");
    if (!form.name.trim() || !form.code.trim()) {
      setError("Name and camera code are required.");
      return;
    }
    const payload: CameraInput = {
      name: form.name.trim(),
      code: form.code.trim().toUpperCase(),
      location_name: form.location_name,
      latitude: form.latitude === "" ? null : Number(form.latitude),
      longitude: form.longitude === "" ? null : Number(form.longitude),
      manufacturer: form.manufacturer,
      model: form.model,
      protocol: form.protocol as CameraInput["protocol"],
      rtsp_url: form.rtsp_url.trim(),
      description: form.description,
      enabled: form.enabled,
      detection_enabled: form.detection_enabled,
    };
    if (camera) payload.code = camera.code; // code immutable on edit
    if (form.cred_username || form.cred_secret) {
      payload.credential = {
        username: form.cred_username,
        secret: form.cred_secret,
        channel: form.cred_channel,
      };
    }
    setSaving(true);
    try {
      await onSubmit(payload);
      onClose();
    } catch (e) {
      setError(String((e as Error).message || "Save failed"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal title={camera ? `Edit camera — ${camera.code}` : "Register camera"} onClose={onClose} wide>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className="label">Camera name *</label>
          <input className="input" value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="SG Highway — Overpass" />
        </div>
        <div>
          <label className="label">Camera code *</label>
          <input className="input" value={form.code} onChange={(e) => set("code", e.target.value)} placeholder="AHM-SG-001" disabled={!!camera} />
        </div>
        <div className="sm:col-span-2">
          <label className="label">Location</label>
          <input className="input" value={form.location_name} onChange={(e) => set("location_name", e.target.value)} placeholder="SG Highway, Ahmedabad" />
        </div>
        <div>
          <label className="label">Latitude</label>
          <input className="input" value={form.latitude} onChange={(e) => set("latitude", e.target.value)} placeholder="23.0225" />
        </div>
        <div>
          <label className="label">Longitude</label>
          <input className="input" value={form.longitude} onChange={(e) => set("longitude", e.target.value)} placeholder="72.5714" />
        </div>
        <div>
          <label className="label">Manufacturer</label>
          <input className="input" value={form.manufacturer} onChange={(e) => set("manufacturer", e.target.value)} />
        </div>
        <div>
          <label className="label">Model</label>
          <input className="input" value={form.model} onChange={(e) => set("model", e.target.value)} />
        </div>
        <div>
          <label className="label">Stream protocol</label>
          <select className="input" value={form.protocol} onChange={(e) => set("protocol", e.target.value)}>
            <option value="rtsp">RTSP</option>
            <option value="file">Prerecorded file (demo)</option>
            <option value="webcam">Local webcam</option>
          </select>
        </div>
        <div>
          <label className="label">Status flags</label>
          <div className="flex gap-4 pt-2 text-sm">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={form.enabled} onChange={(e) => set("enabled", e.target.checked)} />
              Enabled
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={form.detection_enabled} onChange={(e) => set("detection_enabled", e.target.checked)} />
              AI detection
            </label>
          </div>
        </div>
        <div className="sm:col-span-2">
          <label className="label">RTSP / file URL</label>
          <input
            className="input font-mono text-xs"
            value={form.rtsp_url}
            onChange={(e) => set("rtsp_url", e.target.value)}
            placeholder="rtsp://192.168.1.10:554/stream1  or  C:/videos/traffic.mp4"
          />
        </div>
        <div className="sm:col-span-2">
          <label className="label">Description</label>
          <textarea className="input" rows={2} value={form.description} onChange={(e) => set("description", e.target.value)} />
        </div>

        <div className="sm:col-span-2">
          <p className="label">Stream credentials (stored separately, never returned by the API)</p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <input className="input" value={form.cred_username} onChange={(e) => set("cred_username", e.target.value)} placeholder="Username" autoComplete="off" />
            <input className="input font-mono" type="password" value={form.cred_secret} onChange={(e) => set("cred_secret", e.target.value)} placeholder="Password" autoComplete="new-password" />
            <input className="input" value={form.cred_channel} onChange={(e) => set("cred_channel", e.target.value)} placeholder="Channel (optional)" />
          </div>
          <div className="mt-2">
            <ShieldNote>
              Credentials are kept in a dedicated table and combined with the RTSP URL only inside the ingestion
              worker. The API always returns a redacted URL (<code>rtsp://***:***@host</code>).
            </ShieldNote>
          </div>
        </div>
      </div>

      {error && <p className="mt-3 text-sm text-crit">{error}</p>}

      <div className="mt-4 flex justify-end gap-2">
        <button className="btn-ghost" onClick={onClose} disabled={saving}>
          Cancel
        </button>
        <button className="btn-primary" onClick={submit} disabled={saving}>
          {saving ? "Saving…" : camera ? "Save changes" : "Register camera"}
        </button>
      </div>
    </Modal>
  );
}
