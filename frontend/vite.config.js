import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base "/": the site is served from the domain root (also /download), the desktop app opens the
// site itself, and Capacitor serves the bundle from https://localhost/ — absolute paths work everywhere.
// server.host exposes the dev server on the LAN so a phone (Capacitor live-reload) can reach it
export default defineConfig({ plugins: [react()], base: "/", server: { host: true, port: 5173 } });
