import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import EmptyState from "../components/EmptyState";
import { formatKr, moneyApi, type Transaction } from "../api";
import CategoryEditModal from "../components/CategoryEditModal";
import { useI18n } from "../i18n";

type GroupEdit = { key: string; txs: Transaction[] };

export default function TransactionsPage() {
  const { t, cat } = useI18n();
  const [params, setParams] = useSearchParams();
  const reviewOnly = params.get("review") === "1";
  const incomeOnly = params.get("income") === "1";
  const categoryFilter = params.get("category") || undefined;
  const [rows, setRows] = useState<Transaction[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [editing, setEditing] = useState<Transaction | null>(null);
  const [groupEdit, setGroupEdit] = useState<GroupEdit | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  const load = () => {
    setLoading(true);
    return Promise.all([
      moneyApi.transactions({
        needs_review: reviewOnly ? true : undefined,
        income_review: incomeOnly ? true : undefined,
        category: categoryFilter,
        search: search.trim() || undefined,
      }),
      moneyApi.categories(),
    ])
      .then(([tx, c]) => {
        setRows(tx.transactions);
        setCategories(c.categories);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [reviewOnly, incomeOnly, categoryFilter, search]);

  const title = useMemo(() => {
    if (incomeOnly) return t.transactions.incomeReview;
    if (reviewOnly) return t.transactions.needsReview;
    if (categoryFilter) return `${t.transactions.categoryPrefix} ${cat(categoryFilter)}`;
    return t.transactions.all;
  }, [reviewOnly, incomeOnly, categoryFilter, t, cat]);

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

  return (
    <div className="stack">
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
      <label className="search-inline">
        {t.transactions.search}
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t.transactions.searchPlaceholder}
        />
      </label>

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

      {!loading && rows.length === 0 && !reviewOnly && !incomeOnly && !categoryFilter && (
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
          categories={categories}
          onClose={() => setEditing(null)}
          onSave={save}
        />
      )}
      {groupEdit && (
        <CategoryEditModal
          txs={groupEdit.txs}
          matchText={groupEdit.key}
          categories={categories}
          onClose={() => setGroupEdit(null)}
          onSave={save}
        />
      )}
    </div>
  );
}
