import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

// Each deploy gives the bundle a new hashed name (/assets/index-AbC123.js). The open page compares its own
// with the one the server's index.html points to now; a difference means a new version is published.
// The desktop app is a window onto the site, so this is how it learns to reload without reopening.
const CHECK_EVERY_MS = 10 * 60 * 1000;
const SNOOZE_MS = 60 * 60 * 1000; // "Depois" hides it for an hour
const bundleIn = (html) => html.match(/<script[^>]+type="module"[^>]+src="([^"]+)"/)?.[1];
const currentBundle = () => new URL(document.querySelector('script[type="module"][src]')?.src || "", location.href).pathname;

// Never in the middle of something: the order form, or any open form/dialog (they all use .modal-backdrop)
const busy = (pathname) => /^\/orders\/(new|\d+\/edit)$/.test(pathname) || !!document.querySelector(".modal-backdrop");

export default function UpdateBanner() {
  const { pathname } = useLocation();
  const [outdated, setOutdated] = useState(false);
  const [snoozedUntil, setSnoozedUntil] = useState(0);
  const [, recheck] = useState(0); // re-render when a dialog closes, so a waiting banner can show up

  useEffect(() => {
    if (import.meta.env.DEV) return; // Vite's dev server reloads by itself
    const mine = currentBundle();
    async function check() {
      try {
        const html = await (await fetch(`/?v=${Date.now()}`, { cache: "no-store" })).text();
        const live = bundleIn(html);
        if (live && new URL(live, location.href).pathname !== mine) setOutdated(true);
      } catch { /* offline: try again on the next tick */ }
    }
    const timer = setInterval(check, CHECK_EVERY_MS);
    const onFocus = () => { check(); recheck((n) => n + 1); };
    window.addEventListener("focus", onFocus);
    return () => { clearInterval(timer); window.removeEventListener("focus", onFocus); };
  }, []);

  // while waiting to be shown, look again every few seconds for the open dialog to close
  useEffect(() => {
    if (!outdated) return;
    const t = setInterval(() => recheck((n) => n + 1), 3000);
    return () => clearInterval(t);
  }, [outdated]);

  if (!outdated || Date.now() < snoozedUntil || busy(pathname)) return null;
  return (
    <div className="update-banner" role="status">
      <span>Há uma nova versão do app disponível.</span>
      <button type="button" className="btn btn-light" onClick={() => setSnoozedUntil(Date.now() + SNOOZE_MS)}>Depois</button>
      <button type="button" className="btn btn-primary" onClick={() => location.reload()}>Atualizar</button>
    </div>
  );
}
