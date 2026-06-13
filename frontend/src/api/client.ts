// Typed API client. All money fields are integer minor units (paisa);
// conversion to PKR happens at the UI edge only (see format.ts).

const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

// ---------------------------------------------------------------- types

export interface Summary {
  current_balance_minor: number;
  as_of: string;
  txn_count: number;
  warnings: string[];
  documents: DocumentInfo[];
}

export interface DocumentInfo {
  id: number;
  filename: string;
  file_type: string;
  status: string;
  discrepancy_minor: number | null;
  period_start: string | null;
  period_end: string | null;
}

export interface MonthCashflow {
  month: { year: number; month: number };
  income_minor: number;
  expense_minor: number;
  net_minor: number;
  by_category: Record<string, number>;
  txn_count: number;
}

export interface Txn {
  id: number;
  txn_date: string;
  amount_minor: number;
  merchant: string | null;
  raw_description: string;
  category: string | null;
}

export interface Anomaly {
  txn_id: number | null;
  txn_date: string;
  merchant: string | null;
  amount_minor: number;
  category: string;
  kind: string;
  reason: string;
}

export interface RecurringGroup {
  group_id: string;
  merchant: string;
  cadence_days: number;
  typical_amount_minor: number;
  occurrences: number;
  last_date: string;
  monthly_equivalent_minor: number;
  price_change: boolean;
  price_change_pct: number | null;
  last_amount_minor: number | null;
}

export interface Goal {
  id: number;
  name: string;
  target_amount_minor: number;
  target_date: string;
  saved_so_far_minor: number;
  remaining_minor: number;
  months_to_complete: number | null;
  projected_completion: string | null;
  on_track: boolean;
}

export interface IngestResult {
  doc_id: number;
  status: string;
  reconciled: boolean | null;
  discrepancy_minor: number | null;
  txn_count: number;
  skipped_duplicates: number;
  file_type: string;
}

export interface ChatResponse {
  answer: string;
  intent: string;
  tool_calls: { name: string; args: Record<string, unknown> }[];
  data: { result: Record<string, any>; warnings?: string[] } | null;
  trace_id: string;
  explained_by: string;
}

// ------------------------------------------------------------- endpoints

export const api = {
  summary: () => get<Summary>("/dashboard/summary"),
  cashflow: (months = 6) =>
    get<{ months: MonthCashflow[] }>(`/dashboard/cashflow?months=${months}`),
  categories: (month?: string) =>
    get<MonthCashflow>(`/dashboard/categories${month ? `?month=${month}` : ""}`),
  transactions: (params: { month?: string; category?: string }) => {
    const q = new URLSearchParams();
    if (params.month) q.set("month", params.month);
    if (params.category) q.set("category", params.category);
    return get<{ transactions: Txn[] }>(`/dashboard/transactions?${q}`);
  },
  anomalies: () => get<{ anomalies: Anomaly[] }>("/dashboard/anomalies"),
  recurring: () => get<{ recurring: RecurringGroup[] }>("/dashboard/recurring"),
  goals: () => get<{ goals: Goal[] }>("/goals"),
  createGoal: (g: { name: string; target_amount_minor: number; target_date: string }) =>
    post<Goal>("/goals", g),
  chat: (message: string) => post<ChatResponse>("/chat", { message }),
  upload: async (file: File): Promise<IngestResult> => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/ingest`, { method: "POST", body: form });
    if (!res.ok) {
      const detail = await res.json().catch(() => null);
      throw new Error(detail?.detail ?? `Upload failed (${res.status})`);
    }
    return res.json();
  },
};
