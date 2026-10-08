import React from "react";
import ReactDOM from "react-dom/client";
import Download from "./pages/Download";
import "./styles.css";

// Entry of download/index.html (served at app.dimarcy.com.br/download/ as a plain static page).
ReactDOM.createRoot(document.getElementById("root")).render(<Download />);
