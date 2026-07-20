import { NavLink, Route, Routes } from "react-router-dom";
import HeroBanner from "./components/HeroBanner";
import PrivacyBanner from "./components/PrivacyBanner";
import DashboardPage from "./pages/DashboardPage";
import ImportPage from "./pages/ImportPage";
import TransactionsPage from "./pages/TransactionsPage";
import RecurringPage from "./pages/RecurringPage";
import LifePage from "./pages/LifePage";
import DataPage from "./pages/DataPage";

export default function App() {
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
        <nav className="sidebar-nav">
          <NavLink to="/" end>
            Overview
          </NavLink>
          <NavLink to="/import">Import</NavLink>
          <NavLink to="/transactions">Transactions</NavLink>
          <NavLink to="/recurring">Recurring</NavLink>
          <NavLink to="/life">Life admin</NavLink>
          <NavLink to="/data">Your data</NavLink>
        </nav>
        <p className="sidebar-foot">All data stays on this machine.</p>
      </aside>

      <div className="main-col">
        <HeroBanner />
        <div className="app">
          <PrivacyBanner />
          <main>
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/import" element={<ImportPage />} />
              <Route path="/transactions" element={<TransactionsPage />} />
              <Route path="/recurring" element={<RecurringPage />} />
              <Route path="/life" element={<LifePage />} />
              <Route path="/data" element={<DataPage />} />
            </Routes>
          </main>
        </div>
      </div>
    </div>
  );
}
