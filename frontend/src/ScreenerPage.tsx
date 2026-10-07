import { FormEvent, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchScreen, type CheckStatus, type ScreenCheck, type ScreenVerdict } from "./api";
import { isoToDmy } from "./dates";

const CHIP: Record<CheckStatus, string> = { good: "Good", ok: "Okay", bad: "Weak", na: "No data" };
const dmy = (s: string) => s.replace(/\d{4}-\d{2}-\d{2}/g, isoToDmy);

const usd = (v: number) => new Intl.NumberFormat("en-NZ", { style: "currency", currency: "USD" }).format(v);
const compactUsd = (v: number) =>
  new Intl.NumberFormat("en-NZ", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 2 }).format(v);

function CheckRow({ c }: { c: ScreenCheck }) {
  return (
    <div className="check">
      <span className={`chip ${c.status}`}>{CHIP[c.status]}</span>
      <div>
        <div className="name">{c.label}</div>
        {c.detail && <div className="detail">{dmy(c.detail)}</div>}
        {c.rule && <div className="rule">Rule of thumb: {c.rule}</div>}
      </div>
      <div className="val">{dmy(c.value)}</div>
    </div>
  );
}

function VerdictBanner({ title, v }: { title: string; v: ScreenVerdict }) {
  return (
    <div className={`verdict ${v.tone}`}>
      <div className="verdict-kicker">{title}</div>
      <div className="verdict-title">{v.verdict}</div>
      <div className="verdict-sub">{v.summary}</div>
    </div>
  );
}

export default function ScreenerPage() {
  const [input, setInput] = useState("");
  const [ticker, setTicker] = useState("");

  const { data, error, isFetching } = useQuery({
    queryKey: ["screener", ticker],
    queryFn: () => fetchScreen(ticker),
    enabled: ticker !== "",
    staleTime: 5 * 60_000,
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const t = input.trim().toUpperCase();
    if (t) setTicker(t);
  };

  return (
    <div className="scroll">
      <div className="wrap wide">
        <h1>Screener</h1>
        <p className="lede">Enter a US ticker to see whether it looks reasonably priced and whether the short-term setup is good.</p>

        <form className="search screen-search" onSubmit={submit}>
          <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ticker, e.g. MSFT" aria-label="Ticker symbol" spellCheck={false} autoFocus />
          <button className="primary" type="submit" disabled={!input.trim() || isFetching}>
            {isFetching ? "Screening…" : "Screen"}
          </button>
        </form>

        {error && <p className="form-error">{(error as Error).message}. Check the ticker and try again.</p>}
        {!data && !error && !isFetching && <div className="empty">Nothing screened yet. Try a ticker above.</div>}

        {data && (
          <>
            <div className="screen-head">
              <div>
                <span className="sym">{data.ticker}</span>
                {data.name && <span className="screen-name">{data.name}</span>}
              </div>
              <div className="muted">
                {[data.sector, data.industry].filter(Boolean).join(" / ")}
                {data.price !== null && <> &nbsp;|&nbsp; {usd(data.price)}</>}
                {data.market_cap !== null && <> &nbsp;|&nbsp; Market cap {compactUsd(data.market_cap)}</>}
              </div>
            </div>

            {data.warnings.length > 0 && (
              <div className="notice">{data.warnings.map((w) => <div key={w}>{w}</div>)}</div>
            )}

            <div className="screen-grid">
              {data.valuation && (
                <section>
                  <VerdictBanner title="Valuation" v={data.valuation} />
                  {data.valuation.groups.map((g) => (
                    <div key={g.title} className="card check-group">
                      <h3>{g.title}</h3>
                      {g.checks.map((c) => <CheckRow key={c.id} c={c} />)}
                    </div>
                  ))}
                </section>
              )}

              {data.short_term && (
                <section>
                  <VerdictBanner title="Short term" v={data.short_term} />
                  <div className="card check-group">
                    <h3>Entry conditions</h3>
                    {data.short_term.checks.map((c) => <CheckRow key={c.id} c={c} />)}
                  </div>
                  {data.short_term.extras.length > 0 && (
                    <div className="card check-group">
                      <h3>Also worth knowing</h3>
                      <p className="panel-note">These don't change the verdict above.</p>
                      {data.short_term.extras.map((c) => <CheckRow key={c.id} c={c} />)}
                    </div>
                  )}
                </section>
              )}
            </div>

            <p className="foot">
              A screening aid, not financial advice. Thresholds are general rules of thumb and vary by industry and
              company. Data comes from Yahoo Finance and can be incomplete or delayed. Sector averages aren't included.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
