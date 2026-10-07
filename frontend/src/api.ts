export type Timeframe = "D" | "W" | "M" | "Q" | "YTD" | "Y" | "5Y";
export type ChartType = "candles" | "line";

export interface ChartData {
  ticker: string;
  timeframe: Timeframe;
  label: string;
  intraday: boolean;
  quote: { price: number; change_pct: number | null };
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
