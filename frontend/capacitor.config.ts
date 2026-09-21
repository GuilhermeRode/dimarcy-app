import type { CapacitorConfig } from '@capacitor/cli';

// Production mode: the app loads the screens bundled inside webDir (dist/)
// and talks to the API only over the internet (VITE_API_URL baked in at
// build time) — no dependency on the local network. For development with
// live-reload on the LAN, use capacitor.config.dev.ts (`npm run cap:sync:dev`).
const config: CapacitorConfig = {
  appId: 'com.dimarcy.pedidos',
  appName: 'Di Marcy Pedidos',
  webDir: 'dist',
};

export default config;
