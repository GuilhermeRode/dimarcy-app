import { resolve } from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base "/": the site is served from the domain root, the desktop app opens the site itself, and
// Capacitor serves the bundle from https://localhost/ — absolute paths work everywhere.
// Two pages: the app (index.html) and the unlisted installer page (download/index.html), which the
// server's plain file_server delivers at /download/ with no extra configuration.
// server.host exposes the dev server on the LAN so a phone (Capacitor live-reload) can reach it
export default defineConfig({
  plugins: [react()],
  base: "/",
  build: {
    rollupOptions: {
      input: { main: resolve(__dirname, "index.html"), download: resolve(__dirname, "download/index.html") },
    },
  },
  server: { host: true, port: 5173 },
});
