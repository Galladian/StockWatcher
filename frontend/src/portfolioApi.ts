export type TxType = "buy" | "sell" | "dividend";

// Decimals arrive as strings so no precision is lost on the way
export interface Transaction {
  id: number;
  ticker: string;
  type: TxType;
  trade_date: string;
  quantity: string;
  price: string;
  fees: string;
  note: string | null;
}

export interface NewTransaction {
  ticker: string;
  type: TxType;
  trade_date: string;
  quantity: string;
  price: string;
  fees: string;
  note: string;
}

function errorMessage(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const field = Array.isArray(d?.loc) ? String(d.loc[d.loc.length - 1]).replace("_", " ") : "";
        const msg = String(d?.msg ?? "Invalid value").replace(/^Value error, /, "");
        return field && !msg.toLowerCase().includes(field) ? `${field}: ${msg}` : msg;
      })
      .join(". ");
  }
  return `Request failed (${status})`;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(errorMessage(body.detail, res.status));
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export const fetchMe = () => request<{ username: string | null }>("/api/auth/me");

export const login = (username: string, password: string) =>
  request<{ username: string }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });

export const logout = () => request<{ ok: boolean }>("/api/auth/logout", { method: "POST" });

export const listTransactions = () => request<Transaction[]>("/api/portfolio/transactions");

export const addTransaction = (tx: NewTransaction) =>
  request<Transaction>("/api/portfolio/transactions", { method: "POST", body: JSON.stringify(tx) });

export const updateTransaction = (id: number, tx: NewTransaction) =>
  request<Transaction>(`/api/portfolio/transactions/${id}`, { method: "PUT", body: JSON.stringify(tx) });

export const deleteTransaction = (id: number) =>
  request<void>(`/api/portfolio/transactions/${id}`, { method: "DELETE" });

type N = number | null;

export interface Holding {
  ticker: string;
  shares: number;
  avg_cost: number;
  cost_basis: number;
  price: N;
  prev_close: N;
  market_value: N;
  day_change: N;
  day_change_pct: N;
  unrealized: N;
  unrealized_pct: N;
  weight: N;
}

export const CURRENCIES = ["NZD", "USD", "AUD", "GBP", "EUR", "CAD", "JPY"]; // NZD first

export interface CashAccount {
  id: number;
  label: string;
  currency: string;
  amount: number; // in its own currency
  value: N;       // converted to the display currency
  weight: N;
}

export interface Summary {
  as_of: string | null;
  currency: string;   // the currency the figures are actually in
  fx_rate: N;         // units of `currency` per 1 USD (null when showing USD)
  cash: CashAccount[];
  totals: {
    cash: number;
    total_value: number;
    market_value: number;
    cost_basis: number;
    day_change: number;
    day_change_pct: N;
    unrealized: number;
    unrealized_pct: N;
    realized: number;
    dividends: number;
    total_return: number;
  };
  holdings: Holding[];
  warnings: string[];
}

export const fetchSummary = (currency: string) =>
  request<Summary>(`/api/portfolio/summary?currency=${encodeURIComponent(currency)}`);

export interface CashInput {
  label: string;
  currency: string;
  amount: string;
}

export const addCash = (c: CashInput) =>
  request<{ id: number }>("/api/portfolio/cash", { method: "POST", body: JSON.stringify(c) });

export const updateCash = (id: number, c: CashInput) =>
  request<{ id: number }>(`/api/portfolio/cash/${id}`, { method: "PUT", body: JSON.stringify(c) });

export const deleteCash = (id: number) => request<void>(`/api/portfolio/cash/${id}`, { method: "DELETE" });

export interface SectorSlice {
  name: string;
  value: number;
  weight: number;
  holdings: { ticker: string; value: number }[];
}

export interface Mover {
  ticker: string;
  pct: number;
  amount: number;
}

export interface BreakdownData {
  currency: string;
  total_value: number;
  sectors: SectorSlice[];
  concentration: {
    holdings_count: number;
    top: { ticker: string; weight: number } | null;
    top3: number;
    top5: number;
    effective_n: number | null;
    largest_sector: { name: string; weight: number } | null;
  };
  characteristics: {
    beta: N; beta_coverage: N; forward_pe: N; pe_coverage: N;
    dividend_income: number; dividend_yield: N; dividend_payers: number;
  };
  market_cap: { name: string; value: number; weight: number }[];
  performance: { winners: number; losers: number; best: Mover | null; worst: Mover | null; day_best: Mover | null; day_worst: Mover | null };
  observations: { tone: "good" | "ok" | "info"; text: string }[];
  warnings: string[];
}

export const fetchBreakdown = (currency: string) =>
  request<BreakdownData>(`/api/portfolio/breakdown?currency=${encodeURIComponent(currency)}`);
