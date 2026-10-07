export type Timeframe = "D" | "W" | "M" | "Q" | "Y" | "5Y";

export interface ChartData {
  ticker: string;
  timeframe: Timeframe;
  candles: { time: string; open: number; high: number; low: number; close: number }[];
  volume: { time: string; value: number; up: boolean }[];
  rsi: { time: string; value: number }[];
  macd: { time: string; macd: number; signal: number; hist: number }[];
}

export async function fetchChart(ticker: string, timeframe: Timeframe): Promise<ChartData> {
  const res = await fetch(`/api/chart/${encodeURIComponent(ticker)}?timeframe=${timeframe}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${res.status})`);
  }
  return res.json();
}
