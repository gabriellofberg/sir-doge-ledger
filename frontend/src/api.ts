export const CSRF_HEADER = "X-Sir-Doge";

export const MUTATION_HEADERS: Record<string, string> = {
  [CSRF_HEADER]: "1",
};

const defaultInit: RequestInit = {
  credentials: "include",
};

export async function bootstrapAuth(): Promise<boolean> {
  return false;
}

export const authApi = {
  status: () => api<{ needs_setup: boolean; auth_required: boolean; dev_open: boolean }>("/api/auth/status"),
  checkSession: async () => {
    const res = await fetch("/api/money/stats", { credentials: "include" });
    return res.ok;
  },
  login: async (password: string) => {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { ...MUTATION_HEADERS, "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ password }),
    });
    return res.ok;
  },
  setup: async (password: string) => {
    const res = await fetch("/api/auth/setup", {
      method: "POST",
      headers: { ...MUTATION_HEADERS, "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ password }),
    });
    if (!res.ok) return null;
    return res.json() as Promise<{ recovery_key: string }>;
  },
  demo: async () => {
    const res = await fetch("/api/auth/demo", { method: "POST", headers: MUTATION_HEADERS, credentials: "include" });
    return res.ok;
  },
  recover: async (recovery_key: string, new_password: string) => {
    const res = await fetch("/api/auth/recover", {
      method: "POST",
      headers: { ...MUTATION_HEADERS, "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ recovery_key, new_password }),
    });
    return res.ok;
  },
};

export const settingsApi = {
  get: () => api<Record<string, unknown>>("/api/settings"),
  patch: (body: Record<string, unknown>) =>
    api<Record<string, unknown>>("/api/settings", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
};

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
  transfer_kind?: string | null;
  group_key?: string;
  tags?: string[];
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
  cancel_by: string | null;
};

export type Insight = {
  kind: string;
  severity: string;
  score: number;
  params: Record<string, unknown>;
  link?: string | null;
};

export type PriceAlert = {
  id: number;
  normalized_merchant: string;
  old_amount: number;
  new_amount: number;
  detected_at: string;
  pct_change: number;
  yearly_delta: number;
  name: string;
  cadence: string;
  typical_amount: number;
  recurring_group_id: number;
};

export type LifeItem = {
  id: number;
  title: string;
  kind: string;
  due_date: string | null;
  amount: number | null;
  notes: string | null;
};

export type TransferSummary = {
  internal_volume: number;
  internal_count: number;
  pending_count: number;
  pending_volume: number;
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
  transfer_summary?: TransferSummary;
};

export type CashflowMonth = {
  month: string;
  income: number;
  spent: number;
  net: number;
  transfer_volume: number;
  unclear_count: number;
};

export type CategoryInfo = {
  slug: string;
  name: string;
  is_system: number;
  sort_order?: number;
  tx_count?: number;
};

export type CategoryDeletePreview = {
  slug: string;
  tx_count: number;
  estimated_recategorizable: number;
  estimated_unclear: number;
  rules_count: number;
  budgets_count: number;
  is_system: boolean;
};

export type CategoryMergeResult = {
  status: string;
  merged_slug: string;
  target_slug: string;
  transactions_moved: number;
  rules_moved: number;
  budget_moved: number;
};

export const moneyApi = {
  health: () => api<{ status: string; auth_required: boolean }>("/api/health"),
  stats: () => api<MoneyStats>("/api/money/stats"),
  completeness: () => api<MoneyStats>("/api/money/completeness"),
  categories: () => api<{ categories: CategoryInfo[] }>("/api/money/categories"),
  createCategory: (name: string) =>
    api<CategoryInfo>("/api/money/categories", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),
  renameCategory: (slug: string, name: string) =>
    api<CategoryInfo>(`/api/money/categories/${encodeURIComponent(slug)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),
  deleteCategory: (slug: string) =>
    api<{
      status: string;
      removed_slug: string;
      transactions_recategorized: number;
      transactions_unclear: number;
    }>(`/api/money/categories/${encodeURIComponent(slug)}`, { method: "DELETE" }),
  deleteCategoryPreview: (slug: string) =>
    api<CategoryDeletePreview>(
      `/api/money/categories/${encodeURIComponent(slug)}/delete-preview`,
    ),
  mergeCategory: (slug: string, targetSlug: string) =>
    api<CategoryMergeResult>(`/api/money/categories/${encodeURIComponent(slug)}/merge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_slug: targetSlug }),
    }),
  summary: () => api<{ by_category: Array<Record<string, number | string>> }>("/api/money/summary"),
  cashflow: (months = 12) => api<{ months: CashflowMonth[] }>(`/api/money/cashflow?months=${months}`),
  breakdown: (kind: "spent" | "income", opts?: { month?: string; months?: number }) => {
    const q = new URLSearchParams({ kind });
    if (opts?.month) q.set("month", opts.month);
    if (opts?.months != null) q.set("months", String(opts.months));
    return api<{ categories: Array<{ category: string; total: number; tx_count: number }> }>(
      `/api/money/breakdown?${q}`,
    );
  },
  transactions: (params?: {
    needs_review?: boolean;
    income_review?: boolean;
    transfer_review?: boolean;
    transfers_only?: boolean;
    category?: string;
    search?: string;
    tag?: string;
    month?: string;
    sort?: string;
  }) => {
    const q = new URLSearchParams();
    if (params?.needs_review != null) q.set("needs_review", String(params.needs_review));
    if (params?.income_review != null) q.set("income_review", String(params.income_review));
    if (params?.transfer_review != null) q.set("transfer_review", String(params.transfer_review));
    if (params?.transfers_only != null) q.set("transfers_only", String(params.transfers_only));
    if (params?.category) q.set("category", params.category);
    if (params?.search) q.set("search", params.search);
    if (params?.tag) q.set("tag", params.tag);
    if (params?.month) q.set("month", params.month);
    if (params?.sort) q.set("sort", params.sort);
    const s = q.toString();
    return api<{ transactions: Transaction[] }>(`/api/money/transactions${s ? `?${s}` : ""}`);
  },
  classifyTransfer: (body: {
    transaction_ids: number[];
    kind: "internal" | "income" | "expense";
    category?: string;
    remember?: boolean;
    match_text?: string;
  }) =>
    api<{ updated: number }>("/api/money/transactions/classify-transfer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  preview: async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return api<{
      headers: string[];
      preview_rows: Record<string, string>[];
      delimiter: string;
      guessed_mapping: Record<string, string | null>;
      guessed_amount_decimal?: string;
      parsed_preview?: Array<{ tx_date: string; amount: number; description: string }>;
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
  bulkUpdateCategory: (
    transaction_ids: number[],
    category: string,
    remember: boolean,
    match_text?: string,
  ) =>
    api<{ updated: number }>("/api/money/transactions/bulk-category", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transaction_ids, category, remember, match_text }),
    }),
  recurring: () => api<{ groups: RecurringGroup[] }>("/api/money/recurring"),
  updateRecurring: (id: number, body: Partial<RecurringGroup>) =>
    api<RecurringGroup>(`/api/money/recurring/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  rules: () => api<{ rules: Array<Record<string, unknown>> }>("/api/money/rules"),
  updateRule: (id: number, body: { category?: string; enabled?: boolean; match_text?: string }) =>
    api(`/api/money/rules/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  alerts: () =>
    api<{
      budget: Array<Record<string, unknown>>;
      price: Array<Record<string, unknown>>;
      recommendations: Array<Record<string, unknown>>;
    }>("/api/money/alerts"),
  insights: (months = 12) => api<{ insights: Insight[] }>(`/api/money/insights?months=${months}`),
  priceAlerts: () =>
    api<{ alerts: PriceAlert[]; yearly_total: number }>("/api/money/recurring/alerts"),
  acknowledgePriceEvent: (id: number) =>
    api<{ status: string }>(`/api/money/recurring/price-events/${id}/acknowledge`, {
      method: "PATCH",
    }),
  importSample: () => api<{ row_count: number }>("/api/money/import/sample", { method: "POST" }),
  bankProfiles: () => api<{ profiles: Array<Record<string, unknown>> }>("/api/money/bank-profiles"),
  budgets: () => api<{ budgets: Array<Record<string, unknown>>; savings_goals: Array<Record<string, unknown>> }>(
    "/api/money/budgets",
  ),
  setBudget: (category: string, monthly_limit: number | null, enabled = true) =>
    api("/api/money/budgets", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category, monthly_limit, enabled }),
    }),
  yearComparison: () => api<{ years: Array<Record<string, unknown>> }>("/api/money/year-comparison"),
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
  restoreBackup: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return api<{ status: string; restored: Record<string, number> }>("/api/data/import/backup", {
      method: "POST",
      body: fd,
    });
  },
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
