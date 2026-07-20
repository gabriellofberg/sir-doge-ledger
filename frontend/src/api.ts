const API = "/api";

export const CSRF_HEADER = "X-Sir-Doge";

export const MUTATION_HEADERS: Record<string, string> = {
  [CSRF_HEADER]: "1",
};

const defaultInit: RequestInit = {
  credentials: "include",
};

export async function bootstrapAuth(): Promise<void> {
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token");
  if (!token) return;
  try {
    await fetch(`${API}/auth?token=${encodeURIComponent(token)}`, {
      method: "POST",
      headers: MUTATION_HEADERS,
      credentials: "include",
    });
  } finally {
    params.delete("token");
    const clean = window.location.pathname + (params.toString() ? `?${params}` : "");
    window.history.replaceState({}, "", clean);
  }
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method || "GET").toUpperCase();
  const headers = new Headers(init?.headers);
  if (method !== "GET" && method !== "HEAD") {
    headers.set(CSRF_HEADER, "1");
  }
  const res = await fetch(path, { ...defaultInit, ...init, headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export type Transaction = {
  id: number;
  tx_date: string;
  amount: number;
  raw_description: string;
  normalized_merchant: string;
  category: string;
  category_source: string;
  confidence: number;
  needs_review: number;
};

export type RecurringGroup = {
  id: number;
  name: string;
  normalized_merchant: string;
  cadence: string;
  typical_amount: number;
  yearly_cost: number;
  occurrence_count: number;
  last_seen: string;
  decision: string;
  use_it: string | null;
  worth_it: string | null;
};

export type LifeItem = {
  id: number;
  title: string;
  kind: string;
  due_date: string | null;
  amount: number | null;
  notes: string | null;
};

export type MoneyStats = {
  transaction_count: number;
  unclear_count: number;
  pending_recurring: number;
  total_spent: number;
  total_income: number;
  net: number;
  transfer_volume: number;
  uncategorized_income_count: number;
  recurring_yearly_total: number;
};

export type CashflowMonth = {
  month: string;
  income: number;
  spent: number;
  net: number;
  transfer_volume: number;
  unclear_count: number;
};

export const moneyApi = {
  health: () => api<{ status: string; auth_required: boolean }>("/api/health"),
  stats: () => api<MoneyStats>("/api/money/stats"),
  completeness: () => api<MoneyStats>("/api/money/completeness"),
  categories: () => api<{ categories: string[] }>("/api/money/categories"),
  summary: () => api<{ by_category: Array<Record<string, number | string>> }>("/api/money/summary"),
  cashflow: (months = 12) => api<{ months: CashflowMonth[] }>(`/api/money/cashflow?months=${months}`),
  breakdown: (kind: "spent" | "income") =>
    api<{ categories: Array<{ category: string; total: number; tx_count: number }> }>(
      `/api/money/breakdown?kind=${kind}`,
    ),
  transactions: (params?: {
    needs_review?: boolean;
    income_review?: boolean;
    category?: string;
  }) => {
    const q = new URLSearchParams();
    if (params?.needs_review != null) q.set("needs_review", String(params.needs_review));
    if (params?.income_review != null) q.set("income_review", String(params.income_review));
    if (params?.category) q.set("category", params.category);
    const s = q.toString();
    return api<{ transactions: Transaction[] }>(`/api/money/transactions${s ? `?${s}` : ""}`);
  },
  preview: async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return api<{
      headers: string[];
      preview_rows: Record<string, string>[];
      delimiter: string;
      guessed_mapping: Record<string, string | null>;
      import_session_id: string;
      filename: string;
    }>("/api/money/preview", { method: "POST", body: fd });
  },
  importFile: async (
    importSessionId: string,
    filename: string,
    mapping: Record<string, string | null | undefined>,
    deleteUpload = true,
  ) => {
    const fd = new FormData();
    fd.append("import_session_id", importSessionId);
    fd.append("filename", filename);
    fd.append("mapping_json", JSON.stringify(mapping));
    fd.append("delete_upload", deleteUpload ? "true" : "false");
    return api<{ import_id: number; row_count: number; skipped_count: number; unclear_count: number }>(
      "/api/money/import",
      { method: "POST", body: fd },
    );
  },
  updateCategory: (id: number, category: string, remember: boolean, match_text?: string) =>
    api<Transaction>(`/api/money/transactions/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category, remember, match_text }),
    }),
  recurring: () => api<{ groups: RecurringGroup[] }>("/api/money/recurring"),
  updateRecurring: (id: number, body: Partial<RecurringGroup>) =>
    api<RecurringGroup>(`/api/money/recurring/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  rules: () => api<{ rules: Array<Record<string, unknown>> }>("/api/money/rules"),
};

export const lifeApi = {
  list: () => api<{ items: LifeItem[] }>("/api/life/items"),
  create: (body: Omit<LifeItem, "id">) =>
    api<LifeItem>("/api/life/items", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  remove: (id: number) => api<{ status: string }>(`/api/life/items/${id}`, { method: "DELETE" }),
};

async function download(path: string, filename: string): Promise<void> {
  const headers = new Headers();
  headers.set(CSRF_HEADER, "1");
  const res = await fetch(path, { credentials: "include", headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const dataApi = {
  downloadExport: (kind: "csv" | "json") =>
    download(
      kind === "csv" ? "/api/data/export/transactions.csv" : "/api/data/export/backup.json",
      kind === "csv" ? "sir-doge-transactions.csv" : "sir-doge-backup.json",
    ),
  wipeAll: (confirm: string) =>
    api<{ status: string; removed: Record<string, number> }>("/api/data/wipe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm }),
    }),
  logout: () =>
    api<{ status: string }>("/api/auth/logout", {
      method: "POST",
    }),
};

export function formatKr(n: number): string {
  return new Intl.NumberFormat("sv-SE", {
    style: "currency",
    currency: "SEK",
    maximumFractionDigits: 0,
  }).format(n);
}
