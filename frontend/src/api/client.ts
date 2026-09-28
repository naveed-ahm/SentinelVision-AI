import axios from "axios";

// Default: same-origin (vite dev proxy / nginx in production).
// Set VITE_API_URL for a separately deployed backend.
export const API_BASE = import.meta.env.VITE_API_URL ?? "/api/v1";

// Heavy long-lived media (MJPEG streams) and WebSockets bypass the vite proxy
// in dev and hit the backend origin directly. Browsers allow only ~6 concurrent
// HTTP/1.1 connections per origin; long-lived streams on the same origin as
// XHR would starve every API call (pages stuck on "Loading"). nginx in
// production multiplexes over HTTP/2, so same-origin is fine there.
// NOTE: short-lived thumbnails (mediaUrl) stay same-origin — cross-origin
// <img> responses get blocked by Chromium's ORB when they don't sniff as
// images, and brief requests don't threaten the connection budget.
const DEV = import.meta.env.DEV;
const STREAM_ORIGIN = import.meta.env.VITE_BACKEND_ORIGIN ?? (DEV ? "http://127.0.0.1:8000" : "");
export const WS_BASE: string =
  import.meta.env.VITE_WS_URL ??
  (DEV ? "ws://127.0.0.1:8000" : `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}`);

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
  timeout: 15000, // fail fast when the backend is down instead of hanging pages on "Loading"
});

/** Fired whenever the backend rejects our credentials (401 or WS close 4401).
 *  AuthContext listens for this to clear the in-memory user; the router then
 *  redirects to login. Prevents the "eternal Loading" state after e.g. a
 *  server-side SECRET_KEY rotation. */
export const AUTH_REJECTED_EVENT = "sv:unauthorized";
export function notifyAuthRejected() {
  window.dispatchEvent(new CustomEvent(AUTH_REJECTED_EVENT));
}

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let authRejectNotified = false;
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && !err.config?.url?.includes("/auth/login")) {
      setToken(null);
      if (!authRejectNotified) {
        authRejectNotified = true;
        notifyAuthRejected();
        window.setTimeout(() => (authRejectNotified = false), 1000);
      }
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
  return `${STREAM_ORIGIN}${API_BASE}/streams/${cameraId}/${mode}${qs}`;
}

export function errMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    return err.response?.data?.detail ?? err.message;
  }
  return String(err);
}
