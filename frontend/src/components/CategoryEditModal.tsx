import { useState, type FormEvent } from "react";
import { formatKr, type Transaction } from "../api";
import { useI18n } from "../i18n";

type Props = {
  tx?: Transaction;
  /** Bulk: all txs in a merchant group */
  txs?: Transaction[];
  matchText?: string;
  categories: string[];
  onClose: () => void;
  onSave: (category: string, remember: boolean, matchText?: string) => Promise<void>;
};

export default function CategoryEditModal({
  tx,
  txs,
  matchText,
  categories,
  onClose,
  onSave,
}: Props) {
  const { t, cat } = useI18n();
  const bulk = Boolean(txs && txs.length > 0);
  const primary = tx ?? txs![0];
  const [category, setCategory] = useState(primary.category === "Unclear" ? "Other" : primary.category);
  const [remember, setRemember] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSave(category, remember, matchText);
    } catch (err) {
      setError(String(err));
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <h2>{bulk ? t.modal.bulkTitle : t.modal.title}</h2>
        <p className="muted">
          {bulk ? (
            <>
              {t.modal.bulkHint.replace("{count}", String(txs!.length)).replace("{match}", matchText || "")}
            </>
          ) : (
            <>
              {primary.tx_date} · {formatKr(primary.amount)}
              <br />
              {primary.raw_description}
            </>
          )}
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
