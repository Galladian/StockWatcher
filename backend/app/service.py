"""Turns daily data into the candles + indicators for a chosen timeframe."""
import pandas as pd
from .indicators import macd, rsi

# rule: pandas resample rule (None = keep daily). bars: how many candles to display.
TIMEFRAMES = {
    "D":  {"rule": None,    "bars": 180},
    "W":  {"rule": "W-FRI", "bars": 156},
    "M":  {"rule": "ME",    "bars": 120},
    "Q":  {"rule": "QE",    "bars": 80},
    "Y":  {"rule": "YE",    "bars": 30},
    "5Y": {"rule": "W-FRI", "bars": 260},  # five years of weekly candles
}


def resample_ohlcv(daily: pd.DataFrame, rule: str | None) -> pd.DataFrame:
    if rule is None:
        return daily
    agg = daily.resample(rule).agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    # Label each bar with its last real trading day (not a future period-end date)
    last_day = daily.index.to_series().resample(rule).last()
    agg = agg.dropna(subset=["open"])
    agg.index = pd.DatetimeIndex(last_day.loc[agg.index].values)
    return agg


def build_chart(daily: pd.DataFrame, timeframe: str) -> dict:
    cfg = TIMEFRAMES[timeframe]
    df = resample_ohlcv(daily, cfg["rule"])

    # Indicators are computed on the FULL history (warm-up), then trimmed for display.
    ind_rsi = rsi(df["close"])
    ind_macd = macd(df["close"])

    view = df.tail(cfg["bars"])
    idx = view.index

    def t(ts) -> str:
        return ts.strftime("%Y-%m-%d")

    candles, volume = [], []
    for ts, r in view.iterrows():
        up = r["close"] >= r["open"]
        candles.append({"time": t(ts), "open": float(r["open"]), "high": float(r["high"]),
                        "low": float(r["low"]), "close": float(r["close"])})
        volume.append({"time": t(ts), "value": float(r["volume"]), "up": bool(up)})

    rsi_v = ind_rsi.loc[idx].dropna()
    macd_v = ind_macd.loc[idx]

    return {
        "candles": candles,
        "volume": volume,
        "rsi": [{"time": t(ts), "value": float(v)} for ts, v in rsi_v.items()],
        "macd": [
            {"time": t(ts), "macd": float(r["macd"]), "signal": float(r["signal"]), "hist": float(r["hist"])}
            for ts, r in macd_v.iterrows()
        ],
    }
