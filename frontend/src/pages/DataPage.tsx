import { useState } from "react";
import { dataApi } from "../api";

export default function DataPage() {
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleExport(kind: "csv" | "json") {
    setBusy(kind);
    setError(null);
    setMessage(null);
    try {
      await dataApi.downloadExport(kind);
      setMessage(kind === "csv" ? "Transactions CSV downloaded." : "Full backup JSON downloaded.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setBusy(null);
    }
  }

  async function handleWipe() {
    setBusy("wipe");
    setError(null);
    setMessage(null);
    try {
      const result = await dataApi.wipeAll(confirm);
      setConfirm("");
      setMessage(
        `All data removed (${result.removed.transactions} transactions). Safe to show a friend — your login token is unchanged.`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Wipe failed");
    } finally {
      setBusy(null);
    }
  }

  async function handleLogout() {
    setBusy("logout");
    setError(null);
    try {
      await dataApi.logout();
      setMessage("Logged out. Restart the app or open the login link again to sign back in.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Logout failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="stack">
      <header className="page-head">
        <div>
          <h1>Your data</h1>
          <p className="lede">Export a backup, wipe everything before showing a friend, or log out of this browser.</p>
        </div>
      </header>

      {message && <p className="banner ok">{message}</p>}
      {error && <p className="banner err">{error}</p>}

      <section className="panel">
        <h2>Export</h2>
        <p className="muted">Download your data before wiping or for your own records.</p>
        <div className="btn-row">
          <button type="button" disabled={busy !== null} onClick={() => handleExport("csv")}>
            {busy === "csv" ? "Exporting…" : "Download transactions (CSV)"}
          </button>
          <button type="button" className="secondary" disabled={busy !== null} onClick={() => handleExport("json")}>
            {busy === "json" ? "Exporting…" : "Download full backup (JSON)"}
          </button>
        </div>
      </section>

      <section className="panel danger-panel">
        <h2>Wipe all data</h2>
        <p className="muted">
          Removes every transaction, import, rule, recurring group, and life item. Your login token stays — use this
          before demoing SirDoge to someone else.
        </p>
        <label className="field">
          Type <strong>DELETE</strong> to confirm
          <input
            type="text"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder="DELETE"
            autoComplete="off"
          />
        </label>
        <button
          type="button"
          className="danger"
          disabled={busy !== null || confirm !== "DELETE"}
          onClick={handleWipe}
        >
          {busy === "wipe" ? "Wiping…" : "Delete all my data"}
        </button>
      </section>

      <section className="panel">
        <h2>Session</h2>
        <p className="muted">Clears the login cookie in this browser. Does not delete any data.</p>
        <button type="button" className="secondary" disabled={busy !== null} onClick={handleLogout}>
          {busy === "logout" ? "Logging out…" : "Log out"}
        </button>
      </section>
    </div>
  );
}
