import { useEffect, useState } from "react";
import { moneyApi } from "../api";
import { useI18n } from "../i18n";
import { CATEGORIES } from "../categories";

type Rule = { id: number; match_text: string; category: string; enabled: number };

export default function RulesPage() {
  const { t, cat } = useI18n();
  const [rules, setRules] = useState<Rule[]>([]);

  const load = () => moneyApi.rules().then((r) => setRules(r.rules as Rule[]));

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="stack">
      <h1>{t.rules.title}</h1>
      <p className="lede">{t.rules.lede}</p>
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
                <td>{r.match_text}</td>
                <td>
                  <select
                    value={r.category}
                    onChange={(e) =>
                      moneyApi.updateRule(r.id, { category: e.target.value }).then(load)
                    }
                  >
                    {CATEGORIES.map((c) => (
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
          </tbody>
        </table>
        {rules.length === 0 && <p className="muted table-empty">{t.rules.empty}</p>}
      </div>
    </div>
  );
}
