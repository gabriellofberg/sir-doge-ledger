import { useEffect, useMemo, useState } from "react";
import EmptyState from "../components/EmptyState";
import { formatKr, moneyApi, type RecurringGroup, type Transaction } from "../api";
import { useI18n, tr } from "../i18n";

const HIDDEN = "ignore";

export default function RecurringPage() {
  const { t, cat } = useI18n();
  const [groups, setGroups] = useState<RecurringGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [related, setRelated] = useState<Transaction[]>([]);
  const [relatedLoading, setRelatedLoading] = useState(false);

  const visible = useMemo(
    () => groups.filter((g) => g.decision !== HIDDEN),
    [groups],
  );

  const selected = visible.find((g) => g.id === selectedId) ?? visible[0] ?? null;
  const selectedIndex = selected ? visible.findIndex((g) => g.id === selected.id) : -1;

  const load = () => {
    setLoading(true);
    return moneyApi
      .recurring()
      .then((r) => {
        setGroups(r.groups);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (!selected) {
      setSelectedId(null);
      setRelated([]);
      return;
    }
    if (selectedId !== selected.id) {
      setSelectedId(selected.id);
    }
  }, [selected, selectedId]);

  useEffect(() => {
    if (!selected) {
      setRelated([]);
      return;
    }
    let cancelled = false;
    setRelatedLoading(true);
    moneyApi
      .transactions({ search: selected.normalized_merchant })
      .then((r) => {
        if (cancelled) return;
        const near = Math.abs(selected.typical_amount);
        const matched = r.transactions
          .filter((tx) => Math.abs(Math.abs(tx.amount) - near) / Math.max(near, 1) < 0.35)
          .slice(0, 12);
        setRelated(matched.length ? matched : r.transactions.slice(0, 12));
      })
      .finally(() => {
        if (!cancelled) setRelatedLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selected?.id, selected?.normalized_merchant, selected?.typical_amount]);

  async function patch(id: number, body: Partial<RecurringGroup>) {
    const updated = await moneyApi.updateRecurring(id, body);
    setGroups((prev) => {
      const next = prev.map((g) => (g.id === id ? { ...g, ...updated } : g));
      if (body.decision === HIDDEN) {
        const remaining = next.filter((g) => g.decision !== HIDDEN);
        const oldVisible = prev.filter((g) => g.decision !== HIDDEN);
        const idx = oldVisible.findIndex((g) => g.id === id);
        const fallback = remaining[Math.min(Math.max(idx, 0), remaining.length - 1)] ?? null;
        setSelectedId(fallback?.id ?? null);
      }
      return next;
    });
  }

  function go(delta: number) {
    if (selectedIndex < 0) return;
    const next = visible[selectedIndex + delta];
    if (next) setSelectedId(next.id);
  }

  const choiceLabel = { yes: t.recurring.yes, no: t.recurring.no, unsure: t.recurring.unsure };
  const decisionLabel: Record<string, string> = {
    pending: t.recurring.pending,
    keep: t.recurring.keep,
    cancel: t.recurring.cancelWant,
    unsure: t.recurring.notSure,
  };

  return (
    <div className="stack recurring-page">
      <h1>{t.recurring.title}</h1>
      <p className="lede">{t.recurring.lede}</p>

      {loading && <p className="muted page-loading">{t.recurring.loading}</p>}

      {!loading && visible.length > 0 && selected && (
        <div className="recurring-layout">
          <aside className="recurring-nav panel" aria-label={t.recurring.listLabel}>
            <div className="recurring-nav-head">
              <span className="label">{t.recurring.listLabel}</span>
              <strong>
                {tr(t.recurring.progress, {
                  current: String(selectedIndex + 1),
                  total: String(visible.length),
                })}
              </strong>
            </div>
            <ul className="recurring-nav-list">
              {visible.map((g) => (
                <li key={g.id}>
                  <button
                    type="button"
                    className={g.id === selected.id ? "active" : ""}
                    onClick={() => setSelectedId(g.id)}
                  >
                    <span className="nav-name">{g.name}</span>
                    <span className="nav-meta">
                      <em>{formatKr(g.yearly_cost)}/{t.recurring.yearShort}</em>
                      <span className={`status-dot decision-${g.decision}`}>
                        {decisionLabel[g.decision] ?? g.decision}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </aside>

          <article className={`recurring-detail panel decision-${selected.decision}`}>
            <header className="recurring-detail-head">
              <div>
                <p className="muted recurring-step">
                  {tr(t.recurring.progress, {
                    current: String(selectedIndex + 1),
                    total: String(visible.length),
                  })}
                </p>
                <h2>{selected.name}</h2>
                <p className="muted merchant-key">{selected.normalized_merchant}</p>
              </div>
              <div className="recurring-pager">
                <button type="button" onClick={() => go(-1)} disabled={selectedIndex <= 0}>
                  {t.recurring.prev}
                </button>
                <button
                  type="button"
                  onClick={() => go(1)}
                  disabled={selectedIndex >= visible.length - 1}
                >
                  {t.recurring.next}
                </button>
              </div>
            </header>

            <div className="recurring-stats">
              <div>
                <span className="label">{t.recurring.cadence}</span>
                <strong className="pill inline-pill">{selected.cadence}</strong>
              </div>
              <div>
                <span className="label">{t.recurring.perCharge}</span>
                <strong>{formatKr(selected.typical_amount)}</strong>
              </div>
              <div className="yearly">
                <span className="label">{t.recurring.perYear}</span>
                <strong>{formatKr(selected.yearly_cost)}</strong>
              </div>
              <div>
                <span className="label">{t.recurring.fiveYears}</span>
                <strong>{formatKr(selected.yearly_cost * 5)}</strong>
              </div>
            </div>

            <p className="muted">
              {tr(t.recurring.seen, {
                count: selected.occurrence_count,
                last: selected.last_seen,
              })}
            </p>

            <label className="field">
              {t.recurring.cancelBy}
              <input
                type="date"
                value={selected.cancel_by ?? ""}
                onChange={(e) => patch(selected.id, { cancel_by: e.target.value || null })}
              />
            </label>

            <section className="recurring-questions">
              <fieldset>
                <legend>{t.recurring.stillUse}</legend>
                <div className="choice-row">
                  {(["yes", "no", "unsure"] as const).map((v) => (
                    <button
                      key={v}
                      type="button"
                      className={selected.use_it === v ? "selected" : ""}
                      onClick={() => patch(selected.id, { use_it: v })}
                    >
                      {choiceLabel[v]}
                    </button>
                  ))}
                </div>
              </fieldset>

              <fieldset>
                <legend>{tr(t.recurring.worthIt, { amount: formatKr(selected.yearly_cost) })}</legend>
                <div className="choice-row">
                  {(["yes", "no", "unsure"] as const).map((v) => (
                    <button
                      key={v}
                      type="button"
                      className={selected.worth_it === v ? "selected" : ""}
                      onClick={() => patch(selected.id, { worth_it: v })}
                    >
                      {choiceLabel[v]}
                    </button>
                  ))}
                </div>
              </fieldset>
            </section>

            <div className="recurring-actions">
              <div className="choice-row decisions">
                {(
                  [
                    ["keep", t.recurring.keep],
                    ["cancel", t.recurring.cancelWant],
                    ["unsure", t.recurring.notSure],
                  ] as const
                ).map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    className={selected.decision === value ? "primary selected" : ""}
                    onClick={() => patch(selected.id, { decision: value })}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <button
                type="button"
                className="dismiss-btn"
                onClick={() => patch(selected.id, { decision: HIDDEN })}
              >
                {t.recurring.notSub}
              </button>
            </div>

            <section className="related-txs">
              <h3>{t.recurring.relatedTitle}</h3>
              <p className="muted related-hint">{t.recurring.relatedHint}</p>
              {relatedLoading && <p className="muted">{t.recurring.relatedLoading}</p>}
              {!relatedLoading && related.length === 0 && (
                <p className="muted">{t.recurring.relatedEmpty}</p>
              )}
              {!relatedLoading && related.length > 0 && (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>{t.transactions.date}</th>
                        <th>{t.transactions.description}</th>
                        <th>{t.transactions.amount}</th>
                        <th>{t.transactions.category}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {related.map((tx) => (
                        <tr key={tx.id}>
                          <td>{tx.tx_date}</td>
                          <td>{tx.raw_description}</td>
                          <td>{formatKr(tx.amount)}</td>
                          <td>{cat(tx.category)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </article>
        </div>
      )}

      {!loading && visible.length === 0 && (
        <EmptyState
          title={t.recurring.emptyTitle}
          description={t.recurring.emptyHint}
          actionLabel={t.recurring.emptyCta}
          actionTo="/import"
        />
      )}
    </div>
  );
}
