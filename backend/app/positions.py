"""Portfolio maths. Pure functions: ledger rows + quotes in, summary out.

Method: average cost. A sell removes shares at the current average cost per share, and the
difference between sale proceeds and that cost is realised P&L. Fees on buys are added to cost
and fees on sells reduce proceeds. Dividends are counted as income, separate from price P&L.

Day change = value now - value at the previous close - money put in during the latest session.
Fees are left out so one purchase doesn't show up as a day loss.

Trades dated on or after the latest session need care, because people often enter shares they
already own using today's date. For each such trade:
  * price inside the latest session's trading range, dated on that session -> a genuine
    purchase that day, measured from the buy price;
  * price inside the range, dated after the session (e.g. a New Zealand date that is ahead of
    the US session) -> bought after the session, so it adds nothing to the day change;
  * price outside the range -> can't be a fresh purchase, so it is treated as already held
    going into the session and measured from the previous close.
"""
from collections import defaultdict
from decimal import Decimal

ZERO = Decimal(0)
_ORDER = {"buy": 0, "dividend": 1, "sell": 2}  # same-day buys count before same-day sells


def _f(x):
    return None if x is None else float(x)


def _pct(num: Decimal, den: Decimal):
    return float(num / den * 100) if den and den > 0 else None


def _in_range(quote: dict, price: Decimal) -> bool:
    lo, hi = quote.get("low"), quote.get("high")
    if lo is None or hi is None:
        return True  # range unknown: take the trade at face value
    return lo * Decimal("0.995") <= price <= hi * Decimal("1.005")


def compute_portfolio(txs, quotes: dict) -> dict:
    by_ticker = defaultdict(list)
    for t in sorted(txs, key=lambda t: (t.trade_date, _ORDER[t.type], t.id)):
        by_ticker[t.ticker].append(t)

    warnings: list[str] = []
    held: list[dict] = []
    realized_total = dividends_total = ZERO
    sessions = []

    for ticker, rows in by_ticker.items():
        quote = quotes.get(ticker)
        session = quote["session_date"] if quote else None
        shares = cost = realized = divs = net_flow = new_money = extra_prev = ZERO
        shares_prev = None  # shares held going into the latest session

        for t in rows:
            if session and shares_prev is None and t.trade_date >= session:
                shares_prev = shares
            recent = bool(session) and t.trade_date >= session
            gross = t.quantity * t.price

            if t.type == "buy":
                shares += t.quantity
                cost += gross + t.fees
                if recent:
                    if not _in_range(quote, t.price):
                        extra_prev += t.quantity            # looks like an existing holding
                    elif t.trade_date == session:
                        net_flow += gross                   # bought during the latest session
                        new_money += gross
                    else:
                        net_flow += t.quantity * quote["price"]  # bought after it: no day effect
            elif t.type == "sell":
                if shares <= 0:
                    warnings.append(f"{ticker}: a sale of {t.quantity} on {t.trade_date} was ignored because no shares were held.")
                    continue
                qty = min(t.quantity, shares)
                if qty < t.quantity:
                    warnings.append(f"{ticker}: the sale on {t.trade_date} was for {t.quantity} shares but only {qty} were held, so only {qty} were counted.")
                removed = cost / shares * qty
                realized += qty * t.price - t.fees - removed
                shares -= qty
                cost = ZERO if shares == 0 else cost - removed
                if recent:
                    sold_in_session = t.trade_date == session and _in_range(quote, t.price)
                    net_flow -= qty * (t.price if sold_in_session else quote["price"])
            else:  # dividend
                divs += gross - t.fees

        if shares_prev is None:
            shares_prev = shares
        shares_prev += extra_prev
        realized_total += realized
        dividends_total += divs
        if shares <= 0:
            continue  # closed position: only its realised P&L / dividends remain

        h = {"ticker": ticker, "shares": shares, "cost": cost, "price": None}
        if quote is None:
            warnings.append(f"{ticker}: price unavailable, so it is left out of the totals.")
        else:
            price, prev_close = quote["price"], quote["prev_close"]
            mv = shares * price
            prev_value = shares_prev * prev_close
            h.update(
                price=price, prev_close=prev_close, mv=mv,
                day=mv - prev_value - net_flow,
                day_base=prev_value + new_money,
                unrealized=mv - cost,
            )
            sessions.append(session)
        held.append(h)

    priced = [h for h in held if h["price"] is not None]
    mv_total = sum((h["mv"] for h in priced), ZERO)
    cost_total = sum((h["cost"] for h in priced), ZERO)
    day_total = sum((h["day"] for h in priced), ZERO)
    base_total = sum((h["day_base"] for h in priced), ZERO)
    unrealized_total = mv_total - cost_total

    holdings = []
    for h in sorted(held, key=lambda h: h.get("mv", Decimal(-1)), reverse=True):
        holdings.append({
            "ticker": h["ticker"], "shares": float(h["shares"]),
            "avg_cost": float(h["cost"] / h["shares"]), "cost_basis": float(h["cost"]),
            "price": _f(h["price"]), "prev_close": _f(h.get("prev_close")),
            "market_value": _f(h.get("mv")), "day_change": _f(h.get("day")),
            "day_change_pct": _pct(h["day"], h["day_base"]) if "day" in h else None,
            "unrealized": _f(h.get("unrealized")),
            "unrealized_pct": _pct(h["unrealized"], h["cost"]) if "unrealized" in h else None,
            "weight": float(h["mv"] / mv_total * 100) if "mv" in h and mv_total > 0 else None,
        })

    return {
        "as_of": max(sessions).isoformat() if sessions else None,
        "totals": {
            "market_value": float(mv_total),
            "cost_basis": float(cost_total),
            "day_change": float(day_total),
            "day_change_pct": _pct(day_total, base_total),
            "unrealized": float(unrealized_total),
            "unrealized_pct": _pct(unrealized_total, cost_total),
            "realized": float(realized_total),
            "dividends": float(dividends_total),
            "total_return": float(unrealized_total + realized_total + dividends_total),
        },
        "holdings": holdings,
        "warnings": warnings,
    }
