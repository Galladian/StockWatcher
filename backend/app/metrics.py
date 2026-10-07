"""Turns raw provider fields into a clean, provider-agnostic metrics payload.

Conventions: ratios/percentages are returned as plain fractions (0.25 = 25%),
missing or non-finite values are None. The frontend does all formatting.
"""
import math
from datetime import datetime, timezone

from . import data


def _num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)) and math.isfinite(v):
        return float(v)
    return None


def build_metrics(ticker: str) -> dict:
    i = data.get_info(ticker)
    g = lambda k: _num(i.get(k))  # noqa: E731

    price = g("currentPrice") or g("regularMarketPrice") or g("previousClose")
    div_rate = g("dividendRate")
    div_yield = div_rate / price if div_rate and price else None  # computed: provider units vary
    de = g("debtToEquity")
    target = g("targetMeanPrice")

    ex = i.get("exDividendDate")
    ex_date = (
        datetime.fromtimestamp(ex, tz=timezone.utc).strftime("%Y-%m-%d")
        if isinstance(ex, (int, float)) and ex > 0 else None
    )
    rec = i.get("recommendationKey")

    return {
        "ticker": ticker.upper(),
        "name": i.get("longName") or i.get("shortName"),
        "sector": i.get("sector"),
        "industry": i.get("industry"),
        "exchange": i.get("fullExchangeName") or i.get("exchange"),
        "price": price,
        # valuation
        "market_cap": g("marketCap"),
        "enterprise_value": g("enterpriseValue"),
        "pe_trailing": g("trailingPE"),
        "pe_forward": g("forwardPE"),
        "peg": g("pegRatio") if g("pegRatio") is not None else g("trailingPegRatio"),
        "price_to_sales": g("priceToSalesTrailing12Months"),
        "price_to_book": g("priceToBook"),
        "ev_to_ebitda": g("enterpriseToEbitda"),
        "eps_trailing": g("trailingEps"),
        "eps_forward": g("forwardEps"),
        # dividend
        "dividend_rate": div_rate,
        "dividend_yield": div_yield,
        "payout_ratio": g("payoutRatio"),
        "ex_dividend_date": ex_date,
        # profitability
        "gross_margin": g("grossMargins"),
        "operating_margin": g("operatingMargins"),
        "profit_margin": g("profitMargins"),
        "roe": g("returnOnEquity"),
        "roa": g("returnOnAssets"),
        # growth & cash
        "revenue": g("totalRevenue"),
        "revenue_growth": g("revenueGrowth"),
        "earnings_growth": g("earningsGrowth"),
        "free_cash_flow": g("freeCashflow"),
        # balance sheet
        "total_cash": g("totalCash"),
        "total_debt": g("totalDebt"),
        "debt_to_equity": de / 100 if de is not None else None,  # provider reports percent
        "current_ratio": g("currentRatio"),
        # trading
        "beta": g("beta"),
        "week52_high": g("fiftyTwoWeekHigh"),
        "week52_low": g("fiftyTwoWeekLow"),
        "avg_volume": g("averageVolume"),
        "shares_outstanding": g("sharesOutstanding"),
        "short_percent_float": g("shortPercentOfFloat"),
        # analysts
        "recommendation": rec.replace("_", " ").capitalize() if isinstance(rec, str) and rec != "none" else None,
        "analyst_count": g("numberOfAnalystOpinions"),
        "target_mean": target,
        "target_high": g("targetHighPrice"),
        "target_low": g("targetLowPrice"),
        "target_upside": target / price - 1 if target and price else None,
    }
