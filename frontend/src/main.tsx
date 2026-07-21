import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./auth";
import { CategoriesProvider } from "./categories";
import { I18nProvider } from "./i18n";
import App from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <CategoriesProvider>
          <I18nProvider>
            <App />
          </I18nProvider>
        </CategoriesProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
