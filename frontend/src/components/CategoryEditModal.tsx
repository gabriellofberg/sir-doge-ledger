import { useState, type FormEvent } from "react";
import { formatKr, type Transaction } from "../api";
import { useI18n } from "../i18n";

type Props = {
  tx: Transaction;
  categories: string[];
  onClose: () => void;
  onSave: (category: string, remember: boolean) => Promise<void>;
};

export default function CategoryEditModal({ tx, categories, onClose, onSave }: Props) {
  const { t, cat } = useI18n();
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
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <h2>{t.modal.title}</h2>
        <p className="muted">
          {tx.tx_date} · {formatKr(tx.amount)}
          <br />
          {tx.raw_description}
        </p>
        <label>
          {t.modal.category}
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            {categories
              .filter((c) => c !== "Unclear")
              .map((c) => (
                <option key={c} value={c}>
                  {cat(c)}
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
            {t.modal.remember}
            <small>{remember ? t.modal.rememberOn : t.modal.rememberOff}</small>
          </span>
        </label>
        {error && <p className="error">{error}</p>}
        <div className="modal-actions">
          <button type="button" onClick={onClose} disabled={busy}>
            {t.common.cancel}
          </button>
          <button type="submit" className="primary" disabled={busy}>
            {t.common.save}
          </button>
        </div>
      </form>
    </div>
  );
}
