import { NavLink, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import HeroBanner from "./components/HeroBanner";
import LanguageToggle from "./components/LanguageToggle";
import LoginGate from "./components/LoginGate";
import PrivacyBanner from "./components/PrivacyBanner";
import { useI18n } from "./i18n";
import DashboardPage from "./pages/DashboardPage";
import ImportPage from "./pages/ImportPage";
import TransactionsPage from "./pages/TransactionsPage";
import RecurringPage from "./pages/RecurringPage";
import LifePage from "./pages/LifePage";
import DataPage from "./pages/DataPage";
import SettingsPage from "./pages/SettingsPage";
import RulesPage from "./pages/RulesPage";

export default function App() {
  const { status, mode } = useAuth();
  const { t } = useI18n();
  const authed = status === "authenticated";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <img src="/sir-doge-hero.png" alt="" className="sidebar-avatar" />
          <div>
            <strong>SirDoge</strong>
            <span>Ledger</span>
          </div>
        </div>
        <LanguageToggle />
        <nav className="sidebar-nav">
          <NavLink to="/" end>
            {t.nav.overview}
          </NavLink>
          <NavLink to="/import">{t.nav.import}</NavLink>
          <NavLink to="/transactions">{t.nav.transactions}</NavLink>
          <NavLink to="/recurring">{t.nav.recurring}</NavLink>
          <NavLink to="/life">{t.nav.life}</NavLink>
          <NavLink to="/rules">{t.nav.rules}</NavLink>
          <NavLink to="/settings">{t.nav.settings}</NavLink>
          <NavLink to="/data">{t.nav.data}</NavLink>
        </nav>
        <p className="sidebar-foot">
          {mode === "demo" ? `${t.common.demo} · ` : ""}
          {t.sidebarFoot}
        </p>
      </aside>

      <div className="main-col">
        <HeroBanner />
        <div className="app">
          {mode === "demo" && (
            <div className="privacy-banner demo-banner">{t.demoBanner}</div>
          )}
          <PrivacyBanner />
          <main>
            {status === "loading" && <p className="muted page-loading">{t.common.loading}</p>}
            {(status === "unauthenticated" || status === "setup") && <LoginGate />}
            {authed && (
              <Routes>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/import" element={<ImportPage />} />
                <Route path="/transactions" element={<TransactionsPage />} />
                <Route path="/recurring" element={<RecurringPage />} />
                <Route path="/life" element={<LifePage />} />
                <Route path="/rules" element={<RulesPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/data" element={<DataPage />} />
              </Routes>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
