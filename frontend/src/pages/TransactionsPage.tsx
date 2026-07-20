import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { formatKr, moneyApi, type Transaction } from "../api";
import CategoryEditModal from "../components/CategoryEditModal";

export default function TransactionsPage() {
  const [params, setParams] = useSearchParams();
  const reviewOnly = params.get("review") === "1";
  const incomeOnly = params.get("income") === "1";
  const categoryFilter = params.get("category") || undefined;
  const [rows, setRows] = useState<Transaction[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [editing, setEditing] = useState<Transaction | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () =>
    Promise.all([
      moneyApi.transactions({
        needs_review: reviewOnly ? true : undefined,
        income_review: incomeOnly ? true : undefined,
        category: categoryFilter,
      }),
      moneyApi.categories(),
    ])
      .then(([t, c]) => {
        setRows(t.transactions);
        setCategories(c.categories);
      })
      .catch((e) => setError(String(e)));

  useEffect(() => {
    load();
  }, [reviewOnly, incomeOnly, categoryFilter]);

  const title = useMemo(() => {
    if (incomeOnly) return "Income to review";
    if (reviewOnly) return "Needs category review";
    if (categoryFilter) return `Category: ${categoryFilter}`;
    return "All transactions";
  }, [reviewOnly, incomeOnly, categoryFilter]);

  async function save(category: string, remember: boolean) {
    if (!editing) return;
    await moneyApi.updateCategory(editing.id, category, remember);
    setEditing(null);
    await load();
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
            Unclear only
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
            Income review
          </label>
        </div>
      </div>
      <p className="lede">
        Tick <em>Remember for similar purchases</em> when recategorizing to teach SirDoge for next
        import.
      </p>
      {error && <p className="error">{error}</p>}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Description</th>
              <th>Amount</th>
              <th>Category</th>
              <th>Source</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.id} className={t.needs_review ? "needs-review" : undefined}>
                <td>{t.tx_date}</td>
                <td>
                  <div>{t.raw_description}</div>
                  {t.needs_review ? <span className="badge">unclear</span> : null}
                </td>
                <td className={t.amount < 0 ? "neg" : "pos"}>{formatKr(t.amount)}</td>
                <td>{t.category}</td>
                <td className="muted">{t.category_source}</td>
                <td>
                  <button type="button" onClick={() => setEditing(t)}>
                    Edit
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <p className="muted">No transactions in this view.</p>}
      </div>

      {editing && (
        <CategoryEditModal
          tx={editing}
          categories={categories}
          onClose={() => setEditing(null)}
          onSave={save}
        />
      )}
    </div>
  );
}
