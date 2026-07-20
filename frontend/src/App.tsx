import { NavLink, Route, Routes } from "react-router-dom";
import PrivacyBanner from "./components/PrivacyBanner";
import DashboardPage from "./pages/DashboardPage";
import ImportPage from "./pages/ImportPage";
import TransactionsPage from "./pages/TransactionsPage";
import RecurringPage from "./pages/RecurringPage";
import LifePage from "./pages/LifePage";

export default function App() {
  return (
    <div className="app">
      <PrivacyBanner />
      <header className="top">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            🐕
          </span>
          <div>
            <strong>SirDoge Ledger</strong>
            <p className="muted">Local finance & life admin — fancy Doge, no cloud</p>
          </div>
        </div>
        <nav>
          <NavLink to="/" end>
            Overview
          </NavLink>
          <NavLink to="/import">Import</NavLink>
          <NavLink to="/transactions">Transactions</NavLink>
          <NavLink to="/recurring">Recurring</NavLink>
          <NavLink to="/life">Life</NavLink>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/import" element={<ImportPage />} />
          <Route path="/transactions" element={<TransactionsPage />} />
          <Route path="/recurring" element={<RecurringPage />} />
          <Route path="/life" element={<LifePage />} />
        </Routes>
      </main>
    </div>
  );
}
