import type { CapacitorConfig } from '@capacitor/cli';

// Dev mode: the app loads the live Vite dev server on the local network,
// so edits on the PC show up on the phone instantly (no rebuild needed).
// For a real release build, remove the "server" block and run `npx cap sync`
// so the app loads the bundled files from webDir instead.
const config: CapacitorConfig = {
  appId: 'com.dimarcy.pedidos',
  appName: 'Di Marcy Pedidos',
  webDir: 'dist',
  server: {
    url: 'http://192.168.18.165:5173',
    cleartext: true,
  },
};

export default config;
