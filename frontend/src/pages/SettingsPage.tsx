import { useEffect, useState } from "react";
import { moneyApi, settingsApi } from "../api";
import { useI18n } from "../i18n";
import { CATEGORIES } from "../categories";

export default function SettingsPage() {
  const { t, cat } = useI18n();
  const [settings, setSettings] = useState<Record<string, unknown>>({});
  const [budgets, setBudgets] = useState<Array<Record<string, unknown>>>([]);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    settingsApi.get().then(setSettings);
    moneyApi.budgets().then((b) => setBudgets(b.budgets));
  }, []);

  async function save(patch: Record<string, unknown>) {
    const next = await settingsApi.patch(patch);
    setSettings(next);
    if (patch.theme === "dark") document.documentElement.dataset.theme = "dark";
    if (patch.theme === "light") delete document.documentElement.dataset.theme;
    setMsg(t.common.save);
  }

  return (
    <div className="stack">
      <h1>{t.settings.title}</h1>

      <section className="panel form-grid">
        <label>
          {t.settings.defaultMonths}
          <select
            value={String(settings.default_months ?? 12)}
            onChange={(e) => save({ default_months: Number(e.target.value) })}
          >
            {[3, 6, 12].map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t.settings.monthlyIncome}
          <input
            type="number"
            value={Number(settings.monthly_income ?? 0)}
            onChange={(e) => save({ monthly_income: Number(e.target.value) })}
          />
        </label>
        <label className="toggle full">
          <input
            type="checkbox"
            checked={Boolean(settings.delete_upload_after_import ?? true)}
            onChange={(e) => save({ delete_upload_after_import: e.target.checked })}
          />
          {t.settings.deleteUpload}
        </label>
        <label>
          {t.settings.theme}
          <select
            value={String(settings.theme ?? "light")}
            onChange={(e) => save({ theme: e.target.value })}
          >
            <option value="light">{t.settings.light}</option>
            <option value="dark">{t.settings.dark}</option>
          </select>
        </label>
        <p className="muted full">{t.settings.incomeHint}</p>
        <p className="muted full">
          {t.settings.dataDir}: <code>{String(settings.data_dir ?? "")}</code>
        </p>
      </section>

      <section className="panel">
        <h2>{t.settings.budgets}</h2>
        <p className="muted">{t.settings.budgetsHint}</p>
        <div className="budget-grid">
          {CATEGORIES.filter((c) => !["Income", "Transfers", "Unclear"].includes(c)).map(
            (category) => {
              const row = budgets.find((b) => b.category === category);
              return (
                <label key={category}>
                  {cat(category)}
                  <input
                    type="number"
                    placeholder={t.settings.perMonth}
                    defaultValue={row?.monthly_limit != null ? String(row.monthly_limit) : ""}
                    onBlur={(e) => {
                      const v = e.target.value.trim();
                      moneyApi
                        .setBudget(category, v ? Number(v) : null, Boolean(v))
                        .then(() => moneyApi.budgets().then((b) => setBudgets(b.budgets)));
                    }}
                  />
                </label>
              );
            },
          )}
        </div>
      </section>

      {msg && <p className="banner ok">{msg}</p>}
    </div>
  );
}
