import { useEffect, useState } from "react";
import { formatKr, moneyApi, type RecurringGroup } from "../api";

export default function RecurringPage() {
  const [groups, setGroups] = useState<RecurringGroup[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = () =>
    moneyApi
      .recurring()
      .then((r) => setGroups(r.groups))
      .catch((e) => setError(String(e)));

  useEffect(() => {
    load();
  }, []);

  async function patch(id: number, body: Partial<RecurringGroup>) {
    await moneyApi.updateRecurring(id, body);
    await load();
  }

  return (
    <div className="stack">
      <h1>Recurring charges</h1>
      <p className="lede">
        Small monthly amounts are easy to ignore. Here they are shown as yearly cost — then you
        decide if you still use them and if they are worth it.
      </p>
      {error && <p className="error">{error}</p>}

      <div className="card-grid">
        {groups.map((g) => (
          <article key={g.id} className={`review-card decision-${g.decision}`}>
            <header>
              <h2>{g.name}</h2>
              <span className="pill">{g.cadence}</span>
            </header>
            <div className="cost-block">
              <div>
                <span className="label">Per charge</span>
                <strong>{formatKr(g.typical_amount)}</strong>
              </div>
              <div className="yearly">
                <span className="label">Per year</span>
                <strong>{formatKr(g.yearly_cost)}</strong>
              </div>
              <div>
                <span className="label">5 years</span>
                <strong>{formatKr(g.yearly_cost * 5)}</strong>
              </div>
            </div>
            <p className="muted">
              Seen {g.occurrence_count}× · last {g.last_seen}
            </p>

            <fieldset>
              <legend>Do I still use this?</legend>
              <div className="choice-row">
                {(["yes", "no", "unsure"] as const).map((v) => (
                  <button
                    key={v}
                    type="button"
                    className={g.use_it === v ? "selected" : ""}
                    onClick={() => patch(g.id, { use_it: v })}
                  >
                    {v}
                  </button>
                ))}
              </div>
            </fieldset>

            <fieldset>
              <legend>Worth {formatKr(g.yearly_cost)} / year?</legend>
              <div className="choice-row">
                {(["yes", "no", "unsure"] as const).map((v) => (
                  <button
                    key={v}
                    type="button"
                    className={g.worth_it === v ? "selected" : ""}
                    onClick={() => patch(g.id, { worth_it: v })}
                  >
                    {v}
                  </button>
                ))}
              </div>
            </fieldset>

            <div className="choice-row decisions">
              {(
                [
                  ["keep", "Keep"],
                  ["cancel", "Want to cancel"],
                  ["unsure", "Not sure"],
                  ["ignore", "Not a subscription"],
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
      {groups.length === 0 && (
        <p className="muted">No recurring groups yet — import ~6 months of transactions first.</p>
      )}
    </div>
  );
}
