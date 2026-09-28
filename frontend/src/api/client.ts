import axios from "axios";

// Default: same-origin (vite dev proxy / nginx in production).
// Set VITE_API_URL for a separately deployed backend.
export const API_BASE = import.meta.env.VITE_API_URL ?? "/api/v1";
export const WS_BASE: string =
  import.meta.env.VITE_WS_URL ??
  `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}`;

export const TOKEN_KEY = "sentinelvision.token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && !err.config?.url?.includes("/auth/login")) {
      setToken(null);
      if (!window.location.hash.includes("/login")) window.location.hash = "#/login";
    }
    return Promise.reject(err);
  }
);

export function mediaUrl(relPath: string | null | undefined): string | null {
  if (!relPath) return null;
  const token = getToken();
  const qs = token ? `?access_token=${encodeURIComponent(token)}` : "";
  return `${API_BASE}/media-api/${relPath}${qs}`;
}

export function streamUrl(cameraId: number, mode: "mjpeg" | "snapshot"): string {
  const token = getToken();
  const qs = token ? `?access_token=${encodeURIComponent(token)}` : "";
  return `${API_BASE}/streams/${cameraId}/${mode}${qs}`;
}

export function errMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    return err.response?.data?.detail ?? err.message;
  }
  return String(err);
}
