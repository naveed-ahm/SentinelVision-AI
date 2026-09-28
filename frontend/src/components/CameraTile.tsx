import { useEffect, useRef, useState } from "react";
import { Camera as CameraIcon, Maximize2, Minimize2, RefreshCw, WifiOff } from "lucide-react";
import type { Camera } from "../api/types";
import { streamUrl } from "../api/client";
import { Badge, DemoBadge } from "./ui";

const MAX_AUTO_RETRIES = 3;

export function CameraTile({
  camera,
  openMonitoring,
  compact = false,
}: {
  camera: Camera;
  openMonitoring?: (id: number) => void;
  compact?: boolean;
}) {
  const [nonce, setNonce] = useState(0);
  const [zoomed, setZoomed] = useState(false);
  const [failed, setFailed] = useState(false);
  const retriesRef = useRef(0);
  const timerRef = useRef<number | null>(null);
  const isOnline = camera.status === "online";

  useEffect(() => {
    setFailed(false);
    retriesRef.current = 0;
  }, [camera.id, camera.status]);

  useEffect(() => {
    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
  }, []);

  const handleStreamError = () => {
    if (retriesRef.current >= MAX_AUTO_RETRIES) {
      setFailed(true);
      return;
    }
    retriesRef.current += 1;
    timerRef.current = window.setTimeout(() => setNonce((n) => n + 1), 3000);
  };

  const video = isOnline && !failed ? (
    <img
      key={nonce}
      src={streamUrl(camera.id, "mjpeg") + `${nonce ? `&v=${nonce}` : ""}`}
      alt={camera.name}
      className="h-full w-full object-cover"
      onError={handleStreamError}
      loading="lazy"
    />
  ) : (
    <div className="flex h-full w-full flex-col items-center justify-center gap-2 bg-slate-100 text-muted">
      <WifiOff className="h-7 w-7 opacity-70" />
      <p className="text-xs font-medium uppercase tracking-wider">{failed ? "stream unavailable" : camera.status}</p>
      {camera.last_error && <p className="text-[11px] opacity-70 max-w-[90%] truncate">{camera.last_error}</p>}
      <button
        className="btn-ghost mt-1 text-xs"
        onClick={() => {
          setFailed(false);
          retriesRef.current = 0;
          setNonce((n) => n + 1);
        }}
      >
        <RefreshCw className="h-3.5 w-3.5" /> Retry
      </button>
    </div>
  );

  return (
    <div className={`card overflow-hidden flex flex-col ${zoomed ? "fixed inset-4 z-40" : ""}`}>
      <div className={`relative bg-slate-900 ${compact ? "aspect-video" : "aspect-video"}`}>
        {video}
        <div className="absolute top-2 left-2 flex items-center gap-1.5">
          <Badge value={camera.status} className="!bg-white/90" />
          <DemoBadge isDemo={camera.is_demo} className="!bg-white/90" />
        </div>
        <button
          className="absolute top-2 right-2 rounded bg-black/50 p-1.5 text-white/80 hover:text-white"
          onClick={() => setZoomed((z) => !z)}
          title={zoomed ? "Exit full screen" : "Full screen"}
        >
          {zoomed ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
        </button>
      </div>
      <div className="p-3 flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-medium truncate flex items-center gap-1.5">
            <CameraIcon className="h-3.5 w-3.5 text-muted shrink-0" />
            {camera.name}
          </p>
          <p className="text-[11px] text-muted truncate">
            {camera.code} · {camera.location_name || "Unknown location"}
          </p>
        </div>
        {openMonitoring && (
          <button className="btn-ghost text-xs shrink-0" onClick={() => openMonitoring(camera.id)}>
            Open
          </button>
        )}
      </div>
    </div>
  );
}
