import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Backend dev server runs on :8000. Vite proxies /api and /healthz
// so the frontend can use same-origin URLs in dev — no CORS dance.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/healthz": "http://localhost:8000",
    },
  },
});
