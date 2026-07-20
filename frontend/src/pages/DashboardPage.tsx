import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import ChartPlaceholder from "../components/ChartPlaceholder";
import EmptyState from "../components/EmptyState";
import { formatKr, moneyApi, type CashflowMonth, type MoneyStats } from "../api";
import { useI18n, tr } from "../i18n";

const CHART_COLORS = ["#1e3a5f", "#2f855a", "#c53030", "#b8953a", "#4a5568", "#805ad5", "#319795"];

const EMPTY_STATS: MoneyStats = {
  transaction_count: 0,
  unclear_count: 0,
  pending_recurring: 0,
  total_spent: 0,
  total_income: 0,
  net: 0,
  transfer_volume: 0,
  uncategorized_income_count: 0,
  recurring_yearly_total: 0,
};

export default function DashboardPage() {
  const { t, cat } = useI18n();
  const [stats, setStats] = useState<MoneyStats | null>(null);
  const [cashflow, setCashflow] = useState<CashflowMonth[]>([]);
  const [breakdown, setBreakdown] = useState<Array<{ category: string; total: number }>>([]);
  const [months, setMonths] = useState(12);
  const [loading, setLoading] = useState(true);
  const [alerts, setAlerts] = useState<Array<Record<string, unknown>>>([]);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      moneyApi.completeness(),
      moneyApi.cashflow(months),
      moneyApi.breakdown("spent"),
      moneyApi.alerts(),
    ])
      .then(([s, cf, bd, al]) => {
        setStats(s);
        setCashflow(cf.months);
        setBreakdown(
          bd.categories.map((c) => ({
            category: c.category,
            total: Math.abs(Number(c.total)),
          })),
        );
        setAlerts([...al.budget, ...al.price, ...al.recommendations]);
      })
      .finally(() => setLoading(false));
  }, [months]);

  const barData = useMemo(
    () =>
      cashflow.map((m) => ({
        month: m.month,
        [t.overview.income]: m.income,
        [t.overview.spent]: Math.abs(m.spent),
        [t.overview.net]: m.net,
      })),
    [cashflow, t],
  );

  const display = stats ?? EMPTY_STATS;
  const hasData = display.transaction_count > 0;

  if (loading) return <p className="muted page-loading">{t.overview.loading}</p>;

  function alertText(a: Record<string, unknown>): string {
    if (a.kind === "housing_high") return tr(t.overview.alertHousing, { pct: String(a.pct) });
    if (a.kind === "over_budget")
      return tr(t.overview.alertOverBudget, {
        category: cat(String(a.category)),
        spent: String(a.spent),
        limit: String(a.limit),
      });
    if (a.kind === "spending_up")
      return tr(t.overview.alertSpendingUp, {
        category: cat(String(a.category)),
        pct: String(a.pct_change),
      });
    if (a.kind === "spending_down")
      return tr(t.overview.alertSpendingDown, {
        category: cat(String(a.category)),
        pct: String(Math.abs(Number(a.pct_change))),
      });
    if (a.kind === "set_income") return t.overview.alertSetIncome;
    if (a.normalized_merchant)
      return tr(t.overview.alertPrice, {
        merchant: String(a.normalized_merchant),
        old: String(a.old_amount),
        new: String(a.new_amount),
      });
    return "";
  }

  return (
    <div className="stack">
      <header className="page-head">
        <div>
          <h1>{t.overview.title}</h1>
          <p className="lede">{hasData ? t.overview.ledeHasData : t.overview.ledeEmpty}</p>
        </div>
        <div className="range-toggle">
          {[3, 6, 12].map((m) => (
            <button
              key={m}
              type="button"
              className={months === m ? "primary selected" : ""}
              onClick={() => setMonths(m)}
            >
              {m} {t.overview.months}
            </button>
          ))}
        </div>
      </header>

      <div className="stat-grid">
        <div className="stat income-stat">
          <span className="label">{t.overview.income}</span>
          <strong>{formatKr(display.total_income)}</strong>
        </div>
        <div className="stat spend-stat">
          <span className="label">{t.overview.spent}</span>
          <strong>{formatKr(Math.abs(display.total_spent))}</strong>
        </div>
        <div className="stat">
          <span className="label">{t.overview.net}</span>
          <strong className={display.net >= 0 ? "pos" : "neg"}>{formatKr(display.net)}</strong>
        </div>
        <div className={`stat ${display.unclear_count > 0 ? "warn" : ""}`}>
          <span className="label">{t.overview.review}</span>
          <strong>{display.unclear_count}</strong>
          {display.unclear_count > 0 && (
            <Link to="/transactions?review=1">{t.overview.reviewLink}</Link>
          )}
        </div>
      </div>

      {alerts.length > 0 && (
        <section className="panel alerts-panel">
          <h2>{t.overview.insights}</h2>
          {alerts.slice(0, 6).map((a, i) => {
            const text = alertText(a);
            if (!text) return null;
            return (
              <div key={i} className={`alert ${String(a.severity ?? "warn")}`}>
                {text}
              </div>
            );
          })}
        </section>
      )}

      {!hasData && (
        <EmptyState
          title={t.overview.empty}
          description={t.overview.emptyHint}
          actionLabel={t.overview.importCta}
          actionTo="/import"
        />
      )}

      {hasData && (display.unclear_count > 0 || display.uncategorized_income_count > 0) && (
        <section className="panel completeness">
          <h2>{t.overview.completenessTitle}</h2>
          <ul>
            {display.unclear_count > 0 && (
              <li>
                <Link to="/transactions?review=1">
                  {display.unclear_count} {t.overview.unclearCats}
                </Link>
              </li>
            )}
            {display.uncategorized_income_count > 0 && (
              <li>
                <Link to="/transactions?income=1">
                  {display.uncategorized_income_count} {t.overview.uncategorizedIncome}
                </Link>
              </li>
            )}
            {display.transfer_volume > 0 && (
              <li className="muted">
                {formatKr(display.transfer_volume)} — {t.overview.transfersExcluded}
              </li>
            )}
          </ul>
        </section>
      )}

      {hasData && barData.length > 0 ? (
        <div className="chart-grid">
          <section className="panel chart-panel">
            <h2>{t.overview.chartIncomeSpent}</h2>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={barData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e8dcc8" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v: number) => formatKr(v)} />
                <Legend />
                <Bar dataKey={t.overview.income} fill="#2f855a" radius={[6, 6, 0, 0]} />
                <Bar dataKey={t.overview.spent} fill="#c53030" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </section>

          <section className="panel chart-panel">
            <h2>{t.overview.chartNet}</h2>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={barData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e8dcc8" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v: number) => formatKr(v)} />
                <Line
                  type="monotone"
                  dataKey={t.overview.net}
                  stroke="#1e3a5f"
                  strokeWidth={2.5}
                  dot
                />
              </LineChart>
            </ResponsiveContainer>
          </section>

          {breakdown.length > 0 && (
            <section className="panel chart-panel chart-wide">
              <h2>{t.overview.chartCategory}</h2>
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie
                    data={breakdown.map((b) => ({ ...b, category: cat(b.category) }))}
                    dataKey="total"
                    nameKey="category"
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={95}
                    label={({ category, total }: { category: string; total: number }) =>
                      `${category}: ${formatKr(total)}`
                    }
                  >
                    {breakdown.map((_, i) => (
                      <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: number) => formatKr(v)} />
                </PieChart>
              </ResponsiveContainer>
            </section>
          )}
        </div>
      ) : (
        <div className="chart-grid">
          <ChartPlaceholder title={t.overview.chartIncomeSpent} hint={t.overview.chartIncomeHint} />
          <ChartPlaceholder title={t.overview.chartNet} hint={t.overview.chartNetHint} />
          <section className="panel chart-panel chart-wide chart-placeholder">
            <h2>{t.overview.chartCategory}</h2>
            <div className="chart-placeholder-body">
              <div className="chart-placeholder-donut" aria-hidden />
              <p className="muted">{t.overview.chartCategoryHint}</p>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
