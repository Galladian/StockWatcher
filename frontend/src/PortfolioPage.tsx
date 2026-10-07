import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import LoginForm from "./LoginForm";
import {
  addTransaction, deleteTransaction, fetchMe, fetchSummary, listTransactions,
  type Transaction, type TxType,
} from "./portfolioApi";

// ---------- formatting ----------
const usd = (v: number, max = 2) =>
  v.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: max });
const signedUsd = (v: number) => `${v >= 0 ? "+" : "-"}${usd(Math.abs(v))}`;
const signedPct = (v: number | null) => (v === null ? "–" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`);
const tone = (v: number | null) => (v === null ? "" : v >= 0 ? "pos" : "neg");
const shares = (v: number | string) => Number(v).toLocaleString("en-US", { maximumFractionDigits: 6 });

const localToday = () => {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};

function txTotal(t: Transaction): number {
  const gross = Number(t.quantity) * Number(t.price);
  const fees = Number(t.fees);
  return t.type === "buy" ? gross + fees : t.type === "sell" ? gross - fees : gross;
}

// ---------- Holdings tab ----------
function Holdings() {
  const { data, error, isLoading, isFetching, refetch, dataUpdatedAt } = useQuery({
    queryKey: ["summary"],
    queryFn: fetchSummary,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });

  if (isLoading) return <p className="muted">Loading holdings…</p>;
  if (error || !data) return <p className="form-error">{(error as Error)?.message ?? "Couldn't load holdings"}</p>;

  const { totals: t, holdings } = data;
  if (holdings.length === 0)
    return <div className="empty">No holdings yet. Record a buy on the Transactions tab and it will show up here.</div>;

  const updated = dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";

  return (
    <>
      <div className="stats">
        <div className="card stat">
          <div className="label">Total value</div>
          <div className="value">{usd(t.market_value)}</div>
          <div className="sub">Cost basis {usd(t.cost_basis)}</div>
        </div>
        <div className="card stat">
          <div className="label">Day change</div>
          <div className={`value ${tone(t.day_change)}`}>{signedUsd(t.day_change)}</div>
          <div className={`sub ${tone(t.day_change_pct)}`}>{signedPct(t.day_change_pct)}</div>
        </div>
        <div className="card stat">
          <div className="label">Unrealized profit and loss</div>
          <div className={`value ${tone(t.unrealized)}`}>{signedUsd(t.unrealized)}</div>
          <div className={`sub ${tone(t.unrealized_pct)}`}>{signedPct(t.unrealized_pct)} on cost</div>
        </div>
        <div className="card stat">
          <div className="label">Total return</div>
          <div className={`value ${tone(t.total_return)}`}>{signedUsd(t.total_return)}</div>
          <div className="sub">
            Includes {signedUsd(t.realized)} realized and {usd(t.dividends)} dividends
          </div>
        </div>
      </div>

      {data.warnings.length > 0 && (
        <div className="notice">
          {data.warnings.map((w) => <div key={w}>{w}</div>)}
        </div>
      )}

      <div className="card table-wrap holdings">
        <table className="ledger">
          <thead>
            <tr>
              <th>Ticker</th>
              <th className="num">Shares</th>
              <th className="num">Avg cost</th>
              <th className="num">Price</th>
              <th className="num">Day change</th>
              <th className="num">Market value</th>
              <th>Weight</th>
              <th className="num">Unrealized P&amp;L</th>
            </tr>
          </thead>
          <tbody>
            {holdings.map((h) => (
              <tr key={h.ticker}>
                <td><b>{h.ticker}</b></td>
                <td className="num">{shares(h.shares)}</td>
                <td className="num">{usd(h.avg_cost, 4)}</td>
                <td className="num">{h.price === null ? "–" : usd(h.price, 4)}</td>
                <td className={`num ${tone(h.day_change)}`}>
                  {h.day_change === null ? "–" : <>{signedUsd(h.day_change)}<div className="subline">{signedPct(h.day_change_pct)}</div></>}
                </td>
                <td className="num">{h.market_value === null ? "–" : usd(h.market_value)}</td>
                <td>
                  {h.weight === null ? "–" : (
                    <span className="weight">
                      <span className="wbar"><span style={{ width: `${Math.min(100, h.weight)}%` }} /></span>
                      {h.weight.toFixed(1)}%
                    </span>
                  )}
                </td>
                <td className={`num ${tone(h.unrealized)}`}>
                  {h.unrealized === null ? "–" : <>{signedUsd(h.unrealized)}<div className="subline">{signedPct(h.unrealized_pct)}</div></>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="foot">
        {data.as_of ? `Prices from the ${data.as_of} session. ` : ""}
        Refreshes every minute{updated ? `, last at ${updated}` : ""}.{" "}
        <button className="linkbtn inline" onClick={() => refetch()} disabled={isFetching}>
          {isFetching ? "Refreshing…" : "Refresh now"}
        </button>
      </p>
    </>
  );
}

// ---------- Transactions tab ----------
function Transactions() {
  const qc = useQueryClient();
  const txs = useQuery({ queryKey: ["transactions"], queryFn: listTransactions });

  const [type, setType] = useState<TxType>("buy");
  const [ticker, setTicker] = useState("");
  const [date, setDate] = useState(localToday());
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [fees, setFees] = useState("");
  const [note, setNote] = useState("");

  const changed = () => {
    qc.invalidateQueries({ queryKey: ["transactions"] });
    qc.invalidateQueries({ queryKey: ["summary"] });
  };

  const add = useMutation({
    mutationFn: () => addTransaction({ ticker, type, trade_date: date, quantity, price, fees: fees || "0", note }),
    onSuccess: () => {
      changed();
      setTicker(""); setQuantity(""); setPrice(""); setFees(""); setNote("");
    },
  });
  const remove = useMutation({ mutationFn: deleteTransaction, onSuccess: changed });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    add.mutate();
  };
  const confirmDelete = (t: Transaction) => {
    if (window.confirm(`Delete this ${t.type} of ${t.ticker} on ${t.trade_date}?`)) remove.mutate(t.id);
  };

  return (
    <>
      <form className="card" onSubmit={submit}>
        <div className="grid">
          <label className="field">
            Type
            <select value={type} onChange={(e) => setType(e.target.value as TxType)}>
              <option value="buy">Buy</option>
              <option value="sell">Sell</option>
              <option value="dividend">Dividend</option>
            </select>
          </label>
          <label className="field">
            Ticker
            <input className="upper" value={ticker} onChange={(e) => setTicker(e.target.value)} placeholder="AAPL" spellCheck={false} />
          </label>
          <label className="field">
            Date
            <input type="date" value={date} max={localToday()} onChange={(e) => setDate(e.target.value)} />
          </label>
          <label className="field">
            Shares
            <input inputMode="decimal" value={quantity} onChange={(e) => setQuantity(e.target.value)} placeholder="10" />
          </label>
          <label className="field">
            {type === "dividend" ? "Dividend per share" : "Price per share"}
            <input inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="185.20" />
          </label>
          <label className="field">
            Fees
            <input inputMode="decimal" value={fees} onChange={(e) => setFees(e.target.value)} placeholder="0" />
          </label>
          <label className="field wide">
            Note (optional)
            <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} />
          </label>
          <button className="primary" type="submit" disabled={add.isPending || !ticker || !quantity || !price}>
            {add.isPending ? "Adding…" : "Add trade"}
          </button>
        </div>
        {add.error && <p className="form-error">{(add.error as Error).message}</p>}
      </form>

      <h2>Transactions</h2>
      {txs.isLoading && <p className="muted">Loading…</p>}
      {txs.error && <p className="form-error">{(txs.error as Error).message}</p>}
      {txs.data && txs.data.length === 0 && <div className="empty">No trades yet. Add your first one above.</div>}
      {txs.data && txs.data.length > 0 && (
        <div className="card table-wrap">
          <table className="ledger">
            <thead>
              <tr>
                <th>Date</th><th>Type</th><th>Ticker</th>
                <th className="num">Shares</th><th className="num">Price</th><th className="num">Fees</th><th className="num">Total</th>
                <th>Note</th><th />
              </tr>
            </thead>
            <tbody>
              {txs.data.map((t) => (
                <tr key={t.id}>
                  <td>{t.trade_date}</td>
                  <td><span className={`tag ${t.type}`}>{t.type}</span></td>
                  <td><b>{t.ticker}</b></td>
                  <td className="num">{shares(t.quantity)}</td>
                  <td className="num">{usd(Number(t.price), 4)}</td>
                  <td className="num">{Number(t.fees) ? usd(Number(t.fees)) : "–"}</td>
                  <td className="num">{usd(txTotal(t))}</td>
                  <td className="note">{t.note}</td>
                  <td><button className="del" onClick={() => confirmDelete(t)}>Delete</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

// ---------- page ----------
function PortfolioTabs() {
  const [tab, setTab] = useState<"holdings" | "transactions">("holdings");
  return (
    <div className="scroll">
      <div className="wrap">
        <h1>Portfolio</h1>
        <div className="tabs page-tabs" role="group" aria-label="Portfolio sections">
          <button className={tab === "holdings" ? "active" : ""} onClick={() => setTab("holdings")}>Holdings</button>
          <button className={tab === "transactions" ? "active" : ""} onClick={() => setTab("transactions")}>Transactions</button>
        </div>
        {tab === "holdings" ? <Holdings /> : <Transactions />}
      </div>
    </div>
  );
}

export default function PortfolioPage() {
  const me = useQuery({ queryKey: ["me"], queryFn: fetchMe, staleTime: Infinity });
  if (me.isLoading) return <div className="wrap"><p className="muted">Loading…</p></div>;
  if (!me.data?.username) return <LoginForm />;
  return <PortfolioTabs />;
}
