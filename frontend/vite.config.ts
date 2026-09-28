import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Same-origin proxy for the backend API: avoids CORS/ORB issues with
// authenticated MJPEG <img> streams and matches the production nginx layout.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api/v1/ws/dashboard": {
        target: "ws://localhost:8000",
        ws: true,
        changeOrigin: true,
      },
      "/api/v1/ws/live": {
        target: "ws://localhost:8000",
        ws: true,
        changeOrigin: true,
      },
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
