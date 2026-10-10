import numpy as np
import pandas as pd

from app import universe
from app.markets import period_change


def test_period_changes_match_an_independent_calculation():
    idx = pd.bdate_range("2025-01-01", "2026-10-07")
    close = pd.Series(np.linspace(100, 300, len(idx)) + np.sin(np.arange(len(idx))), index=idx)
    base = {"1D": close.iloc[-2], "1W": close[:"2026-09-30"].iloc[-1], "1M": close[:"2026-09-07"].iloc[-1],
            "3M": close[:"2026-07-07"].iloc[-1], "YTD": close[:"2025-12-31"].iloc[-1], "1Y": close[:"2025-10-07"].iloc[-1]}
    for period, start in base.items():
        assert abs(period_change(close, period)["pct"] - (close.iloc[-1] / start - 1) * 100) < 1e-9, period


def test_not_enough_history_gives_nothing_rather_than_a_wrong_number():
    idx = pd.bdate_range("2026-01-05", "2026-10-07")
    short = pd.Series(np.linspace(100, 120, len(idx)), index=idx)
    assert period_change(short, "1Y") is None and period_change(short, "YTD") is None
    assert period_change(short.iloc[:1], "1D") is None


def test_the_s_and_p_list_is_read_from_the_wikipedia_table():
    html = """<table id="constituents"><thead><tr><th>Symbol</th><th>Security</th><th>GICS Sector</th></tr></thead><tbody>
    <tr><td><a href="#">AAPL</a></td><td>Apple Inc.</td><td>Information Technology</td></tr>
    <tr><td>BRK.B</td><td>Berkshire Hathaway</td><td>Financials</td></tr></tbody></table>"""
    assert universe.parse_wikipedia(html) == [("AAPL", "Apple Inc.", "Information Technology"), ("BRK-B", "Berkshire Hathaway", "Financials")]


def test_the_built_in_fallback_list_is_sound():
    symbols = [s for s, _, _ in universe.FALLBACK]
    assert len(symbols) == len(set(symbols)) and len(symbols) > 100
