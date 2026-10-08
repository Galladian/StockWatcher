import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CURRENCIES, fetchBreakdown, type Mover } from "./portfolioApi";

const PALETTE = ["#4da3ff", "#26a69a", "#f6ad55", "#b794f4", "#ef5350", "#ffd54f", "#7bd389", "#ff8fab", "#5fd0e0", "#c7a27c", "#e38b4f", "#8fa8ff"];
const GREY: Record<string, string> = { Cash: "#6b7785", Unknown: "#46505c", "ETFs and funds": "#8a96a3", Funds: "#8a96a3" };

const money = (v: number, ccy: string) =>
  new Intl.NumberFormat("en-NZ", { style: "currency", currency: ccy, maximumFractionDigits: 0 }).format(v);
const signedMoney = (v: number, ccy: string) => `${v >= 0 ? "+" : "-"}${money(Math.abs(v), ccy)}`;
const pct = (v: number, d = 1) => `${v.toFixed(d)}%`;
const signedPct = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
const tone = (v: number) => (v >= 0 ? "pos" : "neg");

function Donut({
  slices, colors, hover, onHover, centerTop, centerMain,
}: {
  slices: { name: string; weight: number }[];
  colors: Record<string, string>;
  hover: string | null;
  onHover: (name: string | null) => void;
  centerTop: string;
  centerMain: string;
}) {
  const size = 240, c = size / 2, r = 86, sw = 30, circ = 2 * Math.PI * r;
  let acc = 0;
  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="donut" role="img" aria-label="Portfolio split by sector">
      <circle cx={c} cy={c} r={r} fill="none" stroke="var(--line)" strokeWidth={sw} />
      {slices.map((s) => {
        const len = circ * (s.weight / 100);
        const shown = Math.max(len - (slices.length > 1 ? 2 : 0), 0);
        const el = (
          <circle
            key={s.name}
            cx={c} cy={c} r={r} fill="none"
            stroke={colors[s.name]}
            strokeWidth={hover === s.name ? sw + 6 : sw}
            strokeDasharray={`${shown} ${circ - shown}`}
            strokeDashoffset={-acc}
            transform={`rotate(-90 ${c} ${c})`}
            opacity={hover && hover !== s.name ? 0.35 : 1}
            onMouseEnter={() => onHover(s.name)}
            onMouseLeave={() => onHover(null)}
          />
        );
        acc += len;
        return el;
      })}
      <text x={c} y={c - 6} textAnchor="middle" className="donut-top">{centerTop}</text>
      <text x={c} y={c + 16} textAnchor="middle" className="donut-main">{centerMain}</text>
    </svg>
  );
}

function MoverLine({ label, m, ccy }: { label: string; m: Mover | null; ccy: string }) {
  if (!m) return null;
  return (
    <div className="m-row">
      <span className="m-label">{label}</span>
      <span className={`m-value ${tone(m.pct)}`}>
        {m.ticker} {signedPct(m.pct)} <span className="muted">({signedMoney(m.amount, ccy)})</span>
      </span>
    </div>
  );
}

export default function Breakdown({ currency, onCurrency }: { currency: string; onCurrency: (c: string) => void }) {
  const [hover, setHover] = useState<string | null>(null);
  const { data, error, isLoading } = useQuery({
    queryKey: ["breakdown", currency],
    queryFn: () => fetchBreakdown(currency),
    staleTime: 15_000,
    placeholderData: (prev) => prev,
  });

  if (isLoading) return <p className="muted">Loading breakdown…</p>;
  if (error || !data) return <p className="form-error">{(error as Error)?.message ?? "Couldn't load the breakdown"}</p>;
  if (data.sectors.length === 0)
    return <div className="empty">Nothing to break down yet. Add a buy or some cash and it will show up here.</div>;

  const ccy = data.currency;
  const colors: Record<string, string> = {};
  let i = 0;
  for (const s of data.sectors) colors[s.name] = GREY[s.name] ?? PALETTE[i++ % PALETTE.length];
  const hovered = data.sectors.find((s) => s.name === hover);
  const { concentration: con, characteristics: ch, performance: perf } = data;

  return (
    <>
      <div className="section-head">
        <h2>Sector allocation</h2>
        <label className="muted">
          Values in{" "}
          <select className="ccy" value={currency} onChange={(e) => onCurrency(e.target.value)} aria-label="Display currency">
            {CURRENCIES.map((c) => <option key={c}>{c}</option>)}
          </select>
        </label>
      </div>

      <div className="card alloc">
        <Donut
          slices={data.sectors}
          colors={colors}
          hover={hover}
          onHover={setHover}
          centerTop={hovered ? hovered.name : "Total value"}
          centerMain={hovered ? pct(hovered.weight) : money(data.total_value, ccy)}
        />
        <div className="table-wrap">
          <table className="ledger">
            <thead>
              <tr><th>Sector</th><th className="num">Share</th><th className="num">Value</th><th>Holdings</th></tr>
            </thead>
            <tbody>
              {data.sectors.map((s) => (
                <tr key={s.name} className={hover === s.name ? "hl" : ""} onMouseEnter={() => setHover(s.name)} onMouseLeave={() => setHover(null)}>
                  <td><span className="swatch" style={{ background: colors[s.name] }} />{s.name}</td>
                  <td className="num">{pct(s.weight)}</td>
                  <td className="num">{money(s.value, ccy)}</td>
                  <td className="muted wrap-cell">{s.holdings.map((h) => h.ticker).join(", ") || "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {data.warnings.length > 0 && <div className="notice">{data.warnings.map((w) => <div key={w}>{w}</div>)}</div>}

      <h2>Worth noting</h2>
      <div className="card">
        {data.observations.map((o) => <div key={o.text} className={`obs ${o.tone}`}>{o.text}</div>)}
      </div>

      <div className="breakdown-cards">
        <div className="card">
          <h3 className="card-title">Concentration</h3>
          <div className="m-row"><span className="m-label">Stocks held</span><span className="m-value">{con.holdings_count}</span></div>
          {con.top && <div className="m-row"><span className="m-label">Largest holding</span><span className="m-value">{con.top.ticker} ({pct(con.top.weight)})</span></div>}
          <div className="m-row"><span className="m-label">Top 3 holdings</span><span className="m-value">{pct(con.top3)}</span></div>
          <div className="m-row"><span className="m-label">Top 5 holdings</span><span className="m-value">{pct(con.top5)}</span></div>
          {con.largest_sector && <div className="m-row"><span className="m-label">Largest sector</span><span className="m-value">{con.largest_sector.name} ({pct(con.largest_sector.weight)})</span></div>}
          {con.effective_n !== null && (
            <div className="m-row">
              <span className="m-label" title="How many equally sized holdings would be as concentrated as yours. Lower means more concentrated.">Effective number of stocks</span>
              <span className="m-value">{con.effective_n.toFixed(1)}</span>
            </div>
          )}
        </div>

        <div className="card">
          <h3 className="card-title">Characteristics</h3>
          <div className="m-row">
            <span className="m-label" title="Weighted by value. Above 1 means the stocks swing more than the market.">Beta</span>
            <span className="m-value">{ch.beta === null ? "–" : ch.beta.toFixed(2)}</span>
          </div>
          <div className="m-row">
            <span className="m-label" title="Weighted by value, the way a fund would calculate it.">Forward P/E</span>
            <span className="m-value">{ch.forward_pe === null ? "–" : ch.forward_pe.toFixed(1)}</span>
          </div>
          <div className="m-row">
            <span className="m-label" title="Based on each stock's current annual dividend and the shares you hold.">Estimated dividends per year</span>
            <span className="m-value">{ch.dividend_payers ? money(ch.dividend_income, ccy) : "None"}</span>
          </div>
          {ch.dividend_payers > 0 && ch.dividend_yield !== null && (
            <div className="m-row"><span className="m-label">Dividend yield on stocks</span><span className="m-value">{pct(ch.dividend_yield, 2)}</span></div>
          )}
          {(ch.beta_coverage !== null && ch.beta_coverage < 99.5) || (ch.pe_coverage !== null && ch.pe_coverage < 99.5) ? (
            <p className="panel-note">Beta and P/E only cover the holdings that report them.</p>
          ) : null}
        </div>

        <div className="card">
          <h3 className="card-title">Performance</h3>
          <div className="m-row"><span className="m-label">In profit</span><span className="m-value pos">{perf.winners}</span></div>
          <div className="m-row"><span className="m-label">At a loss</span><span className="m-value neg">{perf.losers}</span></div>
          <MoverLine label="Best since buying" m={perf.best} ccy={ccy} />
          <MoverLine label="Worst since buying" m={perf.worst} ccy={ccy} />
          <MoverLine label="Best today" m={perf.day_best} ccy={ccy} />
          <MoverLine label="Worst today" m={perf.day_worst} ccy={ccy} />
        </div>

        <div className="card">
          <h3 className="card-title">Company size</h3>
          <div className="stack-bar" role="img" aria-label="Portfolio split by company size">
            {data.market_cap.map((m, idx) => (
              <span key={m.name} style={{ width: `${m.weight}%`, background: GREY[m.name] ?? PALETTE[idx % PALETTE.length] }} title={`${m.name}: ${pct(m.weight)}`} />
            ))}
          </div>
          {data.market_cap.map((m, idx) => (
            <div className="m-row" key={m.name}>
              <span className="m-label"><span className="swatch" style={{ background: GREY[m.name] ?? PALETTE[idx % PALETTE.length] }} />{m.name}</span>
              <span className="m-value">{pct(m.weight)}</span>
            </div>
          ))}
        </div>
      </div>

      <p className="foot">
        Shares are of your whole portfolio, cash included, except company size, which covers stocks only. ETFs are split by the
        fund's own sector weights when Yahoo provides them. Not financial advice.
      </p>
    </>
  );
}
