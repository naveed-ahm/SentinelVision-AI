import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Same-origin proxy for the backend API: avoids CORS/ORB issues with
// authenticated MJPEG <img> streams and matches the production nginx layout.
//
// NOTE: MJPEG streams (`/api/v1/streams/...`) and WebSockets are NOT proxied.
// The browser allows only ~6 concurrent HTTP/1.1 connections per origin; six
// MJPEG tiles + a WebSocket would starve every XHR call ("Loading…" forever).
// In dev, client.ts points those directly at the backend origin (:8000) so
// they use a separate connection pool. Production sits behind nginx, which
// multiplexes over HTTP/2 and doesn't have this limit.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Only lightweight JSON API traffic is proxied.
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
