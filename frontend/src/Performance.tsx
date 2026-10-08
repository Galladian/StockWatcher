import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AreaSeries, ColorType, CrosshairMode, LineSeries, createChart, type IChartApi, type ISeriesApi, type Time } from "lightweight-charts";
import { CURRENCIES, fetchHistory } from "./portfolioApi";
import { RANGES, rangeReturn, sliceRange, toChartPoints, type ChartPoint, type RangeId } from "./history";
import { isoToDmy } from "./dates";
import { useTheme } from "./theme";

// Canvas colours, kept in step with styles.css (the chart sits on a card, so it uses the panel colour)
const HC = {
  dark: { bg: "#151b22", text: "#9aa5b1", grid: "#1f2731", line: "#4da3ff", top: "rgba(77,163,255,0.35)", bottom: "rgba(77,163,255,0.02)", invested: "#9aa5b1" },
  light: { bg: "#f6f8fa", text: "#59636e", grid: "#e1e6eb", line: "#0969da", top: "rgba(9,105,218,0.25)", bottom: "rgba(9,105,218,0.02)", invested: "#59636e" },
};

const compact = new Intl.NumberFormat("en-NZ", { notation: "compact", maximumFractionDigits: 1 });
const money = (v: number, ccy: string) =>
  new Intl.NumberFormat("en-NZ", { style: "currency", currency: ccy, maximumFractionDigits: 0 }).format(v);
const signedMoney = (v: number, ccy: string) => `${v >= 0 ? "+" : "-"}${money(Math.abs(v), ccy)}`;
const signedPct = (v: number | null) => (v === null ? "–" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`);
const tone = (v: number | null) => (v === null ? "" : v >= 0 ? "pos" : "neg");
const dmy = (seconds: number) => isoToDmy(new Date(seconds * 1000).toISOString().slice(0, 10));

function HistoryChart({ points, ccy }: { points: ChartPoint[]; ccy: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<{ value: ISeriesApi<"Area">; invested: ISeriesApi<"Line"> } | null>(null);
  const { resolved } = useTheme();
  const colors = HC[resolved];
  const colorsRef = useRef(colors);
  colorsRef.current = colors;
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    const C = colorsRef.current;
    const chart = createChart(containerRef.current!, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: C.bg }, textColor: C.text },
      grid: { vertLines: { color: C.grid }, horzLines: { color: C.grid } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: C.grid },
      timeScale: { borderColor: C.grid },
      localization: { dateFormat: "dd/MM/yyyy", priceFormatter: (p: number) => compact.format(p) },
    });
    const value = chart.addSeries(AreaSeries, { lineColor: C.line, topColor: C.top, bottomColor: C.bottom, lineWidth: 2, priceLineVisible: false });
    const invested = chart.addSeries(LineSeries, { color: C.invested, lineWidth: 2, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });
    chartRef.current = chart;
    seriesRef.current = { value, invested };
    chart.subscribeCrosshairMove((p) => setHover(typeof p.time === "number" ? p.time : null));
    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    const s = seriesRef.current;
    const chart = chartRef.current;
    if (!s || !chart) return;
    chart.applyOptions({
      layout: { background: { type: ColorType.Solid, color: colors.bg }, textColor: colors.text },
      grid: { vertLines: { color: colors.grid }, horzLines: { color: colors.grid } },
      rightPriceScale: { borderColor: colors.grid },
      timeScale: { borderColor: colors.grid },
    });
    s.value.applyOptions({ lineColor: colors.line, topColor: colors.top, bottomColor: colors.bottom });
    s.invested.applyOptions({ color: colors.invested });
  }, [colors]);

  useEffect(() => {
    const s = seriesRef.current;
    const chart = chartRef.current;
    if (!s || !chart) return;
    s.value.setData(points.map((p) => ({ time: p.time as Time, value: p.value })));
    s.invested.setData(points.map((p) => ({ time: p.time as Time, value: p.invested })));
    chart.timeScale().fitContent();
  }, [points]);

  const byTime = useMemo(() => new Map(points.map((p) => [p.time, p])), [points]);
  const p = (hover !== null ? byTime.get(hover) : undefined) ?? points[points.length - 1];

  return (
    <div className="hist-wrap">
      <div ref={containerRef} className="hist-chart" />
      {p && (
        <div className="legend" style={{ top: 8 }}>
          <b>{dmy(p.time)}</b>
          <span style={{ color: colors.line }}>Value {money(p.value, ccy)}</span>
          <span>Money invested {money(p.invested, ccy)}</span>
        </div>
      )}
    </div>
  );
}

export default function Performance({ currency, onCurrency }: { currency: string; onCurrency: (c: string) => void }) {
  const [range, setRange] = useState<RangeId>("1Y");
  const { data, error, isLoading } = useQuery({
    queryKey: ["history", currency],
    queryFn: () => fetchHistory(currency),
    staleTime: 60_000,
    placeholderData: (prev) => prev,
  });
  const all = useMemo(() => (data ? toChartPoints(data.points) : []), [data]);
  const { shown, base } = useMemo(() => sliceRange(all, range), [all, range]);

  if (isLoading) return <p className="muted">Building your history…</p>;
  if (error || !data) return <p className="form-error">{(error as Error)?.message ?? "Couldn't load your history"}</p>;
  if (all.length === 0)
    return <div className="empty">No history yet. Record a buy on the Transactions tab and your portfolio's value over time will appear here.</div>;

  const ccy = data.currency;
  const latest = all[all.length - 1];
  const ret = rangeReturn(base);
  const phrase = RANGES.find((r) => r.id === range)!.phrase;
  const profit = latest.value - latest.invested + latest.income;
  const profitPct = latest.invested > 0 ? (profit / latest.invested) * 100 : null;

  return (
    <>
      <div className="section-head">
        <h2>Portfolio value over time</h2>
        <label className="muted">
          Values in{" "}
          <select className="ccy" value={currency} onChange={(e) => onCurrency(e.target.value)} aria-label="Display currency">
            {CURRENCIES.map((c) => <option key={c}>{c}</option>)}
          </select>
        </label>
      </div>

      <div className="stats">
        <div className="card stat">
          <div className="label">Value of your stocks</div>
          <div className="value">{money(latest.value, ccy)}</div>
          <div className="sub">As at {dmy(latest.time)}</div>
        </div>
        <div className="card stat">
          <div className="label">Return, {phrase}</div>
          <div className={`value ${tone(ret?.gain ?? null)}`}>{ret ? signedMoney(ret.gain, ccy) : "–"}</div>
          <div className={`sub ${tone(ret?.pct ?? null)}`}>{ret ? signedPct(ret.pct) : ""}</div>
        </div>
        <div className="card stat">
          <div className="label">Profit overall</div>
          <div className={`value ${tone(profit)}`}>{signedMoney(profit, ccy)}</div>
          <div className={`sub ${tone(profitPct)}`}>{signedPct(profitPct)} on {money(latest.invested, ccy)} invested</div>
        </div>
      </div>

      <div className="tabs range-tabs" role="group" aria-label="Time range">
        {RANGES.map((r) => (
          <button key={r.id} className={range === r.id ? "active" : ""} onClick={() => setRange(r.id)}>{r.label}</button>
        ))}
      </div>

      <div className="card hist-card">
        {shown.length > 0 ? <HistoryChart points={shown} ccy={ccy} /> : <div className="empty">No data in this range.</div>}
      </div>

      {data.warnings.length > 0 && <div className="notice" style={{ marginTop: 16 }}>{data.warnings.map((w) => <div key={w}>{w}</div>)}</div>}

      <p className="foot">
        Each day is the shares you held that day times that day's closing price. The dashed line is the money you have put in
        (buys minus sales, fees included), so the gap between the lines is your gain. Cash isn't included because cash balances
        have no dates. Returns leave out money you add or take out and include dividends. All days use today's exchange rate
        {data.fx_rate ? ` (1 USD = ${data.fx_rate.toFixed(4)} ${ccy})` : ""}.
      </p>
    </>
  );
}
