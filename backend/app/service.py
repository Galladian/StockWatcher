"""Builds candles + indicators for a timeframe.

Each timeframe means "the most recent <window>, drawn at <interval>".
We fetch extra history before the window so RSI/MACD are warmed up, then trim.
"""
import pandas as pd

from . import data
from .indicators import macd, rsi

TIMEFRAMES = {
    "D":  {"source": "intraday", "interval": "5m",  "period": "5d",  "window": {"sessions": 1},
           "label": "Latest session, 5-minute bars"},
    "W":  {"source": "intraday", "interval": "30m", "period": "1mo", "window": {"sessions": 5},
           "label": "Last 5 sessions, 30-minute bars"},
    "M":  {"source": "intraday", "interval": "1h",  "period": "3mo", "window": {"months": 1},
           "label": "Last month, hourly bars"},
    "Q":  {"source": "daily",                                        "window": {"months": 3},
           "label": "Last 3 months, daily bars"},
    "Y":  {"source": "daily",                                        "window": {"years": 1},
           "label": "Last year, daily bars"},
    "5Y": {"source": "weekly",                                       "window": {"years": 5},
           "label": "Last 5 years, weekly bars"},
}

EPOCH = pd.Timestamp("1970-01-01")


def resample_ohlcv(daily: pd.DataFrame, rule: str) -> pd.DataFrame:
    agg = daily.resample(rule).agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    # Label each bar with its last real trading day (not a future period-end date)
    last_day = daily.index.to_series().resample(rule).last()
    agg = agg.dropna(subset=["open"])
    agg.index = pd.DatetimeIndex(last_day.loc[agg.index].values)
    return agg


def apply_window(df: pd.DataFrame, window: dict) -> pd.DataFrame:
    if "sessions" in window:
        days = df.index.normalize().unique()[-window["sessions"]:]
        return df[df.index.normalize().isin(days)]
    cutoff = df.index[-1] - pd.DateOffset(**window)
    return df[df.index > cutoff]


def _sec(ts: pd.Timestamp) -> int:
    # Exchange wall-clock time encoded as UTC seconds, so the chart shows market time.
    return int((ts - EPOCH).total_seconds())


def build_chart(ticker: str, timeframe: str) -> dict:
    cfg = TIMEFRAMES[timeframe]
    daily = data.get_daily(ticker)

    if cfg["source"] == "intraday":
        df = data.get_intraday(ticker, cfg["interval"], cfg["period"])
    elif cfg["source"] == "weekly":
        df = resample_ohlcv(daily, "W-FRI")
    else:
        df = daily

    # Indicators on the full fetched history (warm-up), then trim for display.
    ind_rsi = rsi(df["close"])
    ind_macd = macd(df["close"])

    view = apply_window(df, cfg["window"])
    idx = view.index

    candles, volume = [], []
    for ts, r in view.iterrows():
        candles.append({"time": _sec(ts), "open": float(r["open"]), "high": float(r["high"]),
                        "low": float(r["low"]), "close": float(r["close"])})
        volume.append({"time": _sec(ts), "value": float(r["volume"]), "up": bool(r["close"] >= r["open"])})

    rsi_v = ind_rsi.loc[idx].dropna()
    macd_v = ind_macd.loc[idx]

    # Quote: latest price vs the previous trading day's close
    price = float(df["close"].iloc[-1])
    last_day = df.index[-1].normalize()
    prev = daily.loc[daily.index < last_day, "close"]
    change_pct = float((price / prev.iloc[-1] - 1) * 100) if len(prev) else None

    return {
        "ticker": ticker.upper(),
        "timeframe": timeframe,
        "label": cfg["label"],
        "intraday": cfg["source"] == "intraday",
        "quote": {"price": price, "change_pct": change_pct},
        "candles": candles,
        "volume": volume,
        "rsi": [{"time": _sec(ts), "value": float(v)} for ts, v in rsi_v.items()],
        "macd": [
            {"time": _sec(ts), "macd": float(r["macd"]), "signal": float(r["signal"]), "hist": float(r["hist"])}
            for ts, r in macd_v.iterrows()
        ],
    }
