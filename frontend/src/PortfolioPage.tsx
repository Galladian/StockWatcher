import { FormEvent, Fragment, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Breakdown from "./Breakdown";
import Performance from "./Performance";
import { usePrefs } from "./prefs";
import LoginForm from "./LoginForm";
import { isoToDmy, localTodayIso, maskDmy, parseDmy } from "./dates";
import {
  CURRENCIES, addCash, addTransaction, deleteCash, deleteTransaction, fetchMe, fetchSummary,
  listTransactions, updateCash, updateTransaction, type CashAccount, type Transaction, type TxType,
} from "./portfolioApi";

// ---------- formatting ----------
const money = (v: number, ccy: string, max = 2) =>
  new Intl.NumberFormat("en-NZ", { style: "currency", currency: ccy, maximumFractionDigits: max }).format(v);
const signedMoney = (v: number, ccy: string) => `${v >= 0 ? "+" : "-"}${money(Math.abs(v), ccy)}`;
const signedPct = (v: number | null) => (v === null ? "–" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`);
const tone = (v: number | null) => (v === null ? "" : v >= 0 ? "pos" : "neg");
const shares = (v: number | string) => Number(v).toLocaleString("en-US", { maximumFractionDigits: 6 });

function txTotal(t: Transaction): number {
  const gross = Number(t.quantity) * Number(t.price);
  const fees = Number(t.fees);
  return t.type === "buy" ? gross + fees : t.type === "sell" ? gross - fees : gross;
}

// ---------- Cash ----------
function CashRow({ c, shown, onChanged }: { c: CashAccount; shown: string; onChanged: () => void }) {
  const [editing, setEditing] = useState(false);
  const [label, setLabel] = useState(c.label);
  const [currency, setCurrency] = useState(c.currency);
  const [amount, setAmount] = useState(String(c.amount));

  const save = useMutation({
    mutationFn: () => updateCash(c.id, { label, currency, amount: amount.replace(/,/g, "") }),
    onSuccess: () => { setEditing(false); onChanged(); },
  });
  const remove = useMutation({ mutationFn: () => deleteCash(c.id), onSuccess: onChanged });

  if (editing)
    return (
      <tr>
        <td><input value={label} onChange={(e) => setLabel(e.target.value)} maxLength={60} aria-label="Account name" /></td>
        <td>
          <select value={currency} onChange={(e) => setCurrency(e.target.value)} aria-label="Currency">
            {CURRENCIES.map((x) => <option key={x}>{x}</option>)}
          </select>
        </td>
        <td className="num"><input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} aria-label="Amount" /></td>
        <td colSpan={2}>{save.error && <span className="form-error">{(save.error as Error).message}</span>}</td>
        <td className="actions">
          <button className="del" onClick={() => save.mutate()} disabled={save.isPending || !amount}>Save</button>{" "}
          <button className="del" onClick={() => setEditing(false)}>Cancel</button>
        </td>
      </tr>
    );

  return (
    <tr>
      <td>{c.label}</td>
      <td>{c.currency}</td>
      <td className="num">{money(c.amount, c.currency)}</td>
      <td className="num">{c.value === null ? "–" : money(c.value, shown)}</td>
      <td>{c.weight === null ? "–" : `${c.weight.toFixed(1)}%`}</td>
      <td className="actions">
        <button className="del" onClick={() => setEditing(true)}>Edit</button>{" "}
        <button className="del" onClick={() => { if (window.confirm(`Delete "${c.label}"?`)) remove.mutate(); }}>Delete</button>
      </td>
    </tr>
  );
}

function CashSection({ cash, shown, total }: { cash: CashAccount[]; shown: string; total: number }) {
  const qc = useQueryClient();
  const changed = () => {
    qc.invalidateQueries({ queryKey: ["summary"] });
    qc.invalidateQueries({ queryKey: ["breakdown"] });
  };
  const [label, setLabel] = useState("");
  const { defaultCurrency } = usePrefs();
  const [currency, setCurrency] = useState(defaultCurrency);
  const [amount, setAmount] = useState("");

  const add = useMutation({
    mutationFn: () => addCash({ label, currency, amount: amount.replace(/,/g, "") }),
    onSuccess: () => { changed(); setLabel(""); setAmount(""); },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    add.mutate();
  };

  return (
    <section className="cash">
      <div className="section-head">
        <h2>Cash</h2>
        {cash.length > 0 && <span className="muted">{money(total, shown)} in total</span>}
      </div>

      {cash.length > 0 && (
        <div className="card table-wrap">
          <table className="ledger">
            <thead>
              <tr>
                <th>Account</th><th>Currency</th><th className="num">Amount</th>
                <th className="num">In {shown}</th><th>Weight</th><th />
              </tr>
            </thead>
            <tbody>
              {cash.map((c) => <CashRow key={`${c.id}-${c.label}-${c.currency}-${c.amount}`} c={c} shown={shown} onChanged={changed} />)}
            </tbody>
          </table>
        </div>
      )}

      <form className="card cash-form" onSubmit={submit}>
        <div className="grid">
          <label className="field">
            Account name (optional)
            <input value={label} onChange={(e) => setLabel(e.target.value)} maxLength={60} placeholder="Brokerage cash" />
          </label>
          <label className="field">
            Currency
            <select value={currency} onChange={(e) => setCurrency(e.target.value)}>
              {CURRENCIES.map((x) => <option key={x}>{x}</option>)}
            </select>
          </label>
          <label className="field">
            Amount
            <input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="5000" />
          </label>
          <button className="primary" type="submit" disabled={add.isPending || !amount}>
            {add.isPending ? "Adding…" : "Add cash"}
          </button>
        </div>
        {add.error && <p className="form-error">{(add.error as Error).message}</p>}
      </form>
    </section>
  );
}

// ---------- Holdings tab ----------
function Holdings({ currency, pickCurrency }: { currency: string; pickCurrency: (c: string) => void }) {

  const { data, error, isLoading, isFetching, refetch, dataUpdatedAt } = useQuery({
    queryKey: ["summary", currency],
    queryFn: () => fetchSummary(currency),
    staleTime: 30_000,
    refetchInterval: 60_000,
    placeholderData: (prev) => prev, // keep the old figures on screen while a new currency loads
  });

  if (isLoading) return <p className="muted">Loading holdings…</p>;
  if (error || !data) return <p className="form-error">{(error as Error)?.message ?? "Couldn't load holdings"}</p>;

  const { totals: t, holdings, cash } = data;
  const shown = data.currency;
  const hasAnything = holdings.length > 0 || cash.length > 0;
  const updated = dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";

  return (
    <>
      {hasAnything && (
        <div className="stats">
          <div className="card stat">
            <div className="label-row">
              <span className="label">Total value</span>
              <select className="ccy" value={currency} onChange={(e) => pickCurrency(e.target.value)} aria-label="Display currency">
                {CURRENCIES.map((c) => <option key={c}>{c}</option>)}
              </select>
            </div>
            <div className="value">{money(t.total_value, shown)}</div>
            <div className="sub">Stocks {money(t.market_value, shown)}, cash {money(t.cash, shown)}</div>
          </div>
          <div className="card stat">
            <div className="label">Day change</div>
            <div className={`value ${tone(t.day_change)}`}>{signedMoney(t.day_change, shown)}</div>
            <div className={`sub ${tone(t.day_change_pct)}`}>{signedPct(t.day_change_pct)} on your stocks</div>
          </div>
          <div className="card stat">
            <div className="label">Unrealised profit and loss</div>
            <div className={`value ${tone(t.unrealized)}`}>{signedMoney(t.unrealized, shown)}</div>
            <div className={`sub ${tone(t.unrealized_pct)}`}>{signedPct(t.unrealized_pct)} on cost</div>
          </div>
          <div className="card stat">
            <div className="label">Total return</div>
            <div className={`value ${tone(t.total_return)}`}>{signedMoney(t.total_return, shown)}</div>
            <div className="sub">
              Includes {signedMoney(t.realized, shown)} realised and {money(t.dividends, shown)} dividends
            </div>
          </div>
        </div>
      )}

      {data.warnings.length > 0 && (
        <div className="notice">
          {data.warnings.map((w) => <div key={w}>{w}</div>)}
        </div>
      )}

      {holdings.length === 0 ? (
        <div className="empty">No stock holdings yet. Record a buy on the Transactions tab and it will show up here.</div>
      ) : (
        <div className="card table-wrap holdings sticky-head">
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
                <th className="num">Unrealised P&amp;L</th>
              </tr>
            </thead>
            <tbody>
              {holdings.map((h) => (
                <tr key={h.ticker}>
                  <td><b>{h.ticker}</b></td>
                  <td className="num">{shares(h.shares)}</td>
                  <td className="num">{money(h.avg_cost, shown, 4)}</td>
                  <td className="num">{h.price === null ? "–" : money(h.price, shown, 4)}</td>
                  <td className={`num ${tone(h.day_change)}`}>
                    {h.day_change === null ? "–" : <>{signedMoney(h.day_change, shown)}<div className="subline">{signedPct(h.day_change_pct)}</div></>}
                  </td>
                  <td className="num">{h.market_value === null ? "–" : money(h.market_value, shown)}</td>
                  <td>
                    {h.weight === null ? "–" : (
                      <span className="weight">
                        <span className="wbar"><span style={{ width: `${Math.min(100, h.weight)}%` }} /></span>
                        {h.weight.toFixed(1)}%
                      </span>
                    )}
                  </td>
                  <td className={`num ${tone(h.unrealized)}`}>
                    {h.unrealized === null ? "–" : <>{signedMoney(h.unrealized, shown)}<div className="subline">{signedPct(h.unrealized_pct)}</div></>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <CashSection cash={cash} shown={shown} total={t.cash} />

      <p className="foot">
        {data.as_of ? `Stock prices from the ${isoToDmy(data.as_of)} session. ` : ""}
        {data.fx_rate ? `Converted at 1 USD = ${data.fx_rate.toFixed(4)} ${shown}; gains don't include currency moves since you bought. ` : ""}
        Refreshes every minute{updated ? `, last at ${updated}` : ""}.{" "}
        <button className="linkbtn inline" onClick={() => refetch()} disabled={isFetching}>
          {isFetching ? "Refreshing…" : "Refresh now"}
        </button>
      </p>
    </>
  );
}

// ---------- Transactions tab ----------
const RECENT_LIMIT = 10;

function Transactions() {
  const qc = useQueryClient();
  const txs = useQuery({ queryKey: ["transactions"], queryFn: listTransactions });

  const [editingId, setEditingId] = useState<number | null>(null);
  const [type, setType] = useState<TxType>("buy");
  const [ticker, setTicker] = useState("");
  const [dateText, setDateText] = useState(isoToDmy(localTodayIso()));
  const date = parseDmy(dateText); // ISO string, or null while it isn't a valid date
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [fees, setFees] = useState("");
  const [note, setNote] = useState("");
  const [openNotes, setOpenNotes] = useState<Set<number>>(new Set());
  const [query, setQuery] = useState("");
  const [showAll, setShowAll] = useState(false);
  const pickerRef = useRef<HTMLInputElement>(null);
  const formRef = useRef<HTMLFormElement>(null);

  const editing = editingId !== null;
  const clean = (v: string) => v.replace(/,/g, "");

  const resetForm = () => {
    setEditingId(null);
    setType("buy");
    setTicker("");
    setDateText(isoToDmy(localTodayIso()));
    setQuantity(""); setPrice(""); setFees(""); setNote("");
  };

  const changed = () => {
    qc.invalidateQueries({ queryKey: ["transactions"] });
    qc.invalidateQueries({ queryKey: ["summary"] });
    qc.invalidateQueries({ queryKey: ["breakdown"] });
    qc.invalidateQueries({ queryKey: ["history"] });
  };

  const save = useMutation({
    mutationFn: () => {
      const body = {
        ticker, type, trade_date: date ?? "", quantity: clean(quantity), price: clean(price),
        fees: clean(fees) || "0", note,
      };
      return editingId === null ? addTransaction(body) : updateTransaction(editingId, body);
    },
    onSuccess: () => {
      changed();
      if (editing) resetForm();
      else { setTicker(""); setQuantity(""); setPrice(""); setFees(""); setNote(""); } // keep type and date for quick repeat entry
    },
  });

  const remove = useMutation({ mutationFn: deleteTransaction, onSuccess: changed });

  const startEdit = (t: Transaction) => {
    save.reset();
    setEditingId(t.id);
    setType(t.type);
    setTicker(t.ticker);
    setDateText(isoToDmy(t.trade_date));
    setQuantity(t.quantity);
    setPrice(t.price);
    setFees(Number(t.fees) ? t.fees : "");
    setNote(t.note ?? "");
    formRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  };

  const confirmDelete = (t: Transaction) => {
    if (!window.confirm(`Delete this ${t.type} of ${t.ticker} on ${isoToDmy(t.trade_date)}?`)) return;
    if (editingId === t.id) resetForm();
    remove.mutate(t.id);
  };

  const toggleNote = (id: number) =>
    setOpenNotes((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });

  // newest first already; show the latest few unless the person asks for everything
  const needle = query.trim().toUpperCase();
  const filtered = (txs.data ?? []).filter((t) => !needle || t.ticker.includes(needle));
  const visible = showAll ? filtered : filtered.slice(0, RECENT_LIMIT);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate();
  };

  return (
    <>
      <form ref={formRef} className={`card${editing ? " editing" : ""}`} onSubmit={submit}>
        {editing && <p className="editing-banner">Editing a trade. Save your changes or cancel.</p>}
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
          <div className="field">
            <label htmlFor="trade-date">Date</label>
            <div className="date-row">
              <input
                id="trade-date"
                inputMode="numeric"
                placeholder="DD/MM/YYYY"
                value={dateText}
                onChange={(e) => setDateText(maskDmy(e.target.value))}
                aria-invalid={dateText.length === 10 && !date}
              />
              <button
                type="button"
                className="cal"
                aria-label="Pick a date from a calendar"
                onClick={() => { try { pickerRef.current?.showPicker(); } catch { /* unsupported browser */ } }}
              >
                &#128197;
              </button>
              <input
                ref={pickerRef}
                className="hidden-date"
                type="date"
                tabIndex={-1}
                aria-hidden="true"
                max={localTodayIso()}
                value={date ?? ""}
                onChange={(e) => e.target.value && setDateText(isoToDmy(e.target.value))}
              />
            </div>
          </div>
          <label className="field">
            Shares
            <input inputMode="decimal" value={quantity} onChange={(e) => setQuantity(e.target.value)} placeholder="10" />
          </label>
          <label className="field">
            {type === "dividend" ? "Dividend per share (USD)" : "Price per share (USD)"}
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
          <div className="form-actions">
            <button className="primary" type="submit" disabled={save.isPending || !ticker || !quantity || !price || !date}>
              {editing ? (save.isPending ? "Saving…" : "Save changes") : (save.isPending ? "Adding…" : "Add trade")}
            </button>
            {editing && <button type="button" onClick={resetForm}>Cancel</button>}
          </div>
        </div>
        {dateText.length === 10 && !date && (
          <p className="form-error">Enter a real date as DD/MM/YYYY that isn't in the future.</p>
        )}
        <p className="hint">
          Already own the shares? Enter the date you bought them, or your best estimate. Day change counts shares from the date you enter.
        </p>
        {save.error && <p className="form-error">{(save.error as Error).message}</p>}
      </form>

      <div className="section-head">
        <h2>Transactions</h2>
        <input
          type="search"
          className="tx-search"
          placeholder="Search by ticker"
          aria-label="Search transactions by ticker"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          spellCheck={false}
        />
      </div>
      {txs.isLoading && <p className="muted">Loading…</p>}
      {txs.error && <p className="form-error">{(txs.error as Error).message}</p>}
      {txs.data && txs.data.length === 0 && <div className="empty">No trades yet. Add your first one above.</div>}
      {txs.data && txs.data.length > 0 && filtered.length === 0 && <div className="empty">No trades match "{query.trim()}".</div>}
      {txs.data && filtered.length > 0 && (
        <div className="card table-wrap sticky-head">
          <table className="ledger">
            <thead>
              <tr>
                <th>Date</th><th>Type</th><th>Ticker</th>
                <th className="num">Shares</th><th className="num">Price</th><th className="num">Fees</th><th className="num">Total</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {visible.map((t) => {
                const open = openNotes.has(t.id);
                return (
                  <Fragment key={t.id}>
                    <tr className={editingId === t.id ? "editing-row" : ""}>
                      <td>{isoToDmy(t.trade_date)}</td>
                      <td><span className={`tag ${t.type}`}>{t.type}</span></td>
                      <td><b>{t.ticker}</b></td>
                      <td className="num">{shares(t.quantity)}</td>
                      <td className="num">{money(Number(t.price), "USD", 4)}</td>
                      <td className="num">{Number(t.fees) ? money(Number(t.fees), "USD") : "–"}</td>
                      <td className="num">{money(txTotal(t), "USD")}</td>
                      <td className="actions">
                        <button
                          className={`more${t.note ? " has-note" : ""}`}
                          aria-expanded={open}
                          aria-label={open ? "Hide note" : "Show note"}
                          title={t.note ? (open ? "Hide note" : "Show note") : "No note"}
                          onClick={() => toggleNote(t.id)}
                        >
                          &hellip;
                        </button>{" "}
                        <button className="del" onClick={() => startEdit(t)}>Edit</button>{" "}
                        <button className="del" onClick={() => confirmDelete(t)}>Delete</button>
                      </td>
                    </tr>
                    {open && (
                      <tr className="note-row">
                        <td colSpan={8}>
                          {t.note
                            ? <><span className="muted">Note: </span>{t.note}</>
                            : <span className="muted">No note on this trade. Use Edit to add one.</span>}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {filtered.length > RECENT_LIMIT && (
        <div className="more-row">
          <span className="muted">Showing {visible.length} of {filtered.length}{needle ? " matching" : ""} trades</span>
          <button onClick={() => setShowAll((v) => !v)}>
            {showAll ? `Show only the latest ${RECENT_LIMIT}` : `Show all ${filtered.length}`}
          </button>
        </div>
      )}
    </>
  );
}

// ---------- page ----------
function PortfolioTabs() {
  const [tab, setTab] = useState<"holdings" | "performance" | "breakdown" | "transactions">("holdings");
  const { defaultCurrency } = usePrefs();
  const [override, setOverride] = useState<string | null>(null); // a temporary choice from the dropdowns on this page
  useEffect(() => setOverride(null), [defaultCurrency]);          // changing the default in Settings resets the view
  const currency = override ?? defaultCurrency;
  const pickCurrency = (c: string) => setOverride(c);
  return (
    <div className="scroll">
      <div className="wrap">
        <h1>Portfolio</h1>
        <div className="tabs page-tabs" role="group" aria-label="Portfolio sections">
          <button className={tab === "holdings" ? "active" : ""} onClick={() => setTab("holdings")}>Holdings</button>
          <button className={tab === "performance" ? "active" : ""} onClick={() => setTab("performance")}>Performance</button>
          <button className={tab === "breakdown" ? "active" : ""} onClick={() => setTab("breakdown")}>Breakdown</button>
          <button className={tab === "transactions" ? "active" : ""} onClick={() => setTab("transactions")}>Transactions</button>
        </div>
        {tab === "holdings" && <Holdings currency={currency} pickCurrency={pickCurrency} />}
        {tab === "performance" && <Performance currency={currency} onCurrency={pickCurrency} />}
        {tab === "breakdown" && <Breakdown currency={currency} onCurrency={pickCurrency} />}
        {tab === "transactions" && <Transactions />}
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
