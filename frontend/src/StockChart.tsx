import { useEffect, useMemo, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  LineType,
  createChart,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";
import type { ChartData, ChartType } from "./api";
import { useTheme } from "./theme";

// The chart draws on a canvas, so it can't use the CSS variables. Keep these in step with styles.css.
const THEMES = {
  dark: {
    bg: "#0f1419", text: "#9aa5b1", grid: "#1b222b",
    up: "#26a69a", down: "#ef5350", upFaint: "rgba(38,166,154,0.45)", downFaint: "rgba(239,83,80,0.45)",
    rsi: "#b794f4", price: "#4da3ff", macd: "#4da3ff", signal: "#f6ad55", ema: "#ffd54f",
  },
  light: {
    bg: "#ffffff", text: "#59636e", grid: "#eaeef2",
    up: "#0e7a6c", down: "#cf222e", upFaint: "rgba(14,122,108,0.40)", downFaint: "rgba(207,34,46,0.40)",
    rsi: "#8250df", price: "#0969da", macd: "#0969da", signal: "#bc4c00", ema: "#bf8700",
  },
};
type Colors = typeof THEMES.dark;

// Relative pane heights, top to bottom: RSI, price, volume, MACD.
const STRETCH = [1.2, 5, 1, 1.6];

const compact = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 2 });
const n2 = (v?: number) => (v === undefined ? "–" : v.toFixed(2));

interface Series {
  rsi: ISeriesApi<"Line">;
  rsiLines: IPriceLine[]; // overbought, oversold
  candles: ISeriesApi<"Candlestick">;
  line: ISeriesApi<"Line">;
  ema: ISeriesApi<"Line">;
  volume: ISeriesApi<"Histogram">;
  hist: ISeriesApi<"Histogram">;
  macd: ISeriesApi<"Line">;
  signal: ISeriesApi<"Line">;
}

const byTime = <T extends { time: number }>(a: T[]) => new Map(a.map((d) => [d.time, d]));

export default function StockChart({ data, chartType }: { data: ChartData; chartType: ChartType }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<Series | null>(null);

  const { resolved } = useTheme();
  const colors: Colors = THEMES[resolved];
  const colorsRef = useRef(colors);
  colorsRef.current = colors;

  const [hoverTime, setHoverTime] = useState<number | null>(null);
  const [tops, setTops] = useState<number[]>([0, 0, 0, 0]); // y-offset of each pane

  // Create the chart once
  useEffect(() => {
    const C = colorsRef.current;
    const el = containerRef.current!;
    const chart = createChart(el, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: C.bg },
        textColor: C.text,
        panes: { separatorColor: C.grid },
      },
      grid: { vertLines: { color: C.grid }, horzLines: { color: C.grid } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: C.grid },
      timeScale: { borderColor: C.grid },
    });

    // No series "title" tags: names live in the legend at the top-left of each pane,
    // so nothing covers the newest candles. Values still show on the right axis.
    // Add in pane order: 0 RSI, 1 price, 2 volume, 3 MACD
    const rsi = chart.addSeries(LineSeries, { color: C.rsi, lineWidth: 2, priceLineVisible: false }, 0);
    const rsiLines = [
      rsi.createPriceLine({ price: 70, color: C.down, lineStyle: 2, lineWidth: 1, axisLabelVisible: false }),
      rsi.createPriceLine({ price: 30, color: C.up, lineStyle: 2, lineWidth: 1, axisLabelVisible: false }),
    ];

    const candles = chart.addSeries(
      CandlestickSeries,
      { upColor: C.up, downColor: C.down, borderVisible: false, wickUpColor: C.up, wickDownColor: C.down },
      1
    );
    const line = chart.addSeries(LineSeries, { color: C.price, lineWidth: 2, visible: false }, 1);
    const ema = chart.addSeries(
      LineSeries,
      { color: C.ema, lineWidth: 2, lineType: LineType.Curved, priceLineVisible: false, crosshairMarkerVisible: false },
      1
    );
    const volume = chart.addSeries(
      HistogramSeries,
      { priceFormat: { type: "volume" }, priceLineVisible: false, lastValueVisible: false },
      2
    );
    const hist = chart.addSeries(HistogramSeries, { priceLineVisible: false, lastValueVisible: false }, 3);
    const macd = chart.addSeries(LineSeries, { color: C.macd, lineWidth: 2, priceLineVisible: false }, 3);
    const signal = chart.addSeries(LineSeries, { color: C.signal, lineWidth: 2, priceLineVisible: false }, 3);

    chart.panes().forEach((pane, i) => pane.setStretchFactor(STRETCH[i]));

    chartRef.current = chart;
    seriesRef.current = { rsi, rsiLines, candles, line, ema, volume, hist, macd, signal };

    // Work out where each pane starts so the legends can sit inside them
    const measure = () => {
      let y = 0;
      const next: number[] = [];
      chart.panes().forEach((p) => {
        next.push(y);
        y += p.getHeight() + 1; // +1 for the separator
      });
      setTops((prev) => (prev.length === next.length && prev.every((v, i) => v === next[i]) ? prev : next));
    };
    const schedule = () => requestAnimationFrame(measure);
    schedule();
    const ro = new ResizeObserver(schedule);
    ro.observe(el);
    el.addEventListener("pointerup", schedule); // after dragging a pane separator

    chart.subscribeCrosshairMove((p) => setHoverTime(typeof p.time === "number" ? p.time : null));

    return () => {
      ro.disconnect();
      el.removeEventListener("pointerup", schedule);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  // Re-colour the chart when the theme changes
  useEffect(() => {
    const s = seriesRef.current;
    const chart = chartRef.current;
    if (!s || !chart) return;
    chart.applyOptions({
      layout: { background: { type: ColorType.Solid, color: colors.bg }, textColor: colors.text, panes: { separatorColor: colors.grid } },
      grid: { vertLines: { color: colors.grid }, horzLines: { color: colors.grid } },
      rightPriceScale: { borderColor: colors.grid },
      timeScale: { borderColor: colors.grid },
    });
    s.rsi.applyOptions({ color: colors.rsi });
    s.rsiLines[0].applyOptions({ color: colors.down });
    s.rsiLines[1].applyOptions({ color: colors.up });
    s.candles.applyOptions({ upColor: colors.up, downColor: colors.down, wickUpColor: colors.up, wickDownColor: colors.down });
    s.line.applyOptions({ color: colors.price });
    s.ema.applyOptions({ color: colors.ema });
    s.macd.applyOptions({ color: colors.macd });
    s.signal.applyOptions({ color: colors.signal });
  }, [colors]);

  // Push new data whenever ticker/timeframe changes
  useEffect(() => {
    const s = seriesRef.current;
    const chart = chartRef.current;
    if (!s || !chart) return;

    chart.applyOptions({ timeScale: { timeVisible: data.intraday, secondsVisible: false } });

    s.candles.setData(data.candles.map((d) => ({ ...d, time: d.time as Time })));
    s.line.setData(data.candles.map((d) => ({ time: d.time as Time, value: d.close })));
    s.ema.setData(data.ema.data.map((d) => ({ time: d.time as Time, value: d.value })));
    s.rsi.setData(data.rsi.map((d) => ({ time: d.time as Time, value: d.value })));
    s.macd.setData(data.macd.map((d) => ({ time: d.time as Time, value: d.macd })));
    s.signal.setData(data.macd.map((d) => ({ time: d.time as Time, value: d.signal })));
    chart.timeScale().fitContent();
  }, [data]);

  // The volume and histogram bars carry their own colours, so they are redrawn on a theme change
  // (this doesn't touch the zoom).
  useEffect(() => {
    const s = seriesRef.current;
    if (!s) return;
    s.volume.setData(
      data.volume.map((d) => ({ time: d.time as Time, value: d.value, color: d.up ? colors.upFaint : colors.downFaint }))
    );
    s.hist.setData(
      data.macd.map((d) => ({ time: d.time as Time, value: d.hist, color: d.hist >= 0 ? colors.upFaint : colors.downFaint }))
    );
  }, [data, colors]);

  // Candles <-> line
  useEffect(() => {
    const s = seriesRef.current;
    if (!s) return;
    s.candles.applyOptions({ visible: chartType === "candles" });
    s.line.applyOptions({ visible: chartType === "line" });
  }, [chartType]);

  // Legend values: the hovered bar, or the latest bar when the mouse is away
  const maps = useMemo(
    () => ({
      candles: byTime(data.candles),
      ema: byTime(data.ema.data),
      rsi: byTime(data.rsi),
      volume: byTime(data.volume),
      macd: byTime(data.macd),
    }),
    [data]
  );
  const t = hoverTime ?? data.candles[data.candles.length - 1]?.time;
  const bar = t === undefined ? undefined : maps.candles.get(t);
  const emaV = t === undefined ? undefined : maps.ema.get(t);
  const rsiV = t === undefined ? undefined : maps.rsi.get(t);
  const volV = t === undefined ? undefined : maps.volume.get(t);
  const macdV = t === undefined ? undefined : maps.macd.get(t);
  const barColor = bar && bar.close >= bar.open ? colors.up : colors.down;

  return (
    <div className="chart-wrap">
      <div ref={containerRef} className="chart" />

      <div className="legend" style={{ top: tops[0] + 6 }}>
        <b style={{ color: colors.rsi }}>RSI 14</b>
        <span>{n2(rsiV?.value)}</span>
      </div>

      <div className="legend" style={{ top: tops[1] + 6 }}>
        {bar && (
          <span style={{ color: barColor }}>
            O {n2(bar.open)} H {n2(bar.high)} L {n2(bar.low)} C {n2(bar.close)}
          </span>
        )}
        <b style={{ color: colors.ema }}>{data.ema.label}</b>
        <span>{n2(emaV?.value)}</span>
      </div>

      <div className="legend" style={{ top: tops[2] + 6 }}>
        <b>Volume</b>
        <span>{volV ? compact.format(volV.value) : "–"}</span>
      </div>

      <div className="legend" style={{ top: tops[3] + 6 }}>
        <b style={{ color: colors.macd }}>MACD</b>
        <span>{n2(macdV?.macd)}</span>
        <b style={{ color: colors.signal }}>Signal</b>
        <span>{n2(macdV?.signal)}</span>
        <b>Hist</b>
        <span>{n2(macdV?.hist)}</span>
      </div>
    </div>
  );
}
