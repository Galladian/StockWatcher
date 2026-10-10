export type PeriodId = "1D" | "1W" | "1M" | "3M" | "YTD" | "1Y";

export const PERIODS: { id: PeriodId; label: string; phrase: string }[] = [
  { id: "1D", label: "1D", phrase: "today" },
  { id: "1W", label: "1W", phrase: "past week" },
  { id: "1M", label: "1M", phrase: "past month" },
  { id: "3M", label: "3M", phrase: "past 3 months" },
  { id: "YTD", label: "YTD", phrase: "year to date" },
  { id: "1Y", label: "1Y", phrase: "past year" },
];

export interface IndexRow {
  symbol: string;
  name: string;
  country: string;
  last: number | null;
  change_pct: number | null;
  date: string | null; // the latest session this figure is from
}

export interface IndicesData {
  period: PeriodId;
  regions: { name: string; items: IndexRow[] }[];
}

export interface HeatStock {
  symbol: string;
  name: string;
  price: number;
  change_pct: number;
  market_cap: number;
}

export interface HeatSector {
  name: string;
  market_cap: number;
  change_pct: number; // market-cap weighted
  stocks: HeatStock[];
}

export interface HeatmapData {
  period: PeriodId;
  as_of: string | null;
  index_change_pct: number | null; // the S&P 500 itself
  sectors: HeatSector[];
  loaded: number;
  total: number;
  partial: boolean; // company sizes are still being looked up
  source: string;
}

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `Request failed (${res.status})`);
  }
  return res.json();
}

export const fetchIndices = (period: PeriodId) => get<IndicesData>(`/api/markets/indices?period=${period}`);
export const fetchHeatmap = (period: PeriodId) => get<HeatmapData>(`/api/markets/heatmap?period=${period}`);
