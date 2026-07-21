import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import EmptyState from "../components/EmptyState";
import { formatKr, moneyApi, type Transaction } from "../api";
import CategoryEditModal from "../components/CategoryEditModal";
import { useCategories } from "../categories";
import { useI18n, tr } from "../i18n";

type GroupEdit = { key: string; txs: Transaction[] };

const SORT_OPTIONS = [
  "date_desc",
  "date_asc",
  "amount_desc",
  "amount_asc",
  "description_asc",
  "description_desc",
] as const;

type SortOption = (typeof SORT_OPTIONS)[number];

function isSortOption(v: string | null): v is SortOption {
  return SORT_OPTIONS.includes(v as SortOption);
}

export default function TransactionsPage() {
  const { t, cat } = useI18n();
  const { slugs: categorySlugs } = useCategories();
  const [params, setParams] = useSearchParams();
  const reviewOnly = params.get("review") === "1";
  const incomeOnly = params.get("income") === "1";
  const categoryFilter = params.get("category") || "";
  const monthFilter = params.get("month") || "";
  const sortParam = params.get("sort");
  const sortFilter: SortOption = isSortOption(sortParam) ? sortParam : "date_desc";
  const searchParam = params.get("search") || "";
  const [rows, setRows] = useState<Transaction[]>([]);
  const [monthOptions, setMonthOptions] = useState<string[]>([]);
  const [editing, setEditing] = useState<Transaction | null>(null);
  const [groupEdit, setGroupEdit] = useState<GroupEdit | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchDraft, setSearchDraft] = useState(searchParam);

  useEffect(() => {
    setSearchDraft(searchParam);
  }, [searchParam]);

  useEffect(() => {
    moneyApi.cashflow(24).then((cf) => {
      setMonthOptions(cf.months.map((m) => m.month));
    });
  }, []);

  const load = () => {
    setLoading(true);
    return Promise.all([
      moneyApi.transactions({
        needs_review: reviewOnly ? true : undefined,
        income_review: incomeOnly ? true : undefined,
        category: categoryFilter || undefined,
        month: monthFilter || undefined,
        sort: sortFilter,
        search: searchParam.trim() || undefined,
      }),
    ])
      .then(([tx]) => {
        setRows(tx.transactions);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [reviewOnly, incomeOnly, categoryFilter, monthFilter, sortFilter, searchParam]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      const trimmed = searchDraft.trim();
      if (trimmed === searchParam) return;
      const next = new URLSearchParams(params);
      if (trimmed) next.set("search", trimmed);
      else next.delete("search");
      setParams(next, { replace: true });
    }, 300);
    return () => window.clearTimeout(handle);
  }, [searchDraft, searchParam, params, setParams]);

  function patchParams(patch: Record<string, string | null>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(patch)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    setParams(next);
  }

  const title = useMemo(() => {
    if (incomeOnly) return t.transactions.incomeReview;
    if (reviewOnly) return t.transactions.needsReview;
    if (categoryFilter) return `${t.transactions.categoryPrefix} ${cat(categoryFilter)}`;
    return t.transactions.all;
  }, [reviewOnly, incomeOnly, categoryFilter, t, cat]);

  const hasActiveFilters = Boolean(
    categoryFilter || monthFilter || searchParam || sortFilter !== "date_desc",
  );

  const summary = useMemo(() => {
    const total = rows.reduce((sum, row) => sum + Math.abs(row.amount), 0);
    return { count: rows.length, total };
  }, [rows]);

  const summaryContext = useMemo(() => {
    const parts: string[] = [];
    if (monthFilter) parts.push(monthFilter);
    if (categoryFilter) parts.push(cat(categoryFilter));
    return parts.join(" · ");
  }, [monthFilter, categoryFilter, cat]);

  const groups = useMemo(() => {
    if (!reviewOnly) return [];
    const map = new Map<string, Transaction[]>();
    for (const row of rows) {
      const key = (row.group_key || row.normalized_merchant || "UNKNOWN").trim() || "UNKNOWN";
      const list = map.get(key) ?? [];
      list.push(row);
      map.set(key, list);
    }
    return [...map.entries()]
      .map(([key, txs]) => ({ key, txs }))
      .sort((a, b) => b.txs.length - a.txs.length || a.key.localeCompare(b.key));
  }, [rows, reviewOnly]);

  async function save(category: string, remember: boolean, matchText?: string) {
    if (groupEdit) {
      await moneyApi.bulkUpdateCategory(
        groupEdit.txs.map((x) => x.id),
        category,
        remember,
        matchText || groupEdit.key,
      );
      setGroupEdit(null);
    } else if (editing) {
      await moneyApi.updateCategory(editing.id, category, remember, matchText);
      setEditing(null);
    }
    await load();
  }

  function renderRow(row: Transaction) {
    return (
      <tr key={row.id} className={row.needs_review ? "needs-review" : undefined}>
        <td>{row.tx_date}</td>
        <td>
          <div>{row.raw_description}</div>
          {row.needs_review ? <span className="badge">{t.transactions.unclear}</span> : null}
        </td>
        <td className={row.amount < 0 ? "neg" : "pos"}>{formatKr(row.amount)}</td>
        <td>{cat(row.category)}</td>
        <td className="muted">{row.category_source}</td>
        <td>
          <button type="button" onClick={() => setEditing(row)}>
            {t.transactions.edit}
          </button>
        </td>
      </tr>
    );
  }

  const sortLabel = (key: SortOption) => {
    const labels: Record<SortOption, string> = {
      date_desc: t.transactions.sortDateDesc,
      date_asc: t.transactions.sortDateAsc,
      amount_desc: t.transactions.sortAmountDesc,
      amount_asc: t.transactions.sortAmountAsc,
      description_asc: t.transactions.sortDescriptionAsc,
      description_desc: t.transactions.sortDescriptionDesc,
    };
    return labels[key];
  };

  return (
    <div className="stack transactions-page">
      <div className="row-between">
        <h1>{title}</h1>
        <div className="filter-row">
          <label className="toggle">
            <input
              type="checkbox"
              checked={reviewOnly}
              onChange={(e) => {
                const next = new URLSearchParams(params);
                if (e.target.checked) {
                  next.set("review", "1");
                  next.delete("income");
                } else next.delete("review");
                setParams(next);
              }}
            />
            {t.transactions.unclearOnly}
          </label>
          <label className="toggle">
            <input
              type="checkbox"
              checked={incomeOnly}
              onChange={(e) => {
                const next = new URLSearchParams(params);
                if (e.target.checked) {
                  next.set("income", "1");
                  next.delete("review");
                } else next.delete("income");
                setParams(next);
              }}
            />
            {t.transactions.incomeFilter}
          </label>
        </div>
      </div>
      <p className="lede">{reviewOnly ? t.transactions.reviewLede : t.transactions.lede}</p>

      <div className="tx-toolbar-sticky">
        <section className="panel tx-filters" aria-label={t.transactions.filtersLabel}>
          <label>
            <span className="label">{t.transactions.filterMonth}</span>
            <select
              value={monthFilter}
              onChange={(e) => patchParams({ month: e.target.value || null })}
            >
              <option value="">{t.transactions.filterAll}</option>
              {[...monthOptions].reverse().map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="label">{t.transactions.filterCategory}</span>
            <select
              value={categoryFilter}
              onChange={(e) => patchParams({ category: e.target.value || null })}
            >
              <option value="">{t.transactions.filterAll}</option>
              {categorySlugs.map((c) => (
                <option key={c} value={c}>
                  {cat(c)}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="label">{t.transactions.filterSort}</span>
            <select
              value={sortFilter}
              onChange={(e) => patchParams({ sort: e.target.value === "date_desc" ? null : e.target.value })}
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {sortLabel(opt)}
                </option>
              ))}
            </select>
          </label>
          <label className="tx-search">
            <span className="label">{t.transactions.search}</span>
            <input
              type="search"
              value={searchDraft}
              onChange={(e) => setSearchDraft(e.target.value)}
              placeholder={t.transactions.searchPlaceholder}
            />
          </label>
        </section>

        {!loading && rows.length > 0 && (hasActiveFilters || reviewOnly || incomeOnly) && (
          <p className="tx-summary">
            <strong>
              {tr(t.transactions.filterSummary, {
                count: String(summary.count),
                total: formatKr(summary.total),
              })}
            </strong>
            {summaryContext ? <span className="muted"> ({summaryContext})</span> : null}
          </p>
        )}
      </div>

      {reviewOnly && !loading && groups.length > 0 ? (
        <div className="stack review-groups">
          {groups.map(({ key, txs }) => (
            <section key={key} className="panel review-group">
              <div className="row-between review-group-head">
                <div>
                  <h2 className="review-group-title">{key}</h2>
                  <p className="muted">
                    {t.transactions.groupCount.replace("{count}", String(txs.length))}
                  </p>
                </div>
                <button type="button" className="primary" onClick={() => setGroupEdit({ key, txs })}>
                  {t.transactions.categorizeGroup}
                </button>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>{t.transactions.date}</th>
                      <th>{t.transactions.description}</th>
                      <th>{t.transactions.amount}</th>
                      <th>{t.transactions.category}</th>
                      <th>{t.transactions.source}</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>{txs.map(renderRow)}</tbody>
                </table>
              </div>
            </section>
          ))}
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t.transactions.date}</th>
                <th>{t.transactions.description}</th>
                <th>{t.transactions.amount}</th>
                <th>{t.transactions.category}</th>
                <th>{t.transactions.source}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={6} className="table-empty">
                    {t.transactions.loading}
                  </td>
                </tr>
              )}
              {!loading && rows.map(renderRow)}
              {!loading && rows.length === 0 && (
                <tr>
                  <td colSpan={6} className="table-empty">
                    {t.transactions.emptyView}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {!loading && rows.length === 0 && !reviewOnly && !incomeOnly && !hasActiveFilters && (
        <EmptyState
          title={t.transactions.emptyTitle}
          description={t.transactions.emptyHint}
          actionLabel={t.transactions.emptyCta}
          actionTo="/import"
        />
      )}

      {editing && (
        <CategoryEditModal
          tx={editing}
          categories={categorySlugs}
          onClose={() => setEditing(null)}
          onSave={save}
        />
      )}
      {groupEdit && (
        <CategoryEditModal
          txs={groupEdit.txs}
          matchText={groupEdit.key}
          categories={categorySlugs}
          onClose={() => setGroupEdit(null)}
          onSave={save}
        />
      )}
    </div>
  );
}
