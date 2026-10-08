import type { HistoryPoint } from "./portfolioApi";

export type RangeId = "1M" | "3M" | "6M" | "YTD" | "1Y" | "ALL";

export const RANGES: { id: RangeId; label: string; phrase: string }[] = [
  { id: "1M", label: "1M", phrase: "past month" },
  { id: "3M", label: "3M", phrase: "past 3 months" },
  { id: "6M", label: "6M", phrase: "past 6 months" },
  { id: "YTD", label: "YTD", phrase: "year to date" },
  { id: "1Y", label: "1Y", phrase: "past year" },
  { id: "ALL", label: "All", phrase: "since your first trade" },
];

export interface ChartPoint {
  time: number; // UTC seconds at midnight of the date
  value: number;
  invested: number;
  income: number;
}

export const toChartPoints = (pts: HistoryPoint[]): ChartPoint[] =>
  pts.map((p) => ({ time: Date.parse(`${p.date}T00:00:00Z`) / 1000, value: p.value, invested: p.invested, income: p.income }));

/** The same day N months earlier (clamped, so 31 March minus a month is 28 February), in UTC seconds. */
function monthsBack(d: Date, months: number): number {
  const total = d.getUTCFullYear() * 12 + d.getUTCMonth() - months;
  const y = Math.floor(total / 12);
  const m = total % 12;
  const daysInMonth = new Date(Date.UTC(y, m + 1, 0)).getUTCDate();
  return Date.UTC(y, m, Math.min(d.getUTCDate(), daysInMonth)) / 1000;
}

/**
 * `shown` is what the chart plots. `base` is `shown` with one extra point in front, used to measure the
 * return: the close just before the range, or an all-zero point when the portfolio began inside the range.
 */
export function sliceRange(points: ChartPoint[], range: RangeId): { shown: ChartPoint[]; base: ChartPoint[] } {
  if (points.length === 0) return { shown: [], base: [] };
  let firstIn = 0;
  if (range !== "ALL") {
    const last = new Date(points[points.length - 1].time * 1000);
    const cutoff = // keep points strictly after this moment
      range === "YTD"
        ? Date.UTC(last.getUTCFullYear(), 0, 1) / 1000 - 1
        : monthsBack(last, range === "1M" ? 1 : range === "3M" ? 3 : range === "6M" ? 6 : 12);
    firstIn = points.findIndex((p) => p.time > cutoff);
    if (firstIn === -1) return { shown: [], base: [] };
  }
  const shown = points.slice(firstIn);
  const baseline: ChartPoint =
    firstIn > 0 ? points[firstIn - 1] : { time: points[0].time - 86400, value: 0, invested: 0, income: 0 };
  return { shown, base: [baseline, ...shown] };
}

/**
 * Return over the range with new money taken out, so buying more doesn't look like a gain and selling
 * doesn't look like a loss (the Modified Dietz method). Dividends count as return.
 *
 * Money that arrives on a given day is treated as being in place for that whole day, which matches the
 * numerator: it includes that day's price move on the new shares.
 */
export function rangeReturn(base: ChartPoint[]): { gain: number; pct: number | null } | null {
  const n = base.length - 1;
  if (n < 1) return null;
  const a = base[0];
  const b = base[n];
  const gain = b.value - a.value - (b.invested - a.invested) + (b.income - a.income);
  let denominator = a.value;
  for (let i = 1; i <= n; i++) denominator += ((n - i + 1) / n) * (base[i].invested - base[i - 1].invested);
  return { gain, pct: denominator > 0 ? (gain / denominator) * 100 : null };
}
