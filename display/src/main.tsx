import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "./styles.css";

if (import.meta.env.VITE_OLYMPUS_KIOSK === "true") {
  document.documentElement.classList.add("olympus-kiosk");
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
