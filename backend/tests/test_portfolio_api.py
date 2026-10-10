from datetime import date
from decimal import Decimal

from app import data

TRADE = {"ticker": " aapl ", "type": "buy", "trade_date": "2024-03-01", "quantity": "3", "price": "0.1", "fees": "1.25", "note": " first "}


def test_trades_need_a_login(fresh_client):
    assert fresh_client.get("/api/portfolio/transactions").status_code == 401
    assert fresh_client.post("/api/portfolio/transactions", json=TRADE).status_code == 401


def test_add_list_edit_delete(logged_in):
    client, _ = logged_in()
    row = client.post("/api/portfolio/transactions", json=TRADE).json()
    assert (row["ticker"], row["price"], row["note"]) == ("AAPL", "0.1", "first")      # exact decimals, tidied input
    client.post("/api/portfolio/transactions", json={**TRADE, "trade_date": "2024-05-01"})
    listed = client.get("/api/portfolio/transactions").json()
    assert [t["trade_date"] for t in listed] == ["2024-05-01", "2024-03-01"]            # newest first

    edited = client.put(f"/api/portfolio/transactions/{row['id']}", json={**TRADE, "ticker": "msft", "type": "sell", "trade_date": "2024-06-10", "quantity": "2.5", "price": "410.25"}).json()
    assert (edited["ticker"], edited["type"], edited["quantity"]) == ("MSFT", "sell", "2.5")
    assert client.delete(f"/api/portfolio/transactions/{row['id']}").status_code == 204
    assert len(client.get("/api/portfolio/transactions").json()) == 1


def test_bad_input_is_rejected(logged_in):
    client, _ = logged_in()
    for bad in ({"quantity": "0"}, {"quantity": "-1"}, {"price": "-5"}, {"fees": "-1"}, {"ticker": "NO WAY!"},
                {"trade_date": "2999-01-01"}, {"type": "short"}):
        assert client.post("/api/portfolio/transactions", json={**TRADE, **bad}).status_code == 422, bad


def test_people_cannot_see_or_change_each_others_data(logged_in):
    alice, _ = logged_in("alice")
    bob, _ = logged_in("bob")
    tx = alice.post("/api/portfolio/transactions", json=TRADE).json()
    cash = alice.post("/api/portfolio/cash", json={"currency": "NZD", "amount": "500"}).json()

    assert bob.get("/api/portfolio/transactions").json() == []
    assert bob.put(f"/api/portfolio/transactions/{tx['id']}", json=TRADE).status_code == 404
    assert bob.delete(f"/api/portfolio/transactions/{tx['id']}").status_code == 404
    assert bob.put(f"/api/portfolio/cash/{cash['id']}", json={"currency": "NZD", "amount": "1"}).status_code == 404
    assert bob.delete(f"/api/portfolio/cash/{cash['id']}").status_code == 404
    assert bob.get("/api/portfolio/summary").json()["cash"] == []
    assert len(alice.get("/api/portfolio/transactions").json()) == 1                       # nothing of Alice's was touched


def test_summary_converts_currency_and_adds_cash(logged_in, monkeypatch):
    client, _ = logged_in()
    monkeypatch.setattr(data, "get_quotes", lambda ts: {t: {"price": Decimal("200"), "prev_close": Decimal("190"), "session_date": date(2026, 10, 6)} for t in ts})
    monkeypatch.setattr(data, "get_fx_rates", lambda cs: {c: Decimal("2") for c in cs if c != "USD"})
    client.post("/api/portfolio/transactions", json={"ticker": "aapl", "type": "buy", "trade_date": "2026-01-05", "quantity": "10", "price": "150"})
    client.post("/api/portfolio/cash", json={"currency": "NZD", "amount": "1000"})
    totals = client.get("/api/portfolio/summary?currency=NZD").json()["totals"]
    assert totals["market_value"] == 4000 and totals["cash"] == 1000 and totals["total_value"] == 5000   # 10 x $200 x 2, plus cash
    assert client.get("/api/portfolio/summary?currency=XXX").status_code == 400
