"""Portfolio breakdown: sector split, concentration and other things worth noting.

Pure function: a converted portfolio summary plus company profiles in, breakdown out.
"""
from collections import defaultdict

FUND_TYPES = {"ETF", "MUTUALFUND"}
SECTOR_NAMES = {
    "technology": "Technology", "communication_services": "Communication Services",
    "financial_services": "Financial Services", "consumer_cyclical": "Consumer Cyclical",
    "consumer_defensive": "Consumer Defensive", "healthcare": "Healthcare", "industrials": "Industrials",
    "energy": "Energy", "utilities": "Utilities", "realestate": "Real Estate", "basic_materials": "Basic Materials",
}
NOT_A_SECTOR = {"Cash", "Unknown", "ETFs and funds"}

# thresholds for the "worth noting" list
TOP_POSITION_FLAG = 25.0   # one holding with more than this % of the portfolio
SECTOR_FLAG = 40.0         # one sector this many %
FEW_HOLDINGS = 3
CASH_FLAG = 20.0
UNKNOWN_FLAG = 10.0
HIGH_BETA, LOW_BETA = 1.3, 0.8

CAP_BUCKETS = [("Mega cap (over $200B)", 200e9), ("Large cap ($10B to $200B)", 10e9),
               ("Mid cap ($2B to $10B)", 2e9), ("Small cap (under $2B)", 0.0)]


def _empty() -> dict:
    return {
        "total_value": 0.0, "sectors": [],
        "concentration": {"holdings_count": 0, "top": None, "top3": 0.0, "top5": 0.0, "effective_n": None, "largest_sector": None},
        "characteristics": {"beta": None, "beta_coverage": None, "forward_pe": None, "pe_coverage": None,
                            "dividend_income": 0.0, "dividend_yield": None, "dividend_payers": 0},
        "market_cap": [],
        "performance": {"winners": 0, "losers": 0, "best": None, "worst": None, "day_best": None, "day_worst": None},
        "observations": [], "warnings": [],
    }


def _mover(h: dict, pct_key: str, amount_key: str) -> dict:
    return {"ticker": h["ticker"], "pct": h[pct_key], "amount": h[amount_key]}


def compute_breakdown(summary: dict, profiles: dict) -> dict:
    holdings = [h for h in summary["holdings"] if h.get("market_value")]
    stock_total = sum(h["market_value"] for h in holdings)
    cash_total = summary["totals"]["cash"]
    total = stock_total + cash_total
    out = _empty()
    if total <= 0:
        return out
    out["total_value"] = total
    warnings = out["warnings"]

    # ---- sector split (cash included, funds looked through where possible) ----
    sec_value: dict[str, float] = defaultdict(float)
    sec_holdings: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for h in holdings:
        p = profiles.get(h["ticker"])
        mv = h["market_value"]
        weights = p.get("sector_weights") if p else None
        if weights:
            norm = sum(weights.values())
            for key, w in weights.items():
                name = SECTOR_NAMES.get(key, key.replace("_", " ").title())
                sec_value[name] += mv * w / norm
                sec_holdings[name][h["ticker"]] += mv * w / norm
            continue
        if p and p.get("sector"):
            name = p["sector"]
        elif p and p.get("quote_type") in FUND_TYPES:
            name = "ETFs and funds"
        else:
            name = "Unknown"
            warnings.append(f"{h['ticker']}: no sector data, so it is grouped as Unknown.")
        sec_value[name] += mv
        sec_holdings[name][h["ticker"]] += mv
    if cash_total > 0:
        sec_value["Cash"] += cash_total

    out["sectors"] = [
        {"name": n, "value": v, "weight": v / total * 100,
         "holdings": [{"ticker": t, "value": hv} for t, hv in sorted(sec_holdings[n].items(), key=lambda x: -x[1])]}
        for n, v in sorted(sec_value.items(), key=lambda x: -x[1])
    ]

    # ---- concentration ----
    ranked = sorted(holdings, key=lambda h: -h["market_value"])
    weights = [h["market_value"] / total * 100 for h in ranked]
    sector_only = [(n, v) for n, v in sec_value.items() if n not in NOT_A_SECTOR]
    big_sector = max(sector_only, key=lambda x: x[1]) if sector_only else None
    out["concentration"] = {
        "holdings_count": len(ranked),
        "top": {"ticker": ranked[0]["ticker"], "weight": weights[0]} if ranked else None,
        "top3": sum(weights[:3]), "top5": sum(weights[:5]),
        "effective_n": 1 / sum((h["market_value"] / stock_total) ** 2 for h in ranked) if ranked else None,
        "largest_sector": {"name": big_sector[0], "weight": big_sector[1] / total * 100} if big_sector else None,
    }

    # ---- characteristics (value-weighted across the stocks that have the data) ----
    def covered(key, keep=lambda v: True):
        return [(h["market_value"], profiles[h["ticker"]][key]) for h in holdings
                if profiles.get(h["ticker"]) and profiles[h["ticker"]].get(key) is not None and keep(profiles[h["ticker"]][key])]

    betas, pes = covered("beta"), covered("forward_pe", lambda v: v > 0)
    beta = sum(w * b for w, b in betas) / sum(w for w, _ in betas) if betas else None
    pe = sum(w for w, _ in pes) / sum(w / x for w, x in pes) if pes else None   # harmonic: how a fund would compute it
    factor = summary.get("fx_rate") or 1.0                                        # dividends are quoted in USD
    payers = [(h, profiles[h["ticker"]]["dividend_rate"]) for h in holdings
              if profiles.get(h["ticker"]) and (profiles[h["ticker"]].get("dividend_rate") or 0) > 0]
    income = sum(h["shares"] * rate for h, rate in payers) * factor
    out["characteristics"] = {
        "beta": beta, "beta_coverage": sum(w for w, _ in betas) / stock_total * 100 if betas else None,
        "forward_pe": pe, "pe_coverage": sum(w for w, _ in pes) / stock_total * 100 if pes else None,
        "dividend_income": income, "dividend_yield": income / stock_total * 100 if stock_total else None,
        "dividend_payers": len(payers),
    }

    # ---- company size ----
    size: dict[str, float] = defaultdict(float)
    for h in holdings:
        p = profiles.get(h["ticker"]) or {}
        if p.get("quote_type") in FUND_TYPES:
            name = "Funds"
        elif p.get("market_cap"):
            name = next(n for n, floor in CAP_BUCKETS if p["market_cap"] >= floor)
        else:
            name = "Unknown"
        size[name] += h["market_value"]
    order = [n for n, _ in CAP_BUCKETS] + ["Funds", "Unknown"]
    out["market_cap"] = [{"name": n, "value": size[n], "weight": size[n] / stock_total * 100} for n in order if size.get(n)]

    # ---- performance ----
    up = [h for h in holdings if h.get("unrealized") is not None]
    out["performance"]["winners"] = sum(h["unrealized"] > 0 for h in up)
    out["performance"]["losers"] = sum(h["unrealized"] < 0 for h in up)
    by_gain = sorted((h for h in up if h.get("unrealized_pct") is not None), key=lambda h: h["unrealized_pct"])
    by_day = sorted((h for h in holdings if h.get("day_change_pct") is not None and h.get("day_change") is not None),
                    key=lambda h: h["day_change_pct"])
    if len(by_gain) >= 2:
        out["performance"]["best"] = _mover(by_gain[-1], "unrealized_pct", "unrealized")
        out["performance"]["worst"] = _mover(by_gain[0], "unrealized_pct", "unrealized")
    if len(by_day) >= 2:
        out["performance"]["day_best"] = _mover(by_day[-1], "day_change_pct", "day_change")
        out["performance"]["day_worst"] = _mover(by_day[0], "day_change_pct", "day_change")

    # ---- worth noting ----
    obs = out["observations"]
    top, ls = out["concentration"]["top"], out["concentration"]["largest_sector"]
    if top and top["weight"] > TOP_POSITION_FLAG:  # strictly more than a quarter, so an even 4-stock split isn't flagged
        obs.append({"tone": "ok", "text": f"{top['ticker']} is {top['weight']:.0f}% of your portfolio, so it has a big say in your results."})
    if ls and ls["weight"] >= SECTOR_FLAG:
        obs.append({"tone": "ok", "text": f"{ls['weight']:.0f}% of your portfolio is in {ls['name']}, so a bad stretch for that sector would hit you hard."})
    if 0 < len(ranked) <= FEW_HOLDINGS:
        obs.append({"tone": "ok", "text": f"You hold only {len(ranked)} {'stock' if len(ranked) == 1 else 'stocks'}, so the risk from any single company is high."})
    cash_w = cash_total / total * 100
    if cash_w >= CASH_FLAG:
        obs.append({"tone": "info", "text": f"Cash is {cash_w:.0f}% of your portfolio. That cushions swings but earns no market return."})
    unknown_w = sec_value.get("Unknown", 0) / total * 100
    if unknown_w >= UNKNOWN_FLAG:
        obs.append({"tone": "info", "text": f"{unknown_w:.0f}% of your portfolio couldn't be assigned a sector, so the split above is incomplete."})
    if beta is not None and beta >= HIGH_BETA:
        obs.append({"tone": "ok", "text": f"Your stocks have a weighted beta of {beta:.2f}, so they tend to swing more than the overall market."})
    elif beta is not None and beta <= LOW_BETA:
        obs.append({"tone": "info", "text": f"Your stocks have a weighted beta of {beta:.2f}, so they tend to swing less than the overall market."})
    if not obs:
        obs.append({"tone": "good", "text": "Nothing stands out. No single holding, sector or cash balance dominates."})
    return out
