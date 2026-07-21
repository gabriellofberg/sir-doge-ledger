import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { formatKr, moneyApi } from "../api";
import { useI18n, tr } from "../i18n";

type Preview = Awaited<ReturnType<typeof moneyApi.preview>>;

export default function ImportPage() {
  const nav = useNavigate();
  const { t } = useI18n();
  const [preview, setPreview] = useState<Preview | null>(null);
  const [mapping, setMapping] = useState({
    date: "",
    amount: "",
    description: "",
    date_format: "auto",
    amount_decimal: ",",
    delimiter: undefined as string | undefined,
  });
  const [deleteUpload, setDeleteUpload] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fieldLabel = {
    date: t.import.date,
    amount: t.import.amount,
    description: t.import.description,
  };

  async function onFile(file: File | null) {
    if (!file) return;
    setError(null);
    setMessage(null);
    setBusy(true);
    try {
      const p = await moneyApi.preview(file);
      setPreview(p);
      setMapping((m) => ({
        ...m,
        date: p.guessed_mapping.date || p.headers[0] || "",
        amount: p.guessed_mapping.amount || p.headers[1] || "",
        description: p.guessed_mapping.description || p.headers[2] || "",
        amount_decimal: p.guessed_amount_decimal || m.amount_decimal || ",",
        delimiter: p.delimiter === "xlsx" ? undefined : p.delimiter,
      }));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function doImport() {
    if (!preview) return;
    setBusy(true);
    setError(null);
    try {
      const result = await moneyApi.importFile(
        preview.import_session_id,
        preview.filename || "import.csv",
        { ...mapping },
        deleteUpload,
      );
      const skipped =
        result.skipped_count > 0
          ? tr(t.import.skipped, { count: result.skipped_count })
          : "";
      setMessage(
        tr(t.import.imported, {
          count: result.row_count,
          skipped,
          unclear: result.unclear_count,
        }),
      );
      setTimeout(
        () => nav(result.unclear_count ? "/transactions?review=1" : "/"),
        900,
      );
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  const parsedPreview = preview?.parsed_preview ?? [];

  return (
    <div className="stack">
      <h1>{t.import.title}</h1>
      <p className="lede">{t.import.lede}</p>

      <label className="file-pick">
        <span>{t.import.chooseFile}</span>
        <input
          type="file"
          accept=".csv,.txt,.xlsx,.xlsm"
          disabled={busy}
          onChange={(e) => onFile(e.target.files?.[0] ?? null)}
        />
      </label>

      <button
        type="button"
        className="secondary"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            const r = await moneyApi.importSample();
            setMessage(tr(t.import.sampleOk, { count: r.row_count }));
            nav("/");
          } catch (e) {
            setError(String(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        {t.import.loadSample}
      </button>

      {error && <p className="error">{error}</p>}
      {message && <p className="ok">{message}</p>}

      {preview && (
        <>
          <section className="panel">
            <h2>{t.import.mapping}</h2>
            <div className="form-grid">
              {(["date", "amount", "description"] as const).map((field) => (
                <label key={field}>
                  {fieldLabel[field]}
                  <select
                    value={mapping[field]}
                    onChange={(e) => setMapping({ ...mapping, [field]: e.target.value })}
                  >
                    {preview.headers.map((h) => (
                      <option key={h} value={h}>
                        {h}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
              <label>
                {t.import.amountDecimal}
                <select
                  value={mapping.amount_decimal}
                  onChange={(e) => setMapping({ ...mapping, amount_decimal: e.target.value })}
                >
                  <option value=",">{t.import.comma}</option>
                  <option value=".">{t.import.dot}</option>
                </select>
              </label>
            </div>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={deleteUpload}
                onChange={(e) => setDeleteUpload(e.target.checked)}
              />
              <span>
                {t.import.deleteUpload}
                <small>{t.import.deleteHint}</small>
              </span>
            </label>
            <button type="button" className="primary" disabled={busy} onClick={doImport}>
              {t.import.importBtn}
            </button>
          </section>

          {parsedPreview.length > 0 && (
            <section className="panel">
              <h2>{t.import.parsedPreview}</h2>
              <p className="muted">{t.import.parsedPreviewHint}</p>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>{t.import.date}</th>
                      <th>{t.import.description}</th>
                      <th>{t.import.amount}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {parsedPreview.map((row, i) => (
                      <tr key={i}>
                        <td>{row.tx_date}</td>
                        <td>{row.description}</td>
                        <td className={row.amount < 0 ? "neg" : "pos"}>{formatKr(row.amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          <section>
            <h2>{t.import.preview}</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    {preview.headers.map((h) => (
                      <th key={h}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.preview_rows.slice(0, 8).map((row, i) => (
                    <tr key={i}>
                      {preview.headers.map((h) => (
                        <td key={h}>{row[h]}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
