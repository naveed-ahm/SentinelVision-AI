import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { getToken, notifyAuthRejected, WS_BASE } from "../api/client";

export interface LiveAlert {
  id: number;
  alert_type: string;
  severity: string;
  camera_id: number | null;
  title: string;
  description: string;
  created_at: string | null;
  is_demo: boolean;
}

export interface LiveDetection {
  camera_id: number;
  camera_name: string;
  object_class: string;
  confidence: number;
  plate_text: string | null;
  timestamp: string;
  is_demo: boolean;
}

interface LiveState {
  connected: boolean;
  lastAlert: LiveAlert | null;
  lastDetection: LiveDetection | null;
  cameraStatus: Record<number, string>;
  refreshKey: number;
}

const LiveContext = createContext<LiveState>({
  connected: false,
  lastAlert: null,
  lastDetection: null,
  cameraStatus: {},
  refreshKey: 0,
});

export function LiveProvider({ children }: { children: React.ReactNode }) {
  const [connected, setConnected] = useState(false);
  const [lastAlert, setLastAlert] = useState<LiveAlert | null>(null);
  const [lastDetection, setLastDetection] = useState<LiveDetection | null>(null);
  const [cameraStatus, setCameraStatus] = useState<Record<number, string>>({});
  const [refreshKey, setRefreshKey] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);

  const connect = useCallback(() => {
    const token = getToken();
    if (!token) return; // logged out — don't reconnect
    const ws = new WebSocket(`${WS_BASE}/api/v1/ws/dashboard`);
    wsRef.current = ws;
    ws.onopen = () => {
      retryRef.current = 0;
      ws.send(token);
      setConnected(true);
    };
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === "alert") {
          setLastAlert(msg.alert);
          setRefreshKey((k) => k + 1);
        } else if (msg.type === "detection") {
          setLastDetection(msg.detection);
        } else if (msg.type === "camera_status") {
          setCameraStatus((prev) => ({ ...prev, [msg.camera_id]: msg.status }));
          setRefreshKey((k) => k + 1);
        }
      } catch {
        /* ignore malformed frames */
      }
    };
    ws.onclose = (ev) => {
      setConnected(false);
      // 4401 = backend rejected our token (e.g. SECRET_KEY rotated). Notify auth
      // listeners and stop reconnecting — retrying can never succeed until the
      // user logs in again, and the retry loop would spam the backend.
      if (ev.code === 4401) {
        notifyAuthRejected();
        return;
      }
      // Persistent reconnect with capped backoff (2s..15s). The badge keeps the
      // user informed; giving up would leave a silent dashboard.
      retryRef.current += 1;
      const delay = Math.min(2000 * retryRef.current, 15000);
      setTimeout(() => {
        if (getToken()) connect();
      }, delay);
    };
    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    connect();
    return () => wsRef.current?.close();
  }, [connect]);

  const value = useMemo(
    () => ({ connected, lastAlert, lastDetection, cameraStatus, refreshKey }),
    [connected, lastAlert, lastDetection, cameraStatus, refreshKey]
  );
  return <LiveContext.Provider value={value}>{children}</LiveContext.Provider>;
}

export function useLive() {
  return useContext(LiveContext);
}
