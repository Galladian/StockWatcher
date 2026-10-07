import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import LoginForm from "./LoginForm";
import { addTransaction, deleteTransaction, fetchMe, listTransactions, type Transaction, type TxType } from "./portfolioApi";

const localToday = () => {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};

const money = (v: number) =>
  v.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 4 });
const shares = (s: string) => Number(s).toLocaleString("en-US", { maximumFractionDigits: 6 });

function total(t: Transaction): number {
  const gross = Number(t.quantity) * Number(t.price);
  const fees = Number(t.fees);
  return t.type === "buy" ? gross + fees : t.type === "sell" ? gross - fees : gross;
}

function Ledger() {
  const qc = useQueryClient();
  const txs = useQuery({ queryKey: ["transactions"], queryFn: listTransactions });

  const [type, setType] = useState<TxType>("buy");
  const [ticker, setTicker] = useState("");
  const [date, setDate] = useState(localToday());
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [fees, setFees] = useState("");
  const [note, setNote] = useState("");

  const add = useMutation({
    mutationFn: () =>
      addTransaction({ ticker, type, trade_date: date, quantity, price, fees: fees || "0", note }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["transactions"] });
      setTicker(""); setQuantity(""); setPrice(""); setFees(""); setNote("");
    },
  });
  const remove = useMutation({
    mutationFn: deleteTransaction,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["transactions"] }),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    add.mutate();
  };
  const confirmDelete = (t: Transaction) => {
    if (window.confirm(`Delete this ${t.type} of ${t.ticker} on ${t.trade_date}?`)) remove.mutate(t.id);
  };

  const priceLabel = type === "dividend" ? "Dividend per share" : "Price per share";

  return (
    <div className="scroll">
      <div className="wrap">
        <h1>Portfolio</h1>
        <p className="lede">Record your trades here. Positions and profit and loss will be worked out from them.</p>

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
              {priceLabel}
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
                  <th>Date</th>
                  <th>Type</th>
                  <th>Ticker</th>
                  <th className="num">Shares</th>
                  <th className="num">Price</th>
                  <th className="num">Fees</th>
                  <th className="num">Total</th>
                  <th>Note</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {txs.data.map((t) => (
                  <tr key={t.id}>
                    <td>{t.trade_date}</td>
                    <td><span className={`tag ${t.type}`}>{t.type}</span></td>
                    <td><b>{t.ticker}</b></td>
                    <td className="num">{shares(t.quantity)}</td>
                    <td className="num">{money(Number(t.price))}</td>
                    <td className="num">{Number(t.fees) ? money(Number(t.fees)) : "–"}</td>
                    <td className="num">{money(total(t))}</td>
                    <td className="note">{t.note}</td>
                    <td><button className="del" onClick={() => confirmDelete(t)}>Delete</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default function PortfolioPage() {
  const me = useQuery({ queryKey: ["me"], queryFn: fetchMe, staleTime: Infinity });
  if (me.isLoading) return <div className="wrap"><p className="muted">Loading…</p></div>;
  if (!me.data?.username) return <LoginForm />;
  return <Ledger />;
}
