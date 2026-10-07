"""Builds candles + indicators for a timeframe.

Each timeframe means "the most recent <window>, drawn at <interval>".
We fetch extra history before the window so indicators are warmed up, then trim.
"""
import pandas as pd

from . import data
from .indicators import ema_on_bars, macd, rsi

# "ema" = which higher-timeframe 21-period EMA to overlay on the price pane.
TIMEFRAMES = {
    "D":   {"source": "intraday", "interval": "5m",  "period": "5d",  "window": {"sessions": 1},
            "ema": "hourly",  "label": "Latest session, 5-minute bars"},
    "W":   {"source": "intraday", "interval": "30m", "period": "1mo", "window": {"sessions": 5},
            "ema": "hourly",  "label": "Last 5 sessions, 30-minute bars"},
    "M":   {"source": "intraday", "interval": "1h",  "period": "3mo", "window": {"months": 1},
            "ema": "hourly",  "label": "Last month, hourly bars"},
    "Q":   {"source": "daily",                                        "window": {"months": 3},
            "ema": "daily",   "label": "Last 3 months, daily bars"},
    "YTD": {"source": "daily",                                        "window": {"ytd": True},
            "ema": "daily",   "label": "Year to date, daily bars"},
    "Y":   {"source": "daily",                                        "window": {"years": 1},
            "ema": "daily",   "label": "Last year, daily bars"},
    "5Y":  {"source": "weekly",                                       "window": {"years": 5},
            "ema": "monthly", "label": "Last 5 years, weekly bars"},
}

CHANGE_LABELS = {
    "D": "today", "W": "past 5 sessions", "M": "past month", "Q": "past 3 months",
    "YTD": "year to date", "Y": "past year", "5Y": "past 5 years",
}
EMA_LABELS = {"hourly": "EMA 21h", "daily": "EMA 21d", "monthly": "EMA 21m"}
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
    if window.get("ytd"):
        return df[df.index >= pd.Timestamp(year=df.index[-1].year, month=1, day=1)]
    cutoff = df.index[-1] - pd.DateOffset(**window)
    return df[df.index > cutoff]


def htf_closes(ticker: str, kind: str, daily: pd.DataFrame) -> pd.Series:
    """Closes of the higher-timeframe bars, indexed by bar START time."""
    if kind == "hourly":
        return data.get_intraday(ticker, "1h", "3mo")["close"]
    if kind == "daily":
        return daily["close"]
    # monthly: close of each month, labelled by the month's first trading day
    closes = daily["close"].resample("ME").last().dropna()
    starts = daily.index.to_series().resample("ME").first().loc[closes.index]
    closes.index = pd.DatetimeIndex(starts.values)
    return closes


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
    ind_ema = ema_on_bars(df["close"], htf_closes(ticker, cfg["ema"], daily), span=21)

    view = apply_window(df, cfg["window"])
    idx = view.index

    candles, volume = [], []
    for ts, r in view.iterrows():
        candles.append({"time": _sec(ts), "open": float(r["open"]), "high": float(r["high"]),
                        "low": float(r["low"]), "close": float(r["close"])})
        volume.append({"time": _sec(ts), "value": float(r["volume"]), "up": bool(r["close"] >= r["open"])})

    rsi_v = ind_rsi.loc[idx].dropna()
    macd_v = ind_macd.loc[idx]
    ema_v = ind_ema.loc[idx].dropna()

    # Quote: latest price vs the close just before the selected window began
    # (previous close for Daily, last year's close for YTD, a year ago for Annual, ...)
    price = float(df["close"].iloc[-1])
    before = df.loc[df.index < idx[0], "close"]
    base = float(before.iloc[-1]) if len(before) else float(view["open"].iloc[0])
    change_pct = (price / base - 1) * 100

    return {
        "ticker": ticker.upper(),
        "timeframe": timeframe,
        "label": cfg["label"],
        "intraday": cfg["source"] == "intraday",
        "quote": {"price": price, "change_pct": change_pct, "change_label": CHANGE_LABELS[timeframe]},
        "candles": candles,
        "volume": volume,
        "ema": {
            "label": EMA_LABELS[cfg["ema"]],
            "data": [{"time": _sec(ts), "value": float(v)} for ts, v in ema_v.items()],
        },
        "rsi": [{"time": _sec(ts), "value": float(v)} for ts, v in rsi_v.items()],
        "macd": [
            {"time": _sec(ts), "macd": float(r["macd"]), "signal": float(r["signal"]), "hist": float(r["hist"])}
            for ts, r in macd_v.iterrows()
        ],
    }
