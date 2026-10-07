import { useEffect, useRef } from "react";
import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";
import type { ChartData, ChartType } from "./api";

const C = {
  bg: "#0f1419",
  text: "#9aa5b1",
  grid: "#1b222b",
  up: "#26a69a",
  down: "#ef5350",
  upFaint: "rgba(38,166,154,0.45)",
  downFaint: "rgba(239,83,80,0.45)",
  rsi: "#b794f4",
  price: "#4da3ff",
  macd: "#4da3ff",
  signal: "#f6ad55",
};

// Relative pane heights, top to bottom: RSI, price, volume, MACD.
// Stretch factors keep these proportions when the window resizes.
const STRETCH = [1.2, 5, 1, 1.6];

interface Series {
  rsi: ISeriesApi<"Line">;
  candles: ISeriesApi<"Candlestick">;
  line: ISeriesApi<"Line">;
  volume: ISeriesApi<"Histogram">;
  hist: ISeriesApi<"Histogram">;
  macd: ISeriesApi<"Line">;
  signal: ISeriesApi<"Line">;
}

export default function StockChart({ data, chartType }: { data: ChartData; chartType: ChartType }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<Series | null>(null);

  // Create the chart once
  useEffect(() => {
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

    // Add in pane order: 0 RSI, 1 price, 2 volume, 3 MACD
    const rsi = chart.addSeries(LineSeries, { color: C.rsi, lineWidth: 2, priceLineVisible: false, title: "RSI 14" }, 0);
    rsi.createPriceLine({ price: 70, color: C.down, lineStyle: 2, lineWidth: 1, axisLabelVisible: false });
    rsi.createPriceLine({ price: 30, color: C.up, lineStyle: 2, lineWidth: 1, axisLabelVisible: false });

    const candles = chart.addSeries(
      CandlestickSeries,
      { upColor: C.up, downColor: C.down, borderVisible: false, wickUpColor: C.up, wickDownColor: C.down },
      1
    );
    const line = chart.addSeries(LineSeries, { color: C.price, lineWidth: 2, visible: false }, 1);
    const volume = chart.addSeries(
      HistogramSeries,
      { priceFormat: { type: "volume" }, priceLineVisible: false, lastValueVisible: false },
      2
    );
    const hist = chart.addSeries(HistogramSeries, { priceLineVisible: false, lastValueVisible: false }, 3);
    const macd = chart.addSeries(LineSeries, { color: C.macd, lineWidth: 2, priceLineVisible: false, title: "MACD" }, 3);
    const signal = chart.addSeries(LineSeries, { color: C.signal, lineWidth: 2, priceLineVisible: false, title: "Signal" }, 3);

    chart.panes().forEach((pane, i) => pane.setStretchFactor(STRETCH[i]));

    chartRef.current = chart;
    seriesRef.current = { rsi, candles, line, volume, hist, macd, signal };

    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  // Push new data whenever ticker/timeframe changes
  useEffect(() => {
    const s = seriesRef.current;
    const chart = chartRef.current;
    if (!s || !chart) return;

    chart.applyOptions({ timeScale: { timeVisible: data.intraday, secondsVisible: false } });

    s.candles.setData(data.candles.map((d) => ({ ...d, time: d.time as Time })));
    s.line.setData(data.candles.map((d) => ({ time: d.time as Time, value: d.close })));
    s.volume.setData(
      data.volume.map((d) => ({ time: d.time as Time, value: d.value, color: d.up ? C.upFaint : C.downFaint }))
    );
    s.rsi.setData(data.rsi.map((d) => ({ time: d.time as Time, value: d.value })));
    s.macd.setData(data.macd.map((d) => ({ time: d.time as Time, value: d.macd })));
    s.signal.setData(data.macd.map((d) => ({ time: d.time as Time, value: d.signal })));
    s.hist.setData(
      data.macd.map((d) => ({ time: d.time as Time, value: d.hist, color: d.hist >= 0 ? C.upFaint : C.downFaint }))
    );
    chart.timeScale().fitContent();
  }, [data]);

  // Candles <-> line
  useEffect(() => {
    const s = seriesRef.current;
    if (!s) return;
    s.candles.applyOptions({ visible: chartType === "candles" });
    s.line.applyOptions({ visible: chartType === "line" });
  }, [chartType]);

  return <div ref={containerRef} className="chart" />;
}
