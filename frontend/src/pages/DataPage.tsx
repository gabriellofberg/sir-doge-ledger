import { useRef, useState } from "react";
import { useAuth } from "../auth";
import { dataApi } from "../api";
import { useI18n, tr } from "../i18n";

export default function DataPage() {
  const { refresh } = useAuth();
  const { t } = useI18n();
  const fileRef = useRef<HTMLInputElement>(null);
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
      setMessage(kind === "csv" ? t.data.csvOk : t.data.jsonOk);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function handleRestore(file: File) {
    setBusy("restore");
    setError(null);
    setMessage(null);
    try {
      const result = await dataApi.restoreBackup(file);
      const count = result.restored.transactions ?? 0;
      setMessage(tr(t.data.restoreOk, { count: String(count) }));
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function handleWipe() {
    setBusy("wipe");
    setError(null);
    setMessage(null);
    try {
      const result = await dataApi.wipeAll(confirm);
      setConfirm("");
      setMessage(tr(t.data.wipeOk, { count: result.removed.transactions }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function handleLogout() {
    setBusy("logout");
    setError(null);
    try {
      await dataApi.logout();
      await refresh();
      setMessage(t.data.logoutOk);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="stack">
      <header className="page-head">
        <div>
          <h1>{t.data.title}</h1>
          <p className="lede">{t.data.lede}</p>
        </div>
      </header>

      {message && <p className="banner ok">{message}</p>}
      {error && <p className="banner err">{error}</p>}

      <section className="panel">
        <h2>{t.data.demoFlow}</h2>
        <ol className="data-flow-steps muted">
          <li>{t.data.demoStep1}</li>
          <li>{t.data.demoStep2}</li>
          <li>{t.data.demoStep3}</li>
        </ol>
      </section>

      <section className="panel">
        <h2>{t.data.export}</h2>
        <p className="muted">{t.data.exportHint}</p>
        <div className="btn-row">
          <button type="button" disabled={busy !== null} onClick={() => handleExport("csv")}>
            {busy === "csv" ? t.data.exporting : t.data.csv}
          </button>
          <button
            type="button"
            className="primary"
            disabled={busy !== null}
            onClick={() => handleExport("json")}
          >
            {busy === "json" ? t.data.exporting : t.data.json}
          </button>
        </div>
      </section>

      <section className="panel">
        <h2>{t.data.restore}</h2>
        <p className="muted">{t.data.restoreHint}</p>
        <input
          ref={fileRef}
          type="file"
          accept=".json,application/json"
          className="sr-only"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void handleRestore(file);
          }}
        />
        <button
          type="button"
          className="secondary"
          disabled={busy !== null}
          onClick={() => fileRef.current?.click()}
        >
          {busy === "restore" ? t.data.restoring : t.data.restoreBtn}
        </button>
      </section>

      <section className="panel danger-panel">
        <h2>{t.data.wipe}</h2>
        <p className="muted">{t.data.wipeHint}</p>
        <label className="field">
          {t.data.wipeConfirm}
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
          {busy === "wipe" ? t.data.wiping : t.data.wipeBtn}
        </button>
      </section>

      <section className="panel">
        <h2>{t.data.session}</h2>
        <p className="muted">{t.data.sessionHint}</p>
        <button type="button" className="secondary" disabled={busy !== null} onClick={handleLogout}>
          {busy === "logout" ? t.data.loggingOut : t.data.logout}
        </button>
      </section>
    </div>
  );
}
