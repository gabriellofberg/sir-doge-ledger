import { useEffect, useState, type FormEvent } from "react";
import { moneyApi, settingsApi, type CategoryDeletePreview } from "../api";
import { budgetCategorySlugs, useCategories } from "../categories";
import { useI18n, tr } from "../i18n";

export default function SettingsPage() {
  const { t, cat } = useI18n();
  const {
    categories,
    createCategory,
    renameCategory,
    deleteCategory,
    deleteCategoryPreview,
    mergeCategory,
  } = useCategories();
  const [settings, setSettings] = useState<Record<string, unknown>>({});
  const [budgets, setBudgets] = useState<Array<Record<string, unknown>>>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [newCategoryName, setNewCategoryName] = useState("");
  const [creating, setCreating] = useState(false);
  const [renameDrafts, setRenameDrafts] = useState<Record<string, string>>({});

  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [deletePreview, setDeletePreview] = useState<CategoryDeletePreview | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);

  const [mergeSource, setMergeSource] = useState<string | null>(null);
  const [mergeTarget, setMergeTarget] = useState("");
  const [mergeBusy, setMergeBusy] = useState(false);

  useEffect(() => {
    settingsApi.get().then(setSettings);
    moneyApi.budgets().then((b) => setBudgets(b.budgets));
  }, []);

  useEffect(() => {
    setRenameDrafts(Object.fromEntries(categories.map((c) => [c.slug, c.name])));
  }, [categories]);

  async function save(patch: Record<string, unknown>) {
    const next = await settingsApi.patch(patch);
    setSettings(next);
    if (patch.theme === "dark") document.documentElement.dataset.theme = "dark";
    if (patch.theme === "light") delete document.documentElement.dataset.theme;
    setMsg(t.common.save);
  }

  async function submitNewCategory(e: FormEvent) {
    e.preventDefault();
    const name = newCategoryName.trim();
    if (!name) return;
    setCreating(true);
    setError(null);
    try {
      await createCategory(name);
      setNewCategoryName("");
      setMsg(t.settings.categoryCreated);
    } catch (err) {
      setError(String(err));
    } finally {
      setCreating(false);
    }
  }

  async function saveRename(slug: string) {
    const name = (renameDrafts[slug] ?? "").trim();
    const current = categories.find((c) => c.slug === slug)?.name ?? "";
    if (!name || name === current) return;
    setError(null);
    try {
      await renameCategory(slug, name);
      setMsg(t.common.save);
    } catch (err) {
      setError(String(err));
      setRenameDrafts((d) => ({ ...d, [slug]: current }));
    }
  }

  async function openDeletePreview(slug: string) {
    setError(null);
    setDeleteTarget(slug);
    setDeletePreview(null);
    try {
      const preview = await deleteCategoryPreview(slug);
      setDeletePreview(preview);
    } catch (err) {
      setError(String(err));
      setDeleteTarget(null);
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    setDeleteBusy(true);
    setError(null);
    try {
      const result = await deleteCategory(deleteTarget);
      setMsg(
        tr(t.settings.categoryDeleted, {
          recategorized: result.transactions_recategorized,
          unclear: result.transactions_unclear,
        }),
      );
      setDeleteTarget(null);
      setDeletePreview(null);
    } catch (err) {
      setError(String(err));
    } finally {
      setDeleteBusy(false);
    }
  }

  async function confirmMerge(e: FormEvent) {
    e.preventDefault();
    if (!mergeSource || !mergeTarget) return;
    setMergeBusy(true);
    setError(null);
    try {
      const result = await mergeCategory(mergeSource, mergeTarget);
      setMsg(
        tr(t.settings.categoryMerged, {
          source: cat(result.merged_slug),
          target: cat(result.target_slug),
          count: result.transactions_moved,
        }),
      );
      setMergeSource(null);
      setMergeTarget("");
    } catch (err) {
      setError(String(err));
    } finally {
      setMergeBusy(false);
    }
  }

  const budgetSlugs = budgetCategorySlugs(categories);

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

      <section className="panel form-grid">
        <h2 className="full">{t.settings.merchantRules}</h2>
        <label>
          {t.settings.foodoraThreshold}
          <input
            type="number"
            min={0}
            step={50}
            value={Number(settings.foodora_grocery_threshold ?? 350)}
            onChange={(e) => save({ foodora_grocery_threshold: Number(e.target.value) })}
          />
        </label>
        <p className="muted full">{t.settings.foodoraHint}</p>
      </section>

      <section className="panel">
        <h2>{t.settings.categoriesTitle}</h2>
        <p className="muted">{t.settings.categoriesHint}</p>
        <form className="row-between category-add" onSubmit={submitNewCategory}>
          <label className="full">
            {t.settings.newCategory}
            <input
              value={newCategoryName}
              onChange={(e) => setNewCategoryName(e.target.value)}
              placeholder={t.settings.newCategoryPlaceholder}
            />
          </label>
          <button type="submit" className="primary" disabled={creating || !newCategoryName.trim()}>
            {t.settings.addCategory}
          </button>
        </form>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t.settings.categoryName}</th>
                <th>{t.settings.categoryTxCount}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {categories.map((c) => (
                <tr key={c.slug}>
                  <td>
                    <input
                      value={renameDrafts[c.slug] ?? c.name}
                      onChange={(e) =>
                        setRenameDrafts((d) => ({ ...d, [c.slug]: e.target.value }))
                      }
                      onBlur={() => saveRename(c.slug)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") e.currentTarget.blur();
                      }}
                      aria-label={t.settings.categoryName}
                    />
                    {c.is_system ? (
                      <span className="badge muted">{t.settings.systemCategory}</span>
                    ) : null}
                  </td>
                  <td>{c.tx_count ?? 0}</td>
                  <td className="category-actions">
                    {!c.is_system ? (
                      <>
                        <button type="button" onClick={() => setMergeSource(c.slug)}>
                          {t.settings.mergeCategory}
                        </button>
                        <button type="button" className="danger" onClick={() => openDeletePreview(c.slug)}>
                          {t.common.delete}
                        </button>
                      </>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <h2>{t.settings.budgets}</h2>
        <p className="muted">{t.settings.budgetsHint}</p>
        <div className="budget-grid">
          {budgetSlugs.map((slug) => {
            const row = budgets.find((b) => b.category === slug);
            return (
              <label key={slug}>
                {cat(slug)}
                <input
                  type="number"
                  placeholder={t.settings.perMonth}
                  defaultValue={row?.monthly_limit != null ? String(row.monthly_limit) : ""}
                  onBlur={(e) => {
                    const v = e.target.value.trim();
                    moneyApi
                      .setBudget(slug, v ? Number(v) : null, Boolean(v))
                      .then(() => moneyApi.budgets().then((b) => setBudgets(b.budgets)));
                  }}
                />
              </label>
            );
          })}
        </div>
      </section>

      {error && <p className="error">{error}</p>}
      {msg && <p className="banner ok">{msg}</p>}

      {deleteTarget && (
        <div className="modal-backdrop" role="presentation" onClick={() => setDeleteTarget(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>{t.settings.deleteCategoryTitle}</h2>
            <p className="muted">{tr(t.settings.deleteCategoryLead, { name: cat(deleteTarget) })}</p>
            {deletePreview ? (
              <ul className="preview-stats">
                <li>{tr(t.settings.previewTxCount, { count: deletePreview.tx_count })}</li>
                <li>
                  {tr(t.settings.previewRecategorizable, {
                    count: deletePreview.estimated_recategorizable,
                  })}
                </li>
                <li>{tr(t.settings.previewUnclear, { count: deletePreview.estimated_unclear })}</li>
                {deletePreview.rules_count > 0 ? (
                  <li>{tr(t.settings.previewRules, { count: deletePreview.rules_count })}</li>
                ) : null}
                {deletePreview.budgets_count > 0 ? (
                  <li>{tr(t.settings.previewBudgets, { count: deletePreview.budgets_count })}</li>
                ) : null}
              </ul>
            ) : (
              <p className="muted">{t.common.loading}</p>
            )}
            <p className="muted">{t.settings.deleteCategoryHint}</p>
            <div className="modal-actions">
              <button type="button" onClick={() => setDeleteTarget(null)} disabled={deleteBusy}>
                {t.common.cancel}
              </button>
              <button
                type="button"
                className="danger"
                disabled={deleteBusy || !deletePreview || deletePreview.is_system}
                onClick={confirmDelete}
              >
                {t.common.delete}
              </button>
            </div>
          </div>
        </div>
      )}

      {mergeSource && (
        <div className="modal-backdrop" role="presentation" onClick={() => setMergeSource(null)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={confirmMerge}>
            <h2>{t.settings.mergeCategoryTitle}</h2>
            <p className="muted">
              {tr(t.settings.mergeCategoryLead, {
                source: cat(mergeSource),
              })}
            </p>
            <label>
              {t.settings.mergeTarget}
              <select
                value={mergeTarget}
                onChange={(e) => setMergeTarget(e.target.value)}
                required
              >
                <option value="">{t.settings.mergeTargetPlaceholder}</option>
                {categories
                  .filter((c) => c.slug !== mergeSource)
                  .map((c) => (
                    <option key={c.slug} value={c.slug}>
                      {cat(c.slug)}
                    </option>
                  ))}
              </select>
            </label>
            <p className="muted">{t.settings.mergeCategoryHint}</p>
            <div className="modal-actions">
              <button type="button" onClick={() => setMergeSource(null)} disabled={mergeBusy}>
                {t.common.cancel}
              </button>
              <button type="submit" className="primary" disabled={mergeBusy || !mergeTarget}>
                {t.settings.mergeConfirm}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
