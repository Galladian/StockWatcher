import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss
    out = 100 - 100 / (1 + rs)
    # No losses at all -> RSI is 100
    return out.where(avg_loss != 0, 100.0).where(avg_gain.notna())


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    line = ema_fast - ema_slow
    sig = line.ewm(span=signal, adjust=False).mean()
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def ema_on_bars(chart_close: pd.Series, htf_close: pd.Series, span: int = 21) -> pd.Series:
    """EMA of a HIGHER timeframe, evaluated at every bar of a (possibly finer) chart.

    htf_close: closes of the higher-timeframe bars, indexed by each bar's START time.
    The EMA is computed over the full htf history (so it is warmed up), then for each
    chart bar we take the previous completed htf bar's EMA and blend in the chart bar's
    close: alpha*close + (1-alpha)*prev. That is the value the htf EMA would have if the
    current htf bar closed right now, with no look-ahead. When the chart and htf bars
    are the same size this reduces to the ordinary EMA.
    """
    alpha = 2 / (span + 1)
    prev = htf_close.ewm(span=span, adjust=False).mean().shift(1)

    left = pd.DataFrame({"t": chart_close.index, "close": chart_close.values}).sort_values("t")
    right = pd.DataFrame({"start": htf_close.index, "prev": prev.values}).sort_values("start")
    m = pd.merge_asof(left, right, left_on="t", right_on="start", direction="backward")

    out = alpha * m["close"] + (1 - alpha) * m["prev"]
    out.index = pd.DatetimeIndex(m["t"])
    return out.reindex(chart_close.index)
