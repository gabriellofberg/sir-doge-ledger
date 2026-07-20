import { useState, type FormEvent } from "react";
import { formatKr, type Transaction } from "../api";

type Props = {
  tx: Transaction;
  categories: string[];
  onClose: () => void;
  onSave: (category: string, remember: boolean) => Promise<void>;
};

export default function CategoryEditModal({ tx, categories, onClose, onSave }: Props) {
  const [category, setCategory] = useState(tx.category === "Unclear" ? "Other" : tx.category);
  const [remember, setRemember] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSave(category, remember);
    } catch (err) {
      setError(String(err));
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <form
        className="modal"
        onClick={(e) => e.stopPropagation()}
        onSubmit={submit}
      >
        <h2>Re-categorize</h2>
        <p className="muted">
          {tx.tx_date} · {formatKr(tx.amount)}
          <br />
          {tx.raw_description}
        </p>
        <label>
          Category
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            {categories
              .filter((c) => c !== "Unclear")
              .map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
          </select>
        </label>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={remember}
            onChange={(e) => setRemember(e.target.checked)}
          />
          <span>
            Remember for similar purchases
            <small>
              {remember
                ? "Always use this category when the merchant text matches (learned rule)."
                : "Only change this one purchase."}
            </small>
          </span>
        </label>
        {error && <p className="error">{error}</p>}
        <div className="modal-actions">
          <button type="button" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button type="submit" className="primary" disabled={busy}>
            Save
          </button>
        </div>
      </form>
    </div>
  );
}
