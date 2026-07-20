import { useEffect, useState } from "react";
import EmptyState from "../components/EmptyState";
import { formatKr, moneyApi, type RecurringGroup } from "../api";
import { useI18n, tr } from "../i18n";

export default function RecurringPage() {
  const { t } = useI18n();
  const [groups, setGroups] = useState<RecurringGroup[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    return moneyApi
      .recurring()
      .then((r) => setGroups(r.groups))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  async function patch(id: number, body: Partial<RecurringGroup>) {
    await moneyApi.updateRecurring(id, body);
    await load();
  }

  const choiceLabel = { yes: t.recurring.yes, no: t.recurring.no, unsure: t.recurring.unsure };
  const ghostCards = [
    { name: t.recurring.ghostStream, cadence: t.recurring.monthly, yearly: 1188 },
    { name: t.recurring.ghostGym, cadence: t.recurring.monthly, yearly: 4200 },
  ];

  return (
    <div className="stack">
      <h1>{t.recurring.title}</h1>
      <p className="lede">{t.recurring.lede}</p>

      {loading && <p className="muted page-loading">{t.recurring.loading}</p>}

      {!loading && groups.length > 0 && (
        <div className="card-grid">
          {groups.map((g) => (
            <article key={g.id} className={`review-card decision-${g.decision}`}>
              <header>
                <h2>{g.name}</h2>
                <span className="pill">{g.cadence}</span>
              </header>
              <div className="cost-block">
                <div>
                  <span className="label">{t.recurring.perCharge}</span>
                  <strong>{formatKr(g.typical_amount)}</strong>
                </div>
                <div className="yearly">
                  <span className="label">{t.recurring.perYear}</span>
                  <strong>{formatKr(g.yearly_cost)}</strong>
                </div>
                <div>
                  <span className="label">{t.recurring.fiveYears}</span>
                  <strong>{formatKr(g.yearly_cost * 5)}</strong>
                </div>
              </div>
              <p className="muted">
                {tr(t.recurring.seen, { count: g.occurrence_count, last: g.last_seen })}
              </p>
              <label className="field compact">
                {t.recurring.cancelBy}
                <input
                  type="date"
                  value={g.cancel_by ?? ""}
                  onChange={(e) => patch(g.id, { cancel_by: e.target.value || null })}
                />
              </label>

              <fieldset>
                <legend>{t.recurring.stillUse}</legend>
                <div className="choice-row">
                  {(["yes", "no", "unsure"] as const).map((v) => (
                    <button
                      key={v}
                      type="button"
                      className={g.use_it === v ? "selected" : ""}
                      onClick={() => patch(g.id, { use_it: v })}
                    >
                      {choiceLabel[v]}
                    </button>
                  ))}
                </div>
              </fieldset>

              <fieldset>
                <legend>{tr(t.recurring.worthIt, { amount: formatKr(g.yearly_cost) })}</legend>
                <div className="choice-row">
                  {(["yes", "no", "unsure"] as const).map((v) => (
                    <button
                      key={v}
                      type="button"
                      className={g.worth_it === v ? "selected" : ""}
                      onClick={() => patch(g.id, { worth_it: v })}
                    >
                      {choiceLabel[v]}
                    </button>
                  ))}
                </div>
              </fieldset>

              <div className="choice-row decisions">
                {(
                  [
                    ["keep", t.recurring.keep],
                    ["cancel", t.recurring.cancelWant],
                    ["unsure", t.recurring.notSure],
                    ["ignore", t.recurring.notSub],
                  ] as const
                ).map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    className={g.decision === value ? "primary selected" : ""}
                    onClick={() => patch(g.id, { decision: value })}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </article>
          ))}
        </div>
      )}

      {!loading && groups.length === 0 && (
        <>
          <EmptyState
            title={t.recurring.emptyTitle}
            description={t.recurring.emptyHint}
            actionLabel={t.recurring.emptyCta}
            actionTo="/import"
          />
          <div className="card-grid ghost-grid" aria-hidden>
            {ghostCards.map((g) => (
              <article key={g.name} className="review-card ghost-card">
                <header>
                  <h2>{g.name}</h2>
                  <span className="pill">{g.cadence}</span>
                </header>
                <div className="cost-block">
                  <div>
                    <span className="label">{t.recurring.perYear}</span>
                    <strong>{formatKr(g.yearly)}</strong>
                  </div>
                </div>
                <p className="muted">{t.recurring.example}</p>
              </article>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
