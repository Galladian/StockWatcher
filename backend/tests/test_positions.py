from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace as NS

from app.positions import compute_portfolio


def tx(i, kind, day, qty, price, fees="0"):
    return NS(id=i, ticker="XYZ", type=kind, trade_date=date.fromisoformat(day), quantity=D(qty), price=D(price), fees=D(fees))


QUOTE = {"XYZ": {"price": D("150"), "prev_close": D("148"), "session_date": date(2026, 10, 6)}}


def test_average_cost_realised_profit_dividends_and_day_change():
    txs = [tx(1, "buy", "2026-01-02", "10", "100"), tx(2, "buy", "2026-02-01", "5", "120", "1"), tx(3, "sell", "2026-03-01", "5", "130", "2"),
           tx(4, "dividend", "2026-04-01", "10", "0.5"), tx(5, "buy", "2026-10-06", "4", "149")]
    result = compute_portfolio(txs, QUOTE)
    holding, totals = result["holdings"][0], result["totals"]
    assert holding["shares"] == 14 and abs(holding["cost_basis"] - 1663.3333333) < 1e-4
    assert abs(totals["realized"] - 114.3333333) < 1e-4 and totals["dividends"] == 5.0
    assert totals["market_value"] == 2100
    assert abs(totals["day_change"] - 24) < 1e-9        # 10 shares x $2, plus 4 bought during the day x $1


def test_an_existing_holding_entered_with_a_recent_date_does_not_look_like_a_huge_gain_today():
    quote = {"XYZ": {**QUOTE["XYZ"], "low": D("147"), "high": D("151")}}
    result = compute_portfolio([tx(1, "buy", "2026-10-07", "20", "120.74")], quote)
    assert abs(result["totals"]["day_change"] - 40) < 1e-9          # 20 x ($150 - $148), not 20 x ($150 - $120.74)
    assert abs(result["totals"]["unrealized"] - 20 * (150 - 120.74)) < 1e-9


def test_selling_more_than_held_is_flagged_and_capped():
    txs = [tx(1, "buy", "2026-01-01", "2", "10"), tx(2, "sell", "2026-01-02", "5", "12")]
    result = compute_portfolio(txs, QUOTE)
    assert result["holdings"] == [] and any("only 2" in w for w in result["warnings"])
    assert result["totals"]["realized"] == 4.0
