import { FormEvent, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchChart, type Timeframe } from "./api";
import StockChart from "./StockChart";

const TIMEFRAMES: { id: Timeframe; label: string }[] = [
  { id: "D", label: "Daily" },
  { id: "W", label: "Weekly" },
  { id: "M", label: "Monthly" },
  { id: "Q", label: "Quarterly" },
  { id: "Y", label: "Annual" },
  { id: "5Y", label: "5 Year" },
];

export default function App() {
  const [input, setInput] = useState("AAPL");
  const [ticker, setTicker] = useState("AAPL");
  const [timeframe, setTimeframe] = useState<Timeframe>("D");

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

  const last = data?.candles.at(-1);
  const prev = data?.candles.at(-2);
  const change = last && prev ? ((last.close - prev.close) / prev.close) * 100 : null;

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
          {last && <span className="px">{last.close.toFixed(2)}</span>}
          {change !== null && (
            <span className={change >= 0 ? "pos" : "neg"}>
              {change >= 0 ? "+" : ""}
              {change.toFixed(2)}%
            </span>
          )}
          {isFetching && <span className="muted">Loading…</span>}
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
      </header>

      {error && <div className="error">{(error as Error).message}. Check the ticker and try again.</div>}
      <main className="main">{data && <StockChart data={data} />}</main>
    </div>
  );
}
