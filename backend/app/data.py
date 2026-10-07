"""Data provider layer. Only this file knows where prices come from.
To switch to Polygon/Tiingo/etc., keep get_daily()'s signature and swap the body."""
import time
import pandas as pd
import yfinance as yf

_CACHE: dict[str, tuple[float, pd.DataFrame]] = {}
_TTL_SECONDS = 300


class TickerNotFound(Exception):
    pass


def get_daily(ticker: str) -> pd.DataFrame:
    """Full daily OHLCV history, split/dividend adjusted.
    Columns: open, high, low, close, volume. Index: tz-naive DatetimeIndex."""
    ticker = ticker.upper().strip()
    now = time.time()
    hit = _CACHE.get(ticker)
    if hit and now - hit[0] < _TTL_SECONDS:
        return hit[1]

    raw = yf.Ticker(ticker).history(period="max", interval="1d", auto_adjust=True)
    if raw is None or raw.empty:
        raise TickerNotFound(ticker)

    df = raw.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    df = df.dropna(subset=["open", "high", "low", "close"])
    _CACHE[ticker] = (now, df)
    return df
