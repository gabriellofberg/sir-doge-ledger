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
import { formatKr, moneyApi, type CashflowMonth, type Insight, type MoneyStats } from "../api";
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
  const [breakdown, setBreakdown] = useState<Array<{ category: string; total: number; tx_count?: number }>>([]);
  const [months, setMonths] = useState(12);
  const [categoryMonth, setCategoryMonth] = useState<string>(""); // "" = whole selected range
  const [loading, setLoading] = useState(true);
  const [insights, setInsights] = useState<Insight[]>([]);

  useEffect(() => {
    setLoading(true);
    // Reset month pick when range changes if the month falls outside the new cashflow
    setCategoryMonth("");
    Promise.all([
      moneyApi.completeness(),
      moneyApi.cashflow(months),
      moneyApi.breakdown("spent", { months }),
      moneyApi.insights(months),
    ])
      .then(([s, cf, bd, ins]) => {
        setStats(s);
        setCashflow(cf.months);
        setBreakdown(
          bd.categories.map((c) => ({
            category: c.category,
            total: Math.abs(Number(c.total)),
            tx_count: c.tx_count,
          })),
        );
        setInsights(ins.insights);
      })
      .finally(() => setLoading(false));
  }, [months]);

  useEffect(() => {
    if (loading) return;
    const opts = categoryMonth ? { month: categoryMonth } : { months };
    moneyApi.breakdown("spent", opts).then((bd) => {
      setBreakdown(
        bd.categories.map((c) => ({
          category: c.category,
          total: Math.abs(Number(c.total)),
          tx_count: c.tx_count,
        })),
      );
    });
  }, [categoryMonth]);

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

  const categoryTotal = useMemo(
    () => breakdown.reduce((sum, b) => sum + b.total, 0),
    [breakdown],
  );

  const pieData = useMemo(
    () =>
      [...breakdown]
        .sort((a, b) => b.total - a.total)
        .map((b) => ({
          ...b,
          label: cat(b.category),
          pct: categoryTotal > 0 ? Math.round((b.total / categoryTotal) * 100) : 0,
        })),
    [breakdown, cat, categoryTotal],
  );

  const display = stats ?? EMPTY_STATS;
  const hasData = display.transaction_count > 0;

  if (loading) return <p className="muted page-loading">{t.overview.loading}</p>;

  function insightContent(insight: Insight): { title: string; body: string } | null {
    const p = insight.params;
    const kind = insight.kind;
    if (kind === "over_budget")
      return {
        title: cat(String(p.category)),
        body: tr(t.overview.alertOverBudget, {
          category: cat(String(p.category)),
          spent: String(p.spent),
          limit: String(p.limit),
        }),
      };
    if (kind === "spending_up")
      return {
        title: cat(String(p.category)),
        body: tr(t.overview.alertSpendingUp, {
          category: cat(String(p.category)),
          pct: String(p.pct_change),
        }),
      };
    if (kind === "spending_down")
      return {
        title: cat(String(p.category)),
        body: tr(t.overview.alertSpendingDown, {
          category: cat(String(p.category)),
          pct: String(Math.abs(Number(p.pct_change))),
        }),
      };
    if (kind === "savings_scenario")
      return {
        title: t.overview.insightSavingsTitle,
        body: tr(t.overview.insightSavingsBody, {
          category: cat(String(p.category)),
          spent: String(p.spent),
          months: String(p.months),
          pct: String(p.reduction_pct),
          savings: String(p.savings),
        }),
      };
    if (kind === "top_merchant")
      return {
        title: t.overview.insightTopMerchantTitle,
        body: tr(t.overview.insightTopMerchantBody, {
          merchant: String(p.merchant),
          spent: String(p.spent),
          pct: String(p.pct),
        }),
      };
    if (kind === "category_share")
      return {
        title: t.overview.insightCategoryShareTitle,
        body: tr(t.overview.insightCategoryShareBody, {
          category: cat(String(p.category)),
          pct: String(p.pct),
          spent: String(p.spent),
        }),
      };
    if (kind === "income_share")
      return {
        title: t.overview.insightIncomeShareTitle,
        body: tr(t.overview.insightIncomeShareBody, {
          category: cat(String(p.category)),
          pct: String(p.pct),
          guideline: String(p.guideline_hi),
        }),
      };
    if (kind === "mom_trend") {
      const up = p.direction === "up";
      return {
        title: up ? t.overview.insightMomUpTitle : t.overview.insightMomDownTitle,
        body: tr(up ? t.overview.insightMomUpBody : t.overview.insightMomDownBody, {
          pct: String(p.pct),
          month: String(p.month),
        }),
      };
    }
    if (kind === "yoy_change")
      return {
        title: t.overview.insightYoyTitle,
        body: tr(t.overview.insightYoyBody, {
          category: cat(String(p.category)),
          pct: String(p.pct),
          prevYear: String(p.prev_year),
        }),
      };
    if (kind === "recurring_burden")
      return {
        title: t.overview.insightRecurringTitle,
        body: tr(t.overview.insightRecurringBody, {
          total: String(p.total),
          names: String(p.names),
        }),
      };
    if (kind === "best_month")
      return {
        title: t.overview.insightBestMonthTitle,
        body: tr(t.overview.insightBestMonthBody, {
          month: String(p.month),
          net: String(p.net),
        }),
      };
    return null;
  }

  function insightSeverityClass(severity: string): string {
    if (severity === "bad" || severity === "warn") return "warn";
    if (severity === "good") return "good";
    return "info";
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

      {insights.length > 0 && (
        <section className="panel alerts-panel insights-panel">
          <h2>{t.overview.insights}</h2>
          {insights.map((insight, i) => {
            const content = insightContent(insight);
            if (!content) return null;
            return (
              <div key={i} className={`insight-card alert ${insightSeverityClass(insight.severity)}`}>
                <strong className="insight-title">{content.title}</strong>
                <p className="insight-body">{content.body}</p>
                {insight.link && (
                  <Link to={insight.link} className="insight-link">
                    {t.overview.insightViewTx}
                  </Link>
                )}
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
          </ul>
        </section>
      )}

      {hasData && display.transfer_summary &&
        (display.transfer_summary.internal_volume > 0 || display.transfer_summary.pending_count > 0) && (
        <section className="panel transfers-panel">
          <h2>{t.overview.transfersTitle}</h2>
          <p className="muted transfers-intro">{t.overview.transfersIntro}</p>
          <ul>
            {display.transfer_summary.internal_volume > 0 && (
              <li>
                {tr(t.overview.transfersInternal, {
                  amount: formatKr(display.transfer_summary.internal_volume),
                  count: String(display.transfer_summary.internal_count),
                })}
              </li>
            )}
            {display.transfer_summary.pending_count > 0 && (
              <li>
                <Link to="/transactions?transfers=review">
                  {tr(t.overview.transfersPending, {
                    amount: formatKr(display.transfer_summary.pending_volume),
                    count: String(display.transfer_summary.pending_count),
                  })}
                </Link>
              </li>
            )}
          </ul>
          <p>
            <Link to="/transactions?transfers=1">{t.overview.transfersReviewLink}</Link>
          </p>
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

          {pieData.length > 0 && (
            <section className="panel chart-panel chart-wide">
              <div className="chart-panel-head">
                <h2>{t.overview.chartCategory}</h2>
                <label className="category-month-picker">
                  <span className="label">{t.overview.chartCategoryMonth}</span>
                  <select
                    value={categoryMonth}
                    onChange={(e) => setCategoryMonth(e.target.value)}
                  >
                    <option value="">{t.overview.chartCategoryAll} ({months} {t.overview.months})</option>
                    {[...cashflow].reverse().map((m) => (
                      <option key={m.month} value={m.month}>
                        {m.month}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="category-breakdown">
                <ResponsiveContainer width="100%" height={280}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      dataKey="total"
                      nameKey="label"
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={100}
                      paddingAngle={1}
                    >
                      {pieData.map((_, i) => (
                        <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(v: number, _n, item) => {
                        const pct = (item?.payload as { pct?: number })?.pct;
                        return [`${formatKr(v)}${pct != null ? ` (${pct}%)` : ""}`, ""];
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <ul className="category-legend">
                  <li className="category-legend-total">
                    <span>{t.overview.chartCategoryTotal}</span>
                    <strong>{formatKr(categoryTotal)}</strong>
                  </li>
                  {pieData.map((b, i) => {
                    const txParams = new URLSearchParams({ category: b.category, sort: "amount_desc" });
                    if (categoryMonth) txParams.set("month", categoryMonth);
                    return (
                      <li key={b.category}>
                        <Link
                          to={`/transactions?${txParams}`}
                          className="category-legend-link"
                          title={t.overview.chartCategoryDrilldown}
                        >
                          <span
                            className="swatch"
                            style={{ background: CHART_COLORS[i % CHART_COLORS.length] }}
                          />
                          <span className="cat-name">{b.label}</span>
                          <span className="cat-pct">{b.pct}%</span>
                          <strong>{formatKr(b.total)}</strong>
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </div>
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
