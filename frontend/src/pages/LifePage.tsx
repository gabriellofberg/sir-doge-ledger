import { useEffect, useState, type FormEvent } from "react";
import { formatKr, lifeApi, type LifeItem } from "../api";

const KINDS = ["rent", "warranty", "contract", "document", "reminder", "other"];

export default function LifePage() {
  const [items, setItems] = useState<LifeItem[]>([]);
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState("reminder");
  const [due, setDue] = useState("");
  const [amount, setAmount] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = () =>
    lifeApi
      .list()
      .then((r) => setItems(r.items))
      .catch((e) => setError(String(e)));

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

  return (
    <div className="stack">
      <h1>Life admin</h1>
      <p className="lede">Rent, warranties, contracts, and expiry reminders — stored only locally.</p>
      {error && <p className="error">{error}</p>}

      <form className="panel form-grid" onSubmit={add}>
        <label>
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} required />
        </label>
        <label>
          Kind
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            {KINDS.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </label>
        <label>
          Due date
          <input type="date" value={due} onChange={(e) => setDue(e.target.value)} />
        </label>
        <label>
          Amount (optional)
          <input
            type="number"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
        </label>
        <label className="full">
          Notes
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} />
        </label>
        <button type="submit" className="primary">
          Add
        </button>
      </form>

      <ul className="life-list">
        {items.map((item) => (
          <li key={item.id}>
            <div>
              <strong>{item.title}</strong>
              <span className="pill">{item.kind}</span>
              <p className="muted">
                {item.due_date ? `Due ${item.due_date}` : "No due date"}
                {item.amount != null ? ` · ${formatKr(item.amount)}` : ""}
              </p>
              {item.notes && <p>{item.notes}</p>}
            </div>
            <button type="button" onClick={() => lifeApi.remove(item.id).then(load)}>
              Delete
            </button>
          </li>
        ))}
      </ul>
      {items.length === 0 && <p className="muted">Nothing saved yet.</p>}
    </div>
  );
}
