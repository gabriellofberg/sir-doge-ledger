import { useEffect, useState } from "react";
import { moneyApi } from "../api";
import { useCategories } from "../categories";
import { useI18n } from "../i18n";

type Rule = { id: number; match_text: string; category: string; enabled: number };

export default function RulesPage() {
  const { t, cat } = useI18n();
  const { slugs } = useCategories();
  const [rules, setRules] = useState<Rule[]>([]);
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);

  const load = () =>
    moneyApi.rules().then((r) => {
      const list = r.rules as Rule[];
      setRules(list);
      setDrafts(Object.fromEntries(list.map((x) => [x.id, x.match_text])));
    });

  useEffect(() => {
    load();
  }, []);

  async function saveMatch(rule: Rule) {
    const next = (drafts[rule.id] ?? rule.match_text).trim();
    if (!next || next === rule.match_text) return;
    setError(null);
    try {
      await moneyApi.updateRule(rule.id, { match_text: next });
      await load();
    } catch (err) {
      setError(String(err));
      setDrafts((d) => ({ ...d, [rule.id]: rule.match_text }));
    }
  }

  return (
    <div className="stack">
      <h1>{t.rules.title}</h1>
      <p className="lede">{t.rules.lede}</p>
      {error && <p className="error">{error}</p>}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>{t.rules.match}</th>
              <th>{t.rules.category}</th>
              <th>{t.rules.on}</th>
            </tr>
          </thead>
          <tbody>
            {rules.map((r) => (
              <tr key={r.id}>
                <td>
                  <input
                    value={drafts[r.id] ?? r.match_text}
                    onChange={(e) => setDrafts((d) => ({ ...d, [r.id]: e.target.value }))}
                    onBlur={() => saveMatch(r)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.currentTarget.blur();
                      }
                    }}
                    aria-label={t.rules.match}
                  />
                </td>
                <td>
                  <select
                    value={r.category}
                    onChange={(e) =>
                      moneyApi.updateRule(r.id, { category: e.target.value }).then(load)
                    }
                  >
                    {slugs.map((c) => (
                      <option key={c} value={c}>
                        {cat(c)}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <input
                    type="checkbox"
                    checked={Boolean(r.enabled)}
                    onChange={(e) =>
                      moneyApi.updateRule(r.id, { enabled: e.target.checked }).then(load)
                    }
                  />
                </td>
              </tr>
            ))}
            {rules.length === 0 && (
              <tr>
                <td colSpan={3} className="table-empty">
                  {t.rules.empty}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
