import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { ExportHost } from "./components/ExportPreview";
import { ContextMenuHost } from "./menu";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
    <ContextMenuHost />
    <ExportHost />
  </StrictMode>,
);
