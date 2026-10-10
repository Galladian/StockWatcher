from datetime import date

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import data, seed_demo
from app.db import SessionLocal
from app.main import app
from app.models import CashBalance, Transaction, User

TODAY = date(2026, 10, 7)


def fake_history(skip=()):
    days = pd.bdate_range("2024-01-01", "2026-10-07")
    frame = pd.DataFrame({"close": 100.0, "split": 0.0}, index=days)
    return lambda ticker: None if ticker in skip else frame


def counts(name):
    with SessionLocal() as db:
        uid = db.scalar(select(User.id).where(User.username == name))
        return (db.scalar(select(func.count()).select_from(Transaction).where(Transaction.user_id == uid)),
                db.scalar(select(func.count()).select_from(CashBalance).where(CashBalance.user_id == uid)))


def test_seeds_a_realistic_portfolio_the_demo_user_can_log_in_to(monkeypatch):
    monkeypatch.setattr(data, "get_price_history", fake_history())
    result = seed_demo.seed("demo-a", "demo-password-1", today=TODAY)
    assert result == {"transactions": len(seed_demo.PLAN), "skipped": []}
    assert counts("demo-a") == (len(seed_demo.PLAN), len(seed_demo.CASH))
    with SessionLocal() as db:
        dates = db.scalars(select(Transaction.trade_date).join(User).where(User.username == "demo-a")).all()
    assert all(d.weekday() < 5 for d in dates)                       # no trades on weekends
    client = TestClient(app, base_url="https://testserver")
    assert client.post("/api/auth/login", json={"username": "demo-a", "password": "demo-password-1"}).status_code == 200


def test_it_will_not_overwrite_existing_data_unless_asked(monkeypatch):
    monkeypatch.setattr(data, "get_price_history", fake_history())
    seed_demo.seed("demo-b", "demo-password-1", today=TODAY)
    with pytest.raises(SystemExit):
        seed_demo.seed("demo-b", "demo-password-2", today=TODAY)
    seed_demo.seed("demo-b", "demo-password-2", reset=True, today=TODAY)
    assert counts("demo-b") == (len(seed_demo.PLAN), len(seed_demo.CASH))   # rebuilt, not doubled


def test_a_stock_without_price_history_is_skipped_along_with_its_sale(monkeypatch):
    monkeypatch.setattr(data, "get_price_history", fake_history(skip={"NVDA"}))
    result = seed_demo.seed("demo-c", "demo-password-1", today=TODAY)
    assert result["skipped"] == ["NVDA"] and result["transactions"] == len(seed_demo.PLAN) - 2   # its buy and its sell
