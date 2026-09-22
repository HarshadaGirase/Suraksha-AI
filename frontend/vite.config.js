import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // WS#1 is proxied in dev so the browser sees one origin and we avoid a
    // CORS/WSS split between `npm run dev` and the deployed build. In PUBLIC
    // MODE (CLAUDE.MD §6) VITE_WS_URL points straight at the Render backend.
    proxy: {
      "/ws": { target: "ws://127.0.0.1:8000", ws: true },
      "/api": { target: "http://127.0.0.1:8000" },
    },
  },
});
