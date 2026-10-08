import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import Download from "./pages/Download";
import "./styles.css";

// app.dimarcy.com.br/download is a real path (the app itself uses #/ routes): the server falls back
// to index.html for it, and we show the unlisted desktop-download page instead of the app.
const isDownloadPage = window.location.pathname.replace(/\/+$/, "") === "/download";

ReactDOM.createRoot(document.getElementById("root")).render(isDownloadPage ? <Download /> : <App />);
