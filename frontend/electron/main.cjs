const { app, BrowserWindow, shell } = require("electron");
const path = require("path");

function createWindow() {
  const win = new BrowserWindow({
    width: 1360,
    height: 860,
    minWidth: 1024,
    minHeight: 680,
    title: "Di Marcy Pedidos",
    autoHideMenuBar: true,
    webPreferences: { contextIsolation: true },
  });
  if (process.env.ELECTRON_DEV) win.loadURL("http://localhost:5173");
  else win.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  // Only https links leave the app (WhatsApp, maps); everything else is ignored.
  const openExternal = (url) => { if (url.startsWith("https://")) shell.openExternal(url); };
  win.webContents.setWindowOpenHandler(({ url }) => { openExternal(url); return { action: "deny" }; });
  win.webContents.on("will-navigate", (e, url) => {
    if (new URL(url).origin === new URL(win.webContents.getURL()).origin) return;
    e.preventDefault(); // the app window never navigates away from the app
    openExternal(url);
  });
}

app.whenReady().then(createWindow);
app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });
