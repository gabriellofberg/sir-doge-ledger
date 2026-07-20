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
import { formatKr, moneyApi, type CashflowMonth, type MoneyStats } from "../api";

const CHART_COLORS = [
  "#1E3A5F",
  "#2F855A",
  "#C53030",
  "#B8953A",
  "#4A5568",
  "#805AD5",
  "#319795",
  "#DD6B20",
];

export default function DashboardPage() {
  const [stats, setStats] = useState<MoneyStats | null>(null);
  const [cashflow, setCashflow] = useState<CashflowMonth[]>([]);
  const [breakdown, setBreakdown] = useState<Array<{ category: string; total: number }>>([]);
  const [months, setMonths] = useState(12);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      moneyApi.completeness(),
      moneyApi.cashflow(months),
      moneyApi.breakdown("spent"),
    ])
      .then(([s, cf, bd]) => {
        setStats(s);
        setCashflow(cf.months);
        setBreakdown(
          bd.categories.map((c) => ({
            category: c.category,
            total: Math.abs(Number(c.total)),
          })),
        );
      })
      .catch((e) => setError(String(e)));
  }, [months]);

  const barData = useMemo(
    () =>
      cashflow.map((m) => ({
        month: m.month,
        Income: m.income,
        Spent: Math.abs(m.spent),
        Net: m.net,
      })),
    [cashflow],
  );

  if (error) return <p className="error">{error}</p>;
  if (!stats) return <p className="muted">Loading…</p>;

  return (
    <div className="stack">
      <section className="hero-panel">
        <h1>Money overview</h1>
        <p className="lede">
          Income vs spending — transfers excluded so your own account moves do not inflate totals.
        </p>
        <div className="range-toggle">
          {[3, 6, 12].map((m) => (
            <button
              key={m}
              type="button"
              className={months === m ? "primary selected" : ""}
              onClick={() => setMonths(m)}
            >
              {m} mo
            </button>
          ))}
        </div>
      </section>

      <div className="stat-grid">
        <div className="stat income-stat">
          <span className="label">Income</span>
          <strong>{formatKr(stats.total_income)}</strong>
        </div>
        <div className="stat spend-stat">
          <span className="label">Spent</span>
          <strong>{formatKr(Math.abs(stats.total_spent))}</strong>
        </div>
        <div className="stat">
          <span className="label">Net</span>
          <strong className={stats.net >= 0 ? "pos" : "neg"}>{formatKr(stats.net)}</strong>
        </div>
        <div className="stat warn">
          <span className="label">Needs review</span>
          <strong>{stats.unclear_count}</strong>
          {stats.unclear_count > 0 && <Link to="/transactions?review=1">Review →</Link>}
        </div>
      </div>

      {(stats.unclear_count > 0 || stats.uncategorized_income_count > 0) && (
        <section className="panel completeness">
          <h2>Before you trust these numbers</h2>
          <ul>
            {stats.unclear_count > 0 && (
              <li>
                <Link to="/transactions?review=1">{stats.unclear_count} unclear categories</Link>
              </li>
            )}
            {stats.uncategorized_income_count > 0 && (
              <li>
                <Link to="/transactions?income=1">
                  {stats.uncategorized_income_count} income rows not marked as Income
                </Link>
              </li>
            )}
            {stats.transfer_volume > 0 && (
              <li className="muted">
                Transfers {formatKr(stats.transfer_volume)} excluded from income/spent
              </li>
            )}
          </ul>
        </section>
      )}

      {barData.length > 0 && (
        <>
          <section className="panel chart-panel">
            <h2>Monthly income vs spent</h2>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={barData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip formatter={(v: number) => formatKr(v)} />
                <Legend />
                <Bar dataKey="Income" fill="#2F855A" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Spent" fill="#C53030" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </section>

          <section className="panel chart-panel">
            <h2>Monthly net</h2>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={barData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip formatter={(v: number) => formatKr(v)} />
                <Line type="monotone" dataKey="Net" stroke="#1E3A5F" strokeWidth={2} dot />
              </LineChart>
            </ResponsiveContainer>
          </section>
        </>
      )}

      {breakdown.length > 0 && (
        <section className="panel chart-panel">
          <h2>Spending by category</h2>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={breakdown}
                dataKey="total"
                nameKey="category"
                cx="50%"
                cy="50%"
                outerRadius={100}
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

      {barData.length === 0 && (
        <p className="muted">
          No data yet. <Link to="/import">Import a bank export</Link>.
        </p>
      )}
    </div>
  );
}
