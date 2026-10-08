import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";

// A deploy replaces the hashed chunks (old ones are deleted). A page left open across a deploy —
// the desktop app especially — then fails to load a lazy screen (e.g. the customer map) with
// "Failed to fetch dynamically imported module". Reloading picks up the new build. The timestamp
// guard stops a reload loop if a chunk is missing for some other reason.
window.addEventListener("vite:preloadError", (event) => {
  const key = "chunk-reload-at";
  let last = 0;
  try { last = Number(sessionStorage.getItem(key)) || 0; } catch { /* storage blocked: reload once anyway */ }
  if (Date.now() - last < 10000) return; // just reloaded: let the error surface instead of looping
  event.preventDefault();
  try { sessionStorage.setItem(key, String(Date.now())); } catch { /* ignore */ }
  window.location.reload();
});

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
