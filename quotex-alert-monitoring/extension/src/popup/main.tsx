import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

// ALERT-ONLY: This popup displays monitoring status and alerts.
// No trade execution controls are present.

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
