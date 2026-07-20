import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { moneyApi } from "../api";

type Preview = Awaited<ReturnType<typeof moneyApi.preview>>;

export default function ImportPage() {
  const nav = useNavigate();
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
        result.skipped_count > 0 ? ` (${result.skipped_count} duplicates skipped)` : "";
      setMessage(`Imported ${result.row_count} rows${skipped}. ${result.unclear_count} need review.`);
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

  return (
    <div className="stack">
      <h1>Import bank export</h1>
      <p className="lede">
        Export ~6 months from your bank as CSV or Excel. File is parsed locally — never uploaded to
        the internet.
      </p>

      <label className="file-pick">
        <span>Choose file</span>
        <input
          type="file"
          accept=".csv,.txt,.xlsx,.xlsm"
          disabled={busy}
          onChange={(e) => onFile(e.target.files?.[0] ?? null)}
        />
      </label>

      {error && <p className="error">{error}</p>}
      {message && <p className="ok">{message}</p>}

      {preview && (
        <>
          <section className="panel">
            <h2>Column mapping</h2>
            <div className="form-grid">
              {(["date", "amount", "description"] as const).map((field) => (
                <label key={field}>
                  {field}
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
                Amount decimal
                <select
                  value={mapping.amount_decimal}
                  onChange={(e) => setMapping({ ...mapping, amount_decimal: e.target.value })}
                >
                  <option value=",">Comma (1.234,56)</option>
                  <option value=".">Dot (1,234.56)</option>
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
                Delete bank file from disk after import
                <small>Recommended — removes the raw export from local storage</small>
              </span>
            </label>
            <button type="button" className="primary" disabled={busy} onClick={doImport}>
              Import & categorize
            </button>
          </section>

          <section>
            <h2>Preview</h2>
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
