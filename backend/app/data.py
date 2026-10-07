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
            quote = {
                "price": Decimal(str(last)),
                "prev_close": Decimal(str(prev)),
                "session_date": closes.index[-1].date(),
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
