"""Rule-of-thumb stock screener: is it reasonably priced, and is the short-term setup good?

Every check returns a status (good / ok / bad / na), a short value, a plain-English detail and
the rule it was judged against. These are general rules of thumb, not advice, and they vary by
industry. All thresholds are in the constants and bands below so they are easy to tweak.
"""
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from . import data
from .indicators import macd, rsi

# ---- short-term thresholds ----
EMA_SPAN = 21
NEAR_EMA = 0.05          # within 5% above the 21 EMA counts as "close above"
EXTENDED_EMA = 0.10      # more than 10% above is very stretched
TESTING_EMA = 0.01       # up to 1% below is "testing" the line
SWING_WINDOW = 5         # a swing low is the lowest low of the 5 bars either side
SWING_LOOKBACK = 126     # roughly six months of trading days
SUPPORT_NEAR = 0.03      # within 3% above support is "near"
SUPPORT_OK = 0.06
RSI_GOOD = 60
RSI_HOT = 70
MACD_RECENT_DAYS = 5     # a bullish cross within this many trading days is "recent"
EARNINGS_WARN_DAYS = 7

_SCORE = {"good": 1, "ok": 0, "bad": -1}


# ---------- helpers ----------
def _n(v):
    """A finite float, or None."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float, np.integer, np.floating)) and math.isfinite(v):
        return float(v)
    return None


def _pos(v):
    return v if v is not None and v > 0 else None


def _pct(x: float, d: int = 1) -> str:
    return f"{x * 100:.{d}f}%"


def _check(id_, label, status, value, detail, rule="", weight=1.0):
    return {"id": id_, "label": label, "status": status, "value": value,
            "detail": detail, "rule": rule, "weight": weight}


def _na(id_, label, why, rule="", weight=1.0):
    return _check(id_, label, "na", "–", why, rule, weight)


def _band(v, good, ok, lower=False):
    if lower:
        return "good" if v <= good else "ok" if v <= ok else "bad"
    return "good" if v >= good else "ok" if v >= ok else "bad"


def _graded(id_, label, v, good, ok, fmt, detail, rule, lower=False, weight=1.0,
            missing="Not available from the data provider."):
    if v is None:
        return _na(id_, label, missing, rule, weight)
    return _check(id_, label, _band(v, good, ok, lower), fmt(v), detail, rule, weight)


def _first(options):
    for v, src in options:
        if v is not None:
            return v, src
    return None, ""


# ---------- valuation ----------
def build_valuation(i: dict, g: dict) -> dict:
    G = lambda k: _n(i.get(k))  # noqa: E731
    price = G("currentPrice") or G("regularMarketPrice") or G("previousClose")
    fwd_pe, tr_pe = _pos(G("forwardPE")), _pos(G("trailingPE"))
    fwd_eps, tr_eps = G("forwardEps"), G("trailingEps")
    implied_eps = fwd_eps / tr_eps - 1 if fwd_eps and tr_eps and fwd_eps > 0 and tr_eps > 0 else None

    rev, rev_src = _first([
        (g.get("rev_next"), "analyst estimate, next fiscal year"),
        (g.get("rev_curr"), "analyst estimate, this fiscal year"),
        (G("revenueGrowth"), "latest quarter vs a year earlier, as no analyst forecast was found"),
    ])
    eps, eps_src = _first([
        (g.get("eps_next"), "analyst estimate, next fiscal year"),
        (g.get("eps_curr"), "analyst estimate, this fiscal year"),
        (implied_eps, "implied by forward vs trailing EPS"),
        (G("earningsGrowth"), "latest quarter vs a year earlier"),
    ])

    hot = " Very high growth estimates are less reliable." if rev is not None and rev > 0.5 else ""

    # -- valuation against growth --
    peg = G("pegRatio") if G("pegRatio") is not None else G("trailingPegRatio")
    peg_src = "Yahoo's PEG ratio"
    if (peg is None or peg <= 0) and fwd_pe and eps and eps > 0:
        peg, peg_src = fwd_pe / (eps * 100), f"forward P/E divided by expected EPS growth of {_pct(eps)} ({eps_src})"
    peg_rule = "Cheap at 1 or below, fair up to 2, expensive above 2"
    if peg is not None and peg > 0:
        peg_chk = _check("peg", "PEG ratio", _band(peg, 1, 2, lower=True), f"{peg:.2f}",
                         f"Price paid per unit of earnings growth, from {peg_src}.", peg_rule, 2)
    elif eps is not None and eps <= 0 and fwd_pe:
        peg_chk = _check("peg", "PEG ratio", "bad", "n/a",
                         "Earnings aren't expected to grow, so growth can't justify the price.", peg_rule, 2)
    else:
        peg_chk = _na("peg", "PEG ratio", "No PEG ratio or earnings growth estimate available.", peg_rule, 2)

    fg_rule = "Cheap at 1 or below, fair up to 2, expensive above 2 (forward P/E divided by growth in %)"
    if fwd_pe is None:
        fg_chk = _na("fwd_vs_growth", "Forward P/E vs revenue growth",
                     "No forward P/E, which usually means no profit is expected yet.", fg_rule, 2)
    elif rev is None:
        fg_chk = _na("fwd_vs_growth", "Forward P/E vs revenue growth", "No revenue growth estimate available.", fg_rule, 2)
    elif rev <= 0:
        fg_chk = _check("fwd_vs_growth", "Forward P/E vs revenue growth", "ok" if fwd_pe < 15 else "bad",
                        f"P/E {fwd_pe:.1f}",
                        f"Revenue isn't expected to grow ({_pct(rev)}), so only a low multiple is justified.", fg_rule, 2)
    else:
        ratio = fwd_pe / (rev * 100)
        fg_chk = _check("fwd_vs_growth", "Forward P/E vs revenue growth", _band(ratio, 1, 2, lower=True), f"{ratio:.2f}",
                        f"Forward P/E of {fwd_pe:.1f} against expected revenue growth of {_pct(rev)} ({rev_src}).{hot}",
                        fg_rule, 2)

    ps = _pos(G("priceToSalesTrailing12Months"))
    ps_rule = "Cheap at 0.4 or below, fair up to 1, expensive above 1 (price/sales divided by growth in %)"
    if ps is None or rev is None:
        ps_chk = _na("ps_vs_growth", "Price/sales vs revenue growth", "Needs both price/sales and a revenue growth estimate.", ps_rule)
    elif rev <= 0:
        ps_chk = _check("ps_vs_growth", "Price/sales vs revenue growth", "bad", f"P/S {ps:.1f}",
                        "Revenue isn't expected to grow, so a sales multiple is hard to justify.", ps_rule)
    else:
        r = ps / (rev * 100)
        ps_chk = _check("ps_vs_growth", "Price/sales vs revenue growth", _band(r, 0.4, 1, lower=True), f"{r:.2f}",
                        f"Price/sales of {ps:.1f} against expected revenue growth of {_pct(rev)}.", ps_rule)

    if fwd_pe and tr_pe:
        ft_status = "good" if fwd_pe < tr_pe * 0.95 else "bad" if fwd_pe > tr_pe * 1.05 else "ok"
        ft_detail = {"good": "Forward P/E is below trailing, so earnings are expected to grow.",
                     "bad": "Forward P/E is above trailing, so earnings are expected to fall.",
                     "ok": "Forward and trailing P/E are about the same, so flat earnings are expected."}[ft_status]
        ft_chk = _check("fwd_vs_trailing", "Forward vs trailing P/E", ft_status, f"{fwd_pe:.1f} vs {tr_pe:.1f}",
                        ft_detail, "Good if forward is at least 5% below trailing, weak if 5% above")
    else:
        ft_chk = _na("fwd_vs_trailing", "Forward vs trailing P/E", "Needs both a forward and a trailing P/E (negative earnings don't count).",
                     "Good if forward is at least 5% below trailing, weak if 5% above")

    # -- growth outlook --
    rev_chk = _graded("rev_growth", "Expected revenue growth", rev, 0.15, 0.05, _pct,
                      f"Source: {rev_src}." if rev is not None else "", "Good at 15%+, okay at 5%+", missing="No revenue growth estimate available.")
    eps_chk = _graded("eps_growth", "Expected EPS growth", eps, 0.15, 0.05, _pct,
                      f"Source: {eps_src}." if eps is not None else "", "Good at 15%+, okay at 5%+", missing="No earnings growth estimate available.")

    # -- margins and quality --
    m_note = "Margins vary a lot by industry: retailers sit structurally lower than software."
    gm = _graded("gross_margin", "Gross margin", G("grossMargins"), 0.50, 0.30, _pct, m_note, "Good at 50%+, okay at 30%+")
    om = _graded("op_margin", "Operating margin", G("operatingMargins"), 0.20, 0.10, _pct, "Profit from the core business before interest and tax.", "Good at 20%+, okay at 10%+")
    nm = _graded("net_margin", "Net margin", G("profitMargins"), 0.15, 0.05, _pct, "What's left of each dollar of sales as profit.", "Good at 15%+, okay at 5%+")
    roe = _graded("roe", "Return on equity", G("returnOnEquity"), 0.15, 0.08, _pct, "How well shareholders' money is turned into profit.", "Good at 15%+, okay at 8%+")
    mcap, fcf = G("marketCap"), G("freeCashflow")
    fcf_yield = fcf / mcap if mcap and fcf is not None else None
    fcfc = _graded("fcf_yield", "Free cash flow yield", fcf_yield, 0.05, 0.02, _pct,
                   "Cash left after investment, as a share of the company's market value.", "Good at 5%+, okay at 2%+")

    # -- other comparisons --
    ev = G("enterpriseToEbitda")
    if ev is not None and ev <= 0:
        evc = _check("ev_ebitda", "EV/EBITDA", "bad", f"{ev:.1f}", "Negative: the company isn't generating operating profit.", "Good at 12 or below, okay up to 20")
    else:
        evc = _graded("ev_ebitda", "EV/EBITDA", ev, 12, 20, lambda v: f"{v:.1f}",
                      "Company value relative to operating cash profit. Debt is included, unlike P/E.", "Good at 12 or below, okay up to 20", lower=True)
    de = G("debtToEquity")
    dec = _graded("debt_equity", "Debt to equity", de / 100 if de is not None else None, 0.5, 1.5, lambda v: f"{v:.2f}",
                  "How much the company borrows relative to shareholders' equity. Banks naturally run higher.", "Good at 0.5 or below, okay up to 1.5", lower=True)
    target = G("targetMeanPrice")
    upside = target / price - 1 if target and price else None
    n_an = G("numberOfAnalystOpinions")
    upc = _graded("analyst_upside", "Analyst target upside", upside, 0.15, 0.0, lambda v: f"{v * 100:+.1f}%",
                  f"Mean analyst target of ${target:,.2f}" + (f" from {int(n_an)} analysts." if n_an else ".") if target else "",
                  "Good at +15% or more, okay above 0%", missing="No analyst price target available.")

    groups = [
        {"title": "Price against growth", "checks": [peg_chk, fg_chk, ps_chk, ft_chk]},
        {"title": "Growth outlook", "checks": [rev_chk, eps_chk]},
        {"title": "Margins and profitability", "checks": [gm, om, nm, roe, fcfc]},
        {"title": "Other comparisons", "checks": [evc, dec, upc]},
    ]

    flat = [c for gr in groups for c in gr["checks"]]
    scored = [c for c in flat if c["status"] in _SCORE]
    out = {"groups": groups}
    if len(scored) < 5:
        out.update(verdict="Not enough data to judge", tone="na",
                   summary=f"Only {len(scored)} checks have data, which isn't enough for a verdict.")
        return out
    total_w = sum(c["weight"] for c in scored)
    score = sum(_SCORE[c["status"]] * c["weight"] for c in scored) / total_w
    good = sum(c["status"] == "good" for c in scored)
    bad = sum(c["status"] == "bad" for c in scored)
    verdict, tone = (("Looks attractively valued", "good") if score >= 0.35
                     else ("Looks expensive", "bad") if score <= -0.35
                     else ("Fairly valued, with mixed signals", "ok"))
    out.update(verdict=verdict, tone=tone,
               summary=f"{good} of {len(scored)} checks look good and {bad} look weak. PEG and forward P/E vs growth count double.")
    return out


# ---------- short term ----------
def _support(df: pd.DataFrame, price: float):
    """Nearest support at or below the price: a recent swing low, or the 50/200-day average."""
    low, close = df["low"], df["close"]
    cands = []
    s = low.tail(SWING_LOOKBACK)
    vals, k = s.values, SWING_WINDOW
    for j in range(k, len(s) - k):
        if vals[j] == vals[j - k: j + k + 1].min() and vals[j] <= price:
            cands.append((float(vals[j]), f"swing low on {s.index[j]:%Y-%m-%d}"))
    for n in (50, 200):
        if len(close) >= n:
            m = float(close.rolling(n).mean().iloc[-1])
            if m <= price:
                cands.append((m, f"{n}-day average"))
    return max(cands, key=lambda c: c[0]) if cands else None


def _macd_state(close: pd.Series):
    """(currently above signal, trading days since the last bullish cross or None, histogram improving)."""
    m = macd(close)
    diff = (m["macd"] - m["signal"]).dropna()
    if len(diff) < 3:
        return None
    above = diff > 0
    crossed_up = above & ~above.shift(1, fill_value=above.iloc[0])
    idx = np.flatnonzero(crossed_up.values)
    since = int(len(diff) - 1 - idx[-1]) if len(idx) else None
    return bool(above.iloc[-1]), since, bool(diff.iloc[-1] > diff.iloc[-2] > diff.iloc[-3])


def build_short_term(df: pd.DataFrame, info: dict | None) -> dict:
    close = df["close"]
    price = float(close.iloc[-1])

    # 1) close above the 21 EMA
    ema21 = float(close.ewm(span=EMA_SPAN, adjust=False).mean().iloc[-1])
    d = price / ema21 - 1
    ema_rule = "Good if 0-5% above the 21-day EMA, okay if stretched above it or just under, weak if below"
    if 0 <= d <= NEAR_EMA:
        ema_chk = _check("ema", "Close above the 21-day EMA", "good", f"{d * 100:+.1f}%",
                         f"Price ${price:,.2f} is just above the 21-day EMA (${ema21:,.2f}), so the trend is intact without being stretched.", ema_rule)
    elif NEAR_EMA < d:
        st = "ok" if d <= EXTENDED_EMA else "bad"
        ema_chk = _check("ema", "Close above the 21-day EMA", st, f"{d * 100:+.1f}%",
                         f"Price is {d * 100:.1f}% above the 21-day EMA (${ema21:,.2f}): strong, but extended, so it's a poorer place to enter.", ema_rule)
    elif d >= -TESTING_EMA:
        ema_chk = _check("ema", "Close above the 21-day EMA", "ok", f"{d * 100:+.1f}%",
                         f"Price is just under the 21-day EMA (${ema21:,.2f}) and testing it. Wait for a close back above.", ema_rule)
    else:
        ema_chk = _check("ema", "Close above the 21-day EMA", "bad", f"{d * 100:+.1f}%",
                         f"Price is {abs(d) * 100:.1f}% below the 21-day EMA (${ema21:,.2f}), so short-term trend is down.", ema_rule)

    # 2) near support
    sup_rule = "Good within 3% above support, okay within 6%, weak if further away or no support below"
    sup = _support(df, price)
    if sup is None:
        sup_chk = _check("support", "Near support", "bad", "none",
                         "No swing low or 50/200-day average sits below the price, so it's trading near its lows with nothing underneath.", sup_rule)
    else:
        level, label = sup
        dist = (price - level) / price
        sup_chk = _check("support", "Near support", "good" if dist <= SUPPORT_NEAR else "ok" if dist <= SUPPORT_OK else "bad",
                         f"{dist * 100:.1f}% above",
                         f"Nearest support is the {label} at ${level:,.2f}. The closer the price is to it, the less you risk if it fails.", sup_rule)

    # 3) RSI
    r = float(rsi(close).iloc[-1])
    rsi_rule = "Good below 60, okay 60-70, weak at 70 or above"
    rsi_note = " That's oversold territory." if r < 30 else ""
    rsi_chk = _check("rsi", "RSI below 60", "good" if r < RSI_GOOD else "ok" if r < RSI_HOT else "bad", f"{r:.1f}",
                     f"Daily RSI. Below 60 leaves room to run before it looks overbought.{rsi_note}", rsi_rule)

    # 4) MACD cross
    state = _macd_state(close)
    macd_rule = f"Good if it crossed above the signal line within {MACD_RECENT_DAYS} trading days, okay if above for longer, weak if below"
    if state is None:
        macd_chk = _na("macd", "MACD crossed above signal", "Not enough price history.", macd_rule)
    else:
        above, since, improving = state
        if above and since is not None and since <= MACD_RECENT_DAYS:
            ago = "today" if since == 0 else f"{since} trading day{'s' if since != 1 else ''} ago"
            macd_chk = _check("macd", "MACD crossed above signal", "good", f"crossed {ago}",
                              "A fresh bullish cross: momentum has only just turned up.", macd_rule)
        elif above:
            when = f"{since} trading days ago" if since is not None else "a long time ago"
            macd_chk = _check("macd", "MACD crossed above signal", "ok", f"crossed {when}",
                              "MACD is above its signal line, but the cross isn't recent, so some of the move may be done.", macd_rule)
        else:
            tail = " The gap is narrowing, so a cross may be near." if improving else ""
            macd_chk = _check("macd", "MACD crossed above signal", "bad", "below signal",
                              f"MACD is below its signal line, so momentum is still down.{tail}", macd_rule)

    core = [ema_chk, sup_chk, rsi_chk, macd_chk]
    met = sum(c["status"] == "good" for c in core)
    missing = [c["label"] for c in core if c["status"] != "good"]
    verdict, tone = ((("Setup looks favorable", "good") if met == 4 else
                      ("Close to a good setup", "ok") if met == 3 else
                      ("Mixed setup", "ok") if met == 2 else
                      ("Not a good entry right now", "bad")))
    def lc(label: str) -> str:  # lower-case the first word, but keep acronyms like RSI and MACD
        return label if label[:2].isupper() else label[0].lower() + label[1:]
    summary = f"{met} of 4 conditions met." + (f" Not yet: {', '.join(lc(m) for m in missing)}." if missing else "")

    # extras (shown, but not part of the verdict)
    extras = []
    if len(close) >= 50:
        s50 = float(close.rolling(50).mean().iloc[-1])
        s200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
        above_n = (price > s50) + (s200 is not None and price > s200)
        total_n = 2 if s200 is not None else 1
        extras.append(_check("trend", "Trend: above the 50 and 200-day averages",
                             "good" if above_n == total_n else "bad" if above_n == 0 else "ok",
                             f"{above_n} of {total_n}",
                             f"Price ${price:,.2f} vs 50-day ${s50:,.2f}" + (f" and 200-day ${s200:,.2f}." if s200 is not None else "."),
                             "Good above both, weak below both"))
    ts = _n((info or {}).get("earningsTimestamp"))
    if ts:
        days = (datetime.fromtimestamp(ts, tz=timezone.utc).date() - date.today()).days
        if days >= 0:
            extras.append(_check("earnings", "Earnings date", "ok" if days <= EARNINGS_WARN_DAYS else "good",
                                 "today" if days == 0 else f"in {days} days",
                                 "Earnings are close, so expect a big move either way." if days <= EARNINGS_WARN_DAYS
                                 else "No earnings report within the next week.",
                                 f"Okay (caution) if within {EARNINGS_WARN_DAYS} days"))

    return {"verdict": verdict, "tone": tone, "summary": summary, "checks": core, "extras": extras}


# ---------- entry point ----------
def build_screen(ticker: str) -> dict:
    ticker = ticker.upper().strip()
    jobs = {"info": data.get_info, "growth": data.get_growth, "daily": data.get_daily}
    results, errors = {}, {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {k: pool.submit(fn, ticker) for k, fn in jobs.items()}
        for k, f in futures.items():
            try:
                results[k] = f.result()
            except Exception as e:  # noqa: BLE001
                errors[k] = e

    if "info" in errors and "daily" in errors:
        raise next((e for e in errors.values() if isinstance(e, data.TickerNotFound)), errors["info"])

    warnings: list[str] = []
    info, daily = results.get("info"), results.get("daily")
    g = results.get("growth") or {}

    valuation = short_term = None
    if info is not None:
        valuation = build_valuation(info, g)
    else:
        warnings.append("Company fundamentals are unavailable, so the valuation section is skipped.")
    if daily is not None and len(daily) >= 30:
        short_term = build_short_term(daily, info)
    else:
        warnings.append("There isn't enough price history for the short-term section.")

    i = info or {}
    price = float(daily["close"].iloc[-1]) if daily is not None and len(daily) else (
        _n(i.get("currentPrice")) or _n(i.get("regularMarketPrice")))
    return {
        "ticker": ticker,
        "name": i.get("longName") or i.get("shortName"),
        "sector": i.get("sector"),
        "industry": i.get("industry"),
        "price": price,
        "market_cap": _n(i.get("marketCap")),
        "valuation": valuation,
        "short_term": short_term,
        "warnings": warnings,
    }
