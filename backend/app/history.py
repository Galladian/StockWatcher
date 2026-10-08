"""Portfolio value over time, rebuilt from the ledger and daily closing prices (all in USD).

For every day: value = shares held that day x that day's close, summed over your stocks.
Also returns the money you have put in so far (buys minus sales, fees included) and the dividends
received, which the page uses to work out your return without counting new deposits as gains.
Cash isn't included: cash balances have no dates, so there is no history to rebuild.
"""
from collections import defaultdict
from decimal import Decimal

import pandas as pd

from .positions import _ORDER  # same-day ordering as the holdings maths

ZERO = Decimal(0)


def replay(rows) -> tuple[dict, Decimal, Decimal]:
    """Average-cost replay of one ticker's trades, using the same rules as the holdings maths.
    Returns ({date: [shares, cost, cash_flow, income]}, final shares, final cost), where cash_flow is
    money paid in (buys, fees included) minus money taken out (sales, net of fees)."""
    shares = cost = ZERO
    events: dict = {}
    for t in rows:
        e = events.setdefault(t.trade_date, [ZERO, ZERO, ZERO, ZERO])
        if t.type == "buy":
            shares += t.quantity
            cost += t.quantity * t.price + t.fees
            e[2] += t.quantity * t.price + t.fees
        elif t.type == "sell" and shares > 0:
            qty = min(t.quantity, shares)
            removed = cost / shares * qty
            shares -= qty
            cost = ZERO if shares == 0 else cost - removed
            e[2] -= qty * t.price - t.fees
        elif t.type == "dividend":
            e[3] += t.quantity * t.price - t.fees
        e[0], e[1] = shares, cost
    return events, shares, cost


def _split_text(ratio: float) -> str:
    return f"{ratio:g}-for-1" if ratio >= 1 else f"1-for-{1 / ratio:g}"


def compute_history(txs, frames: dict) -> dict:
    by_ticker = defaultdict(list)
    for t in sorted(txs, key=lambda t: (t.trade_date, _ORDER[t.type], t.id)):
        by_ticker[t.ticker].append(t)
    if not by_ticker:
        return {"points": [], "warnings": []}

    warnings: list[str] = []
    events_by = {tk: replay(rows)[0] for tk, rows in by_ticker.items()}
    first = pd.Timestamp(min(t.trade_date for t in txs))

    # one row per trading day from the first trade, plus any trade dates that fall on a non-trading day
    dates = {pd.Timestamp(d) for ev in events_by.values() for d in ev}
    for tk in events_by:
        fr = frames.get(tk)
        if fr is not None and not fr.empty:
            dates.update(fr.index[fr.index >= first])
    grid = pd.DatetimeIndex(sorted(dates))

    value = pd.Series(0.0, index=grid)
    invested = pd.Series(0.0, index=grid)
    income = pd.Series(0.0, index=grid)

    for tk, ev in events_by.items():
        keys = sorted(ev)
        idx = pd.DatetimeIndex([pd.Timestamp(k) for k in keys])
        shares = pd.Series([float(ev[k][0]) for k in keys], index=idx).reindex(grid).ffill().fillna(0.0)
        invested += pd.Series([float(ev[k][2]) for k in keys], index=idx).cumsum().reindex(grid).ffill().fillna(0.0)
        income += pd.Series([float(ev[k][3]) for k in keys], index=idx).cumsum().reindex(grid).ffill().fillna(0.0)

        fr = frames.get(tk)
        if fr is None or fr.empty:
            warnings.append(f"{tk}: no price history is available, so it is left out of the value line.")
            continue
        px = fr["close"].reindex(grid.union(fr.index)).ffill().reindex(grid)
        if ((shares > 0) & px.isna()).any():
            warnings.append(f"{tk}: its price history starts after your first trade, so the earliest days are understated.")
        value += (shares * px).fillna(0.0)

        if "split" in fr:
            sp = fr["split"]
            for d, r in sp[(sp > 0) & (sp != 1) & (sp.index > pd.Timestamp(keys[0]))].items():
                warnings.append(
                    f"{tk} had a {_split_text(float(r))} stock split on {d:%d/%m/%Y}. The chart and your holdings assume "
                    f"you entered trades before that date as post-split shares and prices."
                )

    points = [
        {"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 2), "invested": round(float(i), 2), "income": round(float(n), 2)}
        for d, v, i, n in zip(grid, value, invested, income)
    ]
    return {"points": points, "warnings": warnings}
