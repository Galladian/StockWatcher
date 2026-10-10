"""Data provider layer. Only this file knows where prices come from.
To switch to Polygon/Tiingo/etc., keep get_daily() and get_intraday() signatures and swap the bodies."""
import time
import pandas as pd
import yfinance as yf

_CACHE: dict[tuple, tuple[float, pd.DataFrame]] = {}


class TickerNotFound(Exception):
    pass


def _fetch(ticker: str, interval: str, period: str, ttl: int) -> pd.DataFrame:
    ticker = ticker.upper().strip()
    key = (ticker, interval, period)
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]

    raw = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=True)
    if raw is None or raw.empty:
        raise TickerNotFound(ticker)

    df = raw.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
    # Drop the timezone but keep exchange wall-clock time (so 9:30 stays 9:30 Eastern)
    df.index = pd.to_datetime(df.index).tz_localize(None)
    if interval == "1d":
        df.index = df.index.normalize()
    df = df.dropna(subset=["open", "high", "low", "close"])
    _CACHE[key] = (now, df)
    return df


def get_daily(ticker: str) -> pd.DataFrame:
    """Full daily OHLCV history, split/dividend adjusted."""
    return _fetch(ticker, "1d", "max", ttl=300)


def get_intraday(ticker: str, interval: str, period: str) -> pd.DataFrame:
    """Recent intraday bars (regular trading hours), e.g. interval='5m', period='5d'."""
    return _fetch(ticker, interval, period, ttl=60)


_INFO_CACHE: dict[str, tuple[float, dict]] = {}


def get_info(ticker: str) -> dict:
    """Company profile + fundamentals (raw provider fields). Cached for 15 minutes."""
    ticker = ticker.upper().strip()
    now = time.time()
    hit = _INFO_CACHE.get(ticker)
    if hit and now - hit[0] < 900:
        return hit[1]
    info = yf.Ticker(ticker).info or {}
    if not info:
        raise TickerNotFound(ticker)
    _INFO_CACHE[ticker] = (now, info)
    return info


# ---- quotes (latest price + previous close) for the portfolio ----
from concurrent.futures import ThreadPoolExecutor  # noqa: E402
from decimal import Decimal  # noqa: E402

_QUOTE_CACHE: dict[str, tuple[float, dict | None]] = {}


def _dec(v) -> Decimal | None:
    try:
        f = float(v)
        return Decimal(str(f)) if f == f else None
    except (TypeError, ValueError):
        return None


def get_quote(ticker: str) -> dict | None:
    """Latest price, previous close and the date of the latest session. Cached for 60s.
    Returns None if the provider has nothing for this ticker."""
    ticker = ticker.upper().strip()
    now = time.time()
    hit = _QUOTE_CACHE.get(ticker)
    if hit and now - hit[0] < 60:
        return hit[1]
    quote = None
    try:
        raw = yf.Ticker(ticker).history(period="5d", interval="1d", auto_adjust=False)
        closes = raw["Close"].dropna() if raw is not None and not raw.empty else None
        if closes is not None and len(closes):
            last = float(closes.iloc[-1])
            prev = float(closes.iloc[-2]) if len(closes) > 1 else last
            row = raw.loc[closes.index[-1]]
            quote = {
                "price": Decimal(str(last)),
                "prev_close": Decimal(str(prev)),
                "session_date": closes.index[-1].date(),
                "low": _dec(row.get("Low")),    # the latest session's range, used to sanity-check
                "high": _dec(row.get("High")),  # trades dated on or after that session
            }
    except Exception:
        quote = None
    _QUOTE_CACHE[ticker] = (now, quote)
    return quote


def get_quotes(tickers: list[str]) -> dict[str, dict | None]:
    if not tickers:
        return {}
    with ThreadPoolExecutor(max_workers=min(8, len(tickers))) as pool:
        return dict(zip(tickers, pool.map(get_quote, tickers)))


def get_fx_rates(currencies) -> dict[str, Decimal | None]:
    """Units of each currency per 1 USD (e.g. {'NZD': 1.73}). None if the rate is unavailable."""
    need = sorted({c for c in currencies if c != "USD"})
    quotes = get_quotes([f"USD{c}=X" for c in need])
    out: dict[str, Decimal | None] = {}
    for c in need:
        q = quotes.get(f"USD{c}=X")
        out[c] = q["price"] if q and q["price"] > 0 else None
    return out


_GROWTH_CACHE: dict[str, tuple[float, dict]] = {}


def get_growth(ticker: str) -> dict:
    """Analyst growth estimates (fractions, e.g. 0.15 = 15%). Never raises: missing items are None.
    rev_next / eps_next = next fiscal year, rev_curr / eps_curr = the current fiscal year."""
    ticker = ticker.upper().strip()
    now = time.time()
    hit = _GROWTH_CACHE.get(ticker)
    if hit and now - hit[0] < 900:
        return hit[1]

    out = {"rev_next": None, "rev_curr": None, "eps_next": None, "eps_curr": None}

    def pick(df, row):
        try:
            v = float(df.loc[row, "growth"])
            return v if v == v else None
        except Exception:
            return None

    t = yf.Ticker(ticker)
    try:
        rev = t.revenue_estimate
        out["rev_next"], out["rev_curr"] = pick(rev, "+1y"), pick(rev, "0y")
    except Exception:
        pass
    try:
        eps = t.earnings_estimate
        out["eps_next"], out["eps_curr"] = pick(eps, "+1y"), pick(eps, "0y")
    except Exception:
        pass
    _GROWTH_CACHE[ticker] = (now, out)
    return out


# ---- company profiles for the portfolio breakdown ----
import math  # noqa: E402

_PROFILE_CACHE: dict[str, tuple[float, dict]] = {}


def _fund_sectors(ticker: str) -> dict | None:
    """An ETF's own sector weights (e.g. {'technology': 0.31, ...}) if Yahoo provides them."""
    try:
        w = dict(yf.Ticker(ticker).funds_data.sector_weightings)
        out = {str(k): float(v) for k, v in w.items() if v is not None and math.isfinite(float(v)) and float(v) > 0}
        return out or None
    except Exception:
        return None


def get_profile(ticker: str) -> dict | None:
    """Sector, size, beta etc. for one ticker. Cached for an hour. None if unavailable."""
    ticker = ticker.upper().strip()
    now = time.time()
    hit = _PROFILE_CACHE.get(ticker)
    if hit and now - hit[0] < 3600:
        return hit[1]
    try:
        info = get_info(ticker)
    except Exception:
        return None

    def f(*keys):
        for k in keys:
            try:
                x = float(info.get(k))
                if math.isfinite(x):
                    return x
            except (TypeError, ValueError):
                pass
        return None

    qt = info.get("quoteType")
    profile = {
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "quote_type": qt,
        "beta": f("beta", "beta3Year"),
        "market_cap": f("marketCap"),
        "forward_pe": f("forwardPE"),
        "dividend_rate": f("dividendRate", "trailingAnnualDividendRate"),
        "sector_weights": _fund_sectors(ticker) if qt in ("ETF", "MUTUALFUND") else None,
    }
    _PROFILE_CACHE[ticker] = (now, profile)
    return profile


def get_profiles(tickers: list[str]) -> dict[str, dict | None]:
    if not tickers:
        return {}
    with ThreadPoolExecutor(max_workers=min(8, len(tickers))) as pool:
        return dict(zip(tickers, pool.map(get_profile, tickers)))


# ---- daily history for the portfolio value chart ----
_HISTORY_CACHE: dict[str, tuple[float, "pd.DataFrame"]] = {}


def get_price_history(ticker: str):
    """Daily close (adjusted for splits but not for dividends, so it matches the price you traded at)
    plus the split ratio on each day. Cached for 15 minutes. None if unavailable."""
    ticker = ticker.upper().strip()
    now = time.time()
    hit = _HISTORY_CACHE.get(ticker)
    if hit and now - hit[0] < 900:
        return hit[1]
    try:
        raw = yf.Ticker(ticker).history(period="max", interval="1d", auto_adjust=False, actions=True)
        if raw is None or raw.empty:
            return None
        df = pd.DataFrame({"close": raw["Close"]})
        df["split"] = raw["Stock Splits"] if "Stock Splits" in raw.columns else 0.0
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        df = df.dropna(subset=["close"])
    except Exception:
        return None
    _HISTORY_CACHE[ticker] = (now, df)
    return df


def get_price_histories(tickers: list[str]) -> dict:
    if not tickers:
        return {}
    with ThreadPoolExecutor(max_workers=min(8, len(tickers))) as pool:
        return dict(zip(tickers, pool.map(get_price_history, tickers)))


# ---- bulk closes and share counts for the market overview ----
_CLOSES_CACHE: dict[tuple, tuple[float, "pd.DataFrame"]] = {}


def get_closes(symbols: list[str], period: str = "1y", ttl: int = 300) -> "pd.DataFrame":
    """Daily closes (split-adjusted, not dividend-adjusted) for many symbols in one request.
    Columns are symbols, rows are dates. Symbols the provider has nothing for are simply missing."""
    key = (tuple(sorted(symbols)), period)
    now = time.time()
    hit = _CLOSES_CACHE.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    raw = yf.download(list(symbols), period=period, interval="1d", auto_adjust=False,
                      group_by="column", progress=False, threads=True)
    if raw is None or raw.empty:
        raise TickerNotFound("no price data returned")
    if isinstance(raw.columns, pd.MultiIndex):
        closes = raw["Close"]
    else:  # a single symbol comes back flat on older yfinance versions
        closes = raw[["Close"]].rename(columns={"Close": symbols[0]})
    closes = closes.copy()
    closes.index = pd.to_datetime(closes.index).tz_localize(None).normalize()
    closes = closes.dropna(how="all").dropna(axis=1, how="all")
    _CLOSES_CACHE[key] = (now, closes)
    return closes


def get_shares(ticker: str) -> float | None:
    """Shares outstanding, worked out from the provider's market cap and price. None if unavailable."""
    try:
        fi = yf.Ticker(ticker).fast_info
        cap, price = float(fi["marketCap"]), float(fi["lastPrice"])
        return cap / price if cap > 0 and price > 0 else None
    except Exception:
        return None
