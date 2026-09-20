import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base "./" so it works inside Electron (file://)
// server.host exposes the dev server on the LAN so a phone (Capacitor live-reload) can reach it
export default defineConfig({ plugins: [react()], base: "./", server: { host: true, port: 5173 } });
