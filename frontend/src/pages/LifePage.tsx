import { useEffect, useState, type FormEvent } from "react";
import EmptyState from "../components/EmptyState";
import { formatKr, lifeApi, type LifeItem } from "../api";
import { useI18n } from "../i18n";

const KIND_KEYS = ["rent", "warranty", "contract", "document", "reminder", "other"] as const;

export default function LifePage() {
  const { t } = useI18n();
  const [items, setItems] = useState<LifeItem[]>([]);
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState("reminder");
  const [due, setDue] = useState("");
  const [amount, setAmount] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    return lifeApi
      .list()
      .then((r) => setItems(r.items))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  async function add(e: FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    await lifeApi.create({
      title: title.trim(),
      kind,
      due_date: due || null,
      amount: amount ? Number(amount) : null,
      notes: notes || null,
    });
    setTitle("");
    setDue("");
    setAmount("");
    setNotes("");
    await load();
  }

  const kindLabel = (k: string) =>
    t.life.kinds[k as keyof typeof t.life.kinds] ?? k;

  const ghostItems = [
    { title: t.life.ghostLease, kind: "rent", due: "2026-12-01" },
    { title: t.life.ghostWarranty, kind: "warranty", due: "2027-06-15" },
  ];

  return (
    <div className="stack">
      <h1>{t.life.title}</h1>
      <p className="lede">{t.life.lede}</p>
      <a className="empty-state-cta" href="/api/life/export.ics" download="sir-doge-life.ics">
        {t.life.calendar}
      </a>

      <form className="panel form-grid" onSubmit={add}>
        <label>
          {t.life.formTitle}
          <input value={title} onChange={(e) => setTitle(e.target.value)} required />
        </label>
        <label>
          {t.life.kind}
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            {KIND_KEYS.map((k) => (
              <option key={k} value={k}>
                {kindLabel(k)}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t.life.due}
          <input type="date" value={due} onChange={(e) => setDue(e.target.value)} />
        </label>
        <label>
          {t.life.amount}
          <input
            type="number"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
        </label>
        <label className="full">
          {t.life.notes}
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} />
        </label>
        <button type="submit" className="primary">
          {t.life.add}
        </button>
      </form>

      {loading && <p className="muted page-loading">{t.life.loading}</p>}

      {!loading && items.length > 0 && (
        <ul className="life-list">
          {items.map((item) => (
            <li key={item.id}>
              <div>
                <strong>{item.title}</strong>
                <span className="pill">{kindLabel(item.kind)}</span>
                <p className="muted">
                  {item.due_date
                    ? `${t.life.duePrefix} ${item.due_date}`
                    : t.life.noDue}
                  {item.amount != null ? ` · ${formatKr(item.amount)}` : ""}
                </p>
                {item.notes && <p>{item.notes}</p>}
              </div>
              <button type="button" onClick={() => lifeApi.remove(item.id).then(load)}>
                {t.common.delete}
              </button>
            </li>
          ))}
        </ul>
      )}

      {!loading && items.length === 0 && (
        <>
          <EmptyState title={t.life.emptyTitle} description={t.life.emptyHint} />
          <ul className="life-list ghost-list" aria-hidden>
            {ghostItems.map((item) => (
              <li key={item.title} className="ghost-card">
                <div>
                  <strong>{item.title}</strong>
                  <span className="pill">{kindLabel(item.kind)}</span>
                  <p className="muted">
                    {t.life.duePrefix} {item.due} · {t.life.exampleRow}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
