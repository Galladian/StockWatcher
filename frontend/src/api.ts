export type Timeframe = "D" | "W" | "M" | "Q" | "YTD" | "Y" | "5Y";
export type ChartType = "candles" | "line";

export interface ChartData {
  ticker: string;
  timeframe: Timeframe;
  label: string;
  intraday: boolean;
  quote: { price: number; change_pct: number | null; change_label: string };
  // `time` is UTC seconds (intraday values are exchange wall-clock time)
  candles: { time: number; open: number; high: number; low: number; close: number }[];
  volume: { time: number; value: number; up: boolean }[];
  ema: { label: string; data: { time: number; value: number }[] };
  rsi: { time: number; value: number }[];
  macd: { time: number; macd: number; signal: number; hist: number }[];
}

export async function fetchChart(ticker: string, timeframe: Timeframe): Promise<ChartData> {
  const res = await fetch(`/api/chart/${encodeURIComponent(ticker)}?timeframe=${timeframe}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${res.status})`);
  }
  return res.json();
}

type N = number | null;

export interface Metrics {
  ticker: string;
  name: string | null;
  sector: string | null;
  industry: string | null;
  exchange: string | null;
  price: N;
  market_cap: N; enterprise_value: N; pe_trailing: N; pe_forward: N; peg: N;
  price_to_sales: N; price_to_book: N; ev_to_ebitda: N; eps_trailing: N; eps_forward: N;
  dividend_rate: N; dividend_yield: N; payout_ratio: N; ex_dividend_date: string | null;
  gross_margin: N; operating_margin: N; profit_margin: N; roe: N; roa: N;
  revenue: N; revenue_growth: N; earnings_growth: N; free_cash_flow: N;
  total_cash: N; total_debt: N; debt_to_equity: N; current_ratio: N;
  beta: N; week52_high: N; week52_low: N; avg_volume: N; shares_outstanding: N; short_percent_float: N;
  recommendation: string | null; analyst_count: N;
  target_mean: N; target_high: N; target_low: N; target_upside: N;
}

export async function fetchMetrics(ticker: string): Promise<Metrics> {
  const res = await fetch(`/api/metrics/${encodeURIComponent(ticker)}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${res.status})`);
  }
  return res.json();
}

export type CheckStatus = "good" | "ok" | "bad" | "na";

export interface ScreenCheck {
  id: string;
  label: string;
  status: CheckStatus;
  value: string;
  detail: string;
  rule: string;
}

export interface ScreenVerdict {
  verdict: string;
  tone: CheckStatus;
  summary: string;
}

export interface Screen {
  ticker: string;
  name: string | null;
  sector: string | null;
  industry: string | null;
  price: number | null;
  market_cap: number | null;
  valuation: (ScreenVerdict & { groups: { title: string; checks: ScreenCheck[] }[] }) | null;
  short_term: (ScreenVerdict & { checks: ScreenCheck[]; extras: ScreenCheck[] }) | null;
  warnings: string[];
}

export async function fetchScreen(ticker: string): Promise<Screen> {
  const res = await fetch(`/api/screener/${encodeURIComponent(ticker)}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${res.status})`);
  }
  return res.json();
}
