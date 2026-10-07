import { useQuery } from "@tanstack/react-query";
import { fetchMetrics, type Metrics } from "./api";

type Fmt = "money" | "price" | "ratio" | "mult" | "pct" | "signedPct" | "num" | "date" | "text";
interface Row {
  label: string;
  key: keyof Metrics;
  fmt: Fmt;
  tip?: string;
  tone?: boolean; // color positive/negative
}
interface Section {
  title: string;
  rows: Row[];
}

const SECTIONS: Section[] = [
  {
    title: "Valuation",
    rows: [
      { label: "Market cap", key: "market_cap", fmt: "money" },
      { label: "Enterprise value", key: "enterprise_value", fmt: "money" },
      { label: "P/E (trailing)", key: "pe_trailing", fmt: "ratio", tip: "Price divided by the last 12 months of earnings per share" },
      { label: "Forward P/E", key: "pe_forward", fmt: "ratio", tip: "Price divided by analysts' expected earnings per share for the next 12 months" },
      { label: "PEG", key: "peg", fmt: "ratio", tip: "P/E divided by expected earnings growth. Around 1 is often read as fairly valued" },
      { label: "Price / sales", key: "price_to_sales", fmt: "ratio" },
      { label: "Price / book", key: "price_to_book", fmt: "ratio" },
      { label: "EV / EBITDA", key: "ev_to_ebitda", fmt: "mult" },
      { label: "EPS (trailing)", key: "eps_trailing", fmt: "price" },
      { label: "EPS (forward)", key: "eps_forward", fmt: "price" },
    ],
  },
  {
    title: "Dividend",
    rows: [
      { label: "Yield", key: "dividend_yield", fmt: "pct" },
      { label: "Annual dividend", key: "dividend_rate", fmt: "price" },
      { label: "Payout ratio", key: "payout_ratio", fmt: "pct", tip: "Share of earnings paid out as dividends" },
      { label: "Ex-dividend date", key: "ex_dividend_date", fmt: "date" },
    ],
  },
  {
    title: "Profitability",
    rows: [
      { label: "Gross margin", key: "gross_margin", fmt: "pct" },
      { label: "Operating margin", key: "operating_margin", fmt: "pct" },
      { label: "Net margin", key: "profit_margin", fmt: "pct" },
      { label: "Return on equity", key: "roe", fmt: "pct" },
      { label: "Return on assets", key: "roa", fmt: "pct" },
    ],
  },
  {
    title: "Growth and cash flow",
    rows: [
      { label: "Revenue (TTM)", key: "revenue", fmt: "money" },
      { label: "Revenue growth", key: "revenue_growth", fmt: "signedPct", tone: true, tip: "Latest quarter vs the same quarter last year" },
      { label: "Earnings growth", key: "earnings_growth", fmt: "signedPct", tone: true, tip: "Latest quarter vs the same quarter last year" },
      { label: "Free cash flow", key: "free_cash_flow", fmt: "money" },
    ],
  },
  {
    title: "Balance sheet",
    rows: [
      { label: "Cash", key: "total_cash", fmt: "money" },
      { label: "Debt", key: "total_debt", fmt: "money" },
      { label: "Debt / equity", key: "debt_to_equity", fmt: "ratio" },
      { label: "Current ratio", key: "current_ratio", fmt: "ratio", tip: "Current assets divided by current liabilities" },
    ],
  },
  {
    title: "Trading",
    rows: [
      { label: "Beta", key: "beta", fmt: "ratio", tip: "Volatility relative to the market. Above 1 moves more than the market" },
      { label: "Average volume", key: "avg_volume", fmt: "num" },
      { label: "Shares outstanding", key: "shares_outstanding", fmt: "num" },
      { label: "Short % of float", key: "short_percent_float", fmt: "pct" },
    ],
  },
];

const ANALYST_ROWS: Row[] = [
  { label: "Rating", key: "recommendation", fmt: "text" },
  { label: "Mean target", key: "target_mean", fmt: "price" },
  { label: "Upside to target", key: "target_upside", fmt: "signedPct", tone: true },
  { label: "Target low", key: "target_low", fmt: "price" },
  { label: "Target high", key: "target_high", fmt: "price" },
  { label: "Analysts", key: "analyst_count", fmt: "num" },
];

const compact = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 2 });

function format(v: unknown, f: Fmt): string {
  if (v === null || v === undefined || v === "") return "–";
  if (typeof v === "string") return v;
  if (typeof v !== "number") return "–";
  switch (f) {
    case "money": return `${v < 0 ? "-" : ""}$${compact.format(Math.abs(v))}`;
    case "price": return `$${v.toFixed(2)}`;
    case "ratio": return v.toFixed(2);
    case "mult": return `${v.toFixed(2)}x`;
    case "pct": return `${(v * 100).toFixed(2)}%`;
    case "signedPct": return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(2)}%`;
    case "num": return compact.format(v);
    default: return String(v);
  }
}

function RowView({ row, m }: { row: Row; m: Metrics }) {
  const v = m[row.key];
  const tone = row.tone && typeof v === "number" ? (v >= 0 ? "pos" : "neg") : "";
  return (
    <div className="m-row">
      <span className="m-label" title={row.tip}>{row.label}</span>
      <span className={`m-value ${tone}`}>{format(v, row.fmt)}</span>
    </div>
  );
}

function hasData(rows: Row[], m: Metrics) {
  return rows.some((r) => m[r.key] !== null && m[r.key] !== undefined);
}

function RangeBar({ low, high, price }: { low: number; high: number; price: number }) {
  const pos = high > low ? Math.min(1, Math.max(0, (price - low) / (high - low))) : 0.5;
  return (
    <div className="range" title="Where the current price sits in its 52-week range">
      <div className="range-head">
        <span>52-week range</span>
        <span>{(pos * 100).toFixed(0)}% of range</span>
      </div>
      <div className="range-track">
        <div className="range-dot" style={{ left: `${pos * 100}%` }} />
      </div>
      <div className="range-ends">
        <span>${low.toFixed(2)}</span>
        <span>${high.toFixed(2)}</span>
      </div>
    </div>
  );
}

export default function MetricsPanel({ ticker }: { ticker: string }) {
  const { data: m, error, isLoading } = useQuery({
    queryKey: ["metrics", ticker],
    queryFn: () => fetchMetrics(ticker),
    staleTime: 15 * 60_000,
  });

  if (isLoading) return <aside className="panel"><p className="panel-note">Loading metrics…</p></aside>;
  if (error || !m)
    return (
      <aside className="panel">
        <p className="panel-note">{(error as Error)?.message ?? "Metrics unavailable"}</p>
      </aside>
    );

  const paysDividend = m.dividend_rate !== null || m.dividend_yield !== null;
  const meta = [m.sector, m.industry].filter(Boolean).join(" / ");

  return (
    <aside className="panel">
      <div className="panel-head">
        <div className="panel-name">{m.name ?? m.ticker}</div>
        <div className="panel-meta">{[m.ticker, m.exchange].filter(Boolean).join(" on ")}</div>
        {meta && <div className="panel-meta">{meta}</div>}
      </div>

      {m.week52_low !== null && m.week52_high !== null && m.price !== null && (
        <RangeBar low={m.week52_low} high={m.week52_high} price={m.price} />
      )}

      {SECTIONS.map((s) => {
        if (s.title === "Dividend" && !paysDividend)
          return (
            <section key={s.title} className="m-section">
              <h3>{s.title}</h3>
              <p className="panel-note">Doesn't pay a dividend.</p>
            </section>
          );
        if (!hasData(s.rows, m)) return null;
        return (
          <section key={s.title} className="m-section">
            <h3>{s.title}</h3>
            {s.rows.map((r) => <RowView key={r.key} row={r} m={m} />)}
          </section>
        );
      })}

      {hasData(ANALYST_ROWS, m) && (
        <section className="m-section">
          <h3>Analyst view</h3>
          {ANALYST_ROWS.map((r) => <RowView key={r.key} row={r} m={m} />)}
        </section>
      )}

      <p className="panel-foot">Data from Yahoo Finance. Some fields may be missing or delayed.</p>
    </aside>
  );
}
