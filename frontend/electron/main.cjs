const { app, BrowserWindow, dialog, shell } = require("electron");

// The desktop app is a window onto the web app: always the deployed version, no reinstall
// per release, and same-origin API calls (no CORS). Dev mode points at the local Vite server.
const APP_URL = process.env.ELECTRON_DEV ? "http://localhost:5173" : (process.env.DIMARCY_URL || "https://app.dimarcy.com.br");
const APP_ORIGIN = new URL(APP_URL).origin;

const OFFLINE_PAGE = `data:text/html;charset=utf-8,${encodeURIComponent(`<!doctype html>
<html lang="pt-BR"><meta charset="utf-8"><title>Di Marcy Pedidos</title>
<body style="font-family:system-ui,sans-serif;display:grid;place-items:center;height:100vh;margin:0;background:#eef2f9;color:#16233d">
<div style="text-align:center"><h2>Sem conexão com o servidor</h2>
<p>Verifique a internet e tente de novo.</p>
<a href="${APP_URL}" style="display:inline-block;margin-top:8px;padding:10px 18px;border-radius:8px;background:#2f6fed;color:#fff;text-decoration:none">Tentar novamente</a>
</div></body></html>`)}`;

// Only https links leave the app (WhatsApp, maps); everything else is ignored.
const openExternal = (url) => { if (url.startsWith("https://")) shell.openExternal(url); };

function createWindow() {
  const win = new BrowserWindow({
    width: 1360,
    height: 860,
    minWidth: 1024,
    minHeight: 680,
    title: "Di Marcy Pedidos",
    autoHideMenuBar: true,
    webPreferences: { contextIsolation: true, sandbox: true, nodeIntegration: false },
  });
  win.loadURL(APP_URL);
  win.webContents.on("did-fail-load", (_e, code, _desc, url, isMainFrame) => {
    if (isMainFrame && code !== -3 && url.startsWith(APP_ORIGIN)) win.loadURL(OFFLINE_PAGE); // -3 = aborted
  });
  // The order screen blocks unloading while an order is unsaved (beforeunload). Electron would then
  // silently refuse to close — ask instead, like the in-app dialog does.
  win.webContents.on("will-prevent-unload", (e) => {
    const choice = dialog.showMessageBoxSync(win, {
      type: "warning",
      title: "Pedido não salvo",
      message: "Sair sem salvar o pedido?",
      detail: "Os produtos e dados preenchidos neste pedido serão perdidos.",
      buttons: ["Continuar no pedido", "Sair sem salvar"],
      defaultId: 0,
      cancelId: 0,
      noLink: true,
    });
    if (choice === 1) e.preventDefault(); // preventDefault here = ignore the page's block and close
  });
  win.webContents.setWindowOpenHandler(({ url }) => { openExternal(url); return { action: "deny" }; });
  win.webContents.on("will-navigate", (e, url) => {
    if (new URL(url).origin === APP_ORIGIN) return; // inside the app (also "Tentar novamente")
    e.preventDefault(); // the app window never navigates to other sites
    openExternal(url);
  });
}

app.whenReady().then(createWindow);
app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });
