import React from "react";
import ReactDOM from "react-dom/client";
import { HistoryPage } from "./HistoryPage";

const root = document.getElementById("root");
if (root) {
  ReactDOM.createRoot(root).render(
    <React.StrictMode>
      <HistoryPage />
    </React.StrictMode>
  );
}
