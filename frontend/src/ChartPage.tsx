import { FormEvent, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchChart, type ChartType, type Timeframe } from "./api";
import StockChart from "./StockChart";
import MetricsPanel from "./MetricsPanel";

const TIMEFRAMES: { id: Timeframe; label: string }[] = [
  { id: "D", label: "Daily" },
  { id: "W", label: "Weekly" },
  { id: "M", label: "Monthly" },
  { id: "Q", label: "Quarterly" },
  { id: "YTD", label: "YTD" },
  { id: "Y", label: "Annual" },
  { id: "5Y", label: "5 Year" },
];

export default function ChartPage() {
  const [input, setInput] = useState("AAPL");
  const [ticker, setTicker] = useState("AAPL");
  const [timeframe, setTimeframe] = useState<Timeframe>("Y");
  const [chartType, setChartType] = useState<ChartType>("candles");
  const [panelOpen, setPanelOpen] = useState(() => {
    try { return localStorage.getItem("metricsOpen") === "1"; } catch { return false; }
  });
  const togglePanel = () =>
    setPanelOpen((open) => {
      const next = !open;
      try { localStorage.setItem("metricsOpen", next ? "1" : "0"); } catch { /* ignore */ }
      return next;
    });

  const { data, error, isFetching } = useQuery({
    queryKey: ["chart", ticker, timeframe],
    queryFn: () => fetchChart(ticker, timeframe),
    placeholderData: (prev) => prev, // keep the old chart visible while the next loads
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const t = input.trim().toUpperCase();
    if (t) setTicker(t);
  };

  const change = data?.quote.change_pct ?? null;

  return (
    <div className="app">
      <header className="bar">
        <form onSubmit={submit} className="search">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ticker, e.g. MSFT"
            aria-label="Ticker symbol"
            spellCheck={false}
          />
          <button type="submit">Load</button>
        </form>

        <div className="quote">
          <span className="sym">{data?.ticker ?? ticker}</span>
          {data && <span className="px">{data.quote.price.toFixed(2)}</span>}
          {change !== null && (
            <span className={change >= 0 ? "pos" : "neg"}>
              {change >= 0 ? "+" : ""}
              {change.toFixed(2)}%
              <span className="muted"> {data?.quote.change_label}</span>
            </span>
          )}
        </div>

        <div className="controls">
          <div className="tabs" role="group" aria-label="Chart type">
            <button className={chartType === "candles" ? "active" : ""} onClick={() => setChartType("candles")}>
              Candles
            </button>
            <button className={chartType === "line" ? "active" : ""} onClick={() => setChartType("line")}>
              Line
            </button>
          </div>
          <div className="tabs" role="group" aria-label="Timeframe">
            {TIMEFRAMES.map((t) => (
              <button
                key={t.id}
                className={t.id === timeframe ? "active" : ""}
                onClick={() => setTimeframe(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </header>

      {error && <div className="error">{(error as Error).message}. Check the ticker and try again.</div>}
      {data && (
        <div className="caption">
          <span>{data.label}</span>
          {isFetching && <span className="loading">Loading…</span>}
        </div>
      )}
      <main className="main">
        <div className="chart-area">{data && <StockChart data={data} chartType={chartType} />}</div>
        <div className="side">
          <button className="side-tab" onClick={togglePanel} aria-expanded={panelOpen} title="Toggle metrics panel">
            <span>{panelOpen ? "›" : "‹"}</span>
            <span className="side-label">Metrics</span>
          </button>
          {panelOpen && <MetricsPanel ticker={ticker} />}
        </div>
      </main>
    </div>
  );
}
