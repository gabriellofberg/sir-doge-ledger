import { useState, type FormEvent } from "react";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";

type Mode = "login" | "setup" | "recover";

export default function LoginGate() {
  const { status, login, setup, demo, recover } = useAuth();
  const { t } = useI18n();
  const [mode, setMode] = useState<Mode>(status === "setup" ? "setup" : "login");
  const [password, setPassword] = useState("");
  const [recoveryKey, setRecoveryKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recoveryShown, setRecoveryShown] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    if (mode === "setup") {
      const res = await setup(password);
      if (!res) setError(t.login.wrongPassword);
      else setRecoveryShown(res.recovery_key ?? null);
    } else if (mode === "recover") {
      const ok = await recover(recoveryKey, password);
      if (!ok) setError(t.login.wrongPassword);
    } else {
      const ok = await login(password);
      if (!ok) setError(t.login.wrongPassword);
    }
    setBusy(false);
  }

  return (
    <div className="login-gate">
      <section className="login-card panel">
        <img src="/sir-doge-hero.png" alt="" className="login-avatar" />
        <h1>{mode === "setup" ? t.login.setupTitle : t.login.title}</h1>
        <p className="lede">{mode === "setup" ? t.login.setupHint : t.login.lede}</p>

        {recoveryShown && (
          <p className="banner ok">
            <strong>{t.login.recoveryShown}</strong> {recoveryShown}
          </p>
        )}

        <form onSubmit={onSubmit} className="login-form">
          {mode === "recover" && (
            <label>
              {t.login.recoveryKey}
              <input value={recoveryKey} onChange={(e) => setRecoveryKey(e.target.value)} required />
            </label>
          )}
          <label>
            {mode === "recover" ? t.login.newPassword : t.login.password}
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={mode === "setup" || mode === "recover" ? 8 : 1}
            />
          </label>
          {error && <p className="banner err">{error}</p>}
          <button type="submit" className="primary" disabled={busy}>
            {busy
              ? t.common.loading
              : mode === "setup"
                ? t.login.create
                : mode === "recover"
                  ? t.login.recoverBtn
                  : t.login.signIn}
          </button>
        </form>

        <div className="login-alt">
          <button type="button" className="secondary" disabled={busy} onClick={() => demo()}>
            {t.login.demo}
          </button>
          <p className="muted">{t.login.demoHint}</p>
          {mode !== "recover" && (
            <button
              type="button"
              className="linkish"
              onClick={() => setMode(mode === "setup" ? "login" : "recover")}
            >
              {mode === "setup" ? t.login.signIn : t.login.recover}
            </button>
          )}
          {status === "setup" && mode !== "setup" && (
            <button type="button" className="linkish" onClick={() => setMode("setup")}>
              {t.login.setupTitle}
            </button>
          )}
        </div>
      </section>
    </div>
  );
}
