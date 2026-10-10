"""Create a demo account with a realistic but entirely fictional portfolio, to show people without
exposing real finances.

    python -m app.seed_demo                  create user 'demo' (a random password is printed once)
    python -m app.seed_demo --reset          wipe and rebuild the demo portfolio
    DEMO_PASSWORD=... python -m app.seed_demo

Prices are the real closing prices on each trade date, looked up from Yahoo, so the numbers look believable.
"""
import argparse
import os
import re
import secrets
import sys
from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
from sqlalchemy import delete, select

from . import data
from .db import SessionLocal, init_db
from .models import CashBalance, Transaction, User
from .security import hash_password

# (ticker, type, days ago, shares)
PLAN = [
    ("AAPL", "buy", 400, 25), ("MSFT", "buy", 380, 12), ("NVDA", "buy", 350, 30), ("SPY", "buy", 330, 15),
    ("JPM", "buy", 300, 14), ("XOM", "buy", 270, 30), ("AMZN", "buy", 240, 18), ("LLY", "buy", 200, 5),
    ("COST", "buy", 160, 4), ("NVDA", "sell", 90, 10), ("MSFT", "buy", 60, 6), ("GOOGL", "buy", 30, 12),
]
CASH = [("Savings", "NZD", "6500"), ("Brokerage cash", "USD", "1800")]
FEES = Decimal("1.00")


def _weekday(d: date) -> date:
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _close_on(frame: pd.DataFrame, d: date) -> Decimal | None:
    closes = frame["close"]
    closes = closes[closes.index <= pd.Timestamp(d)]
    return Decimal(str(round(float(closes.iloc[-1]), 2))) if len(closes) else None


def seed(username: str, password: str, reset: bool = False, today: date | None = None) -> dict:
    init_db()
    today = today or date.today()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            user = User(username=username, password_hash=hash_password(password))
            db.add(user)
            db.flush()
        else:
            if db.scalar(select(Transaction.id).where(Transaction.user_id == user.id)) and not reset:
                raise SystemExit(f"'{username}' already has data. Use --reset to rebuild it.")
            user.password_hash = hash_password(password)
            db.execute(delete(Transaction).where(Transaction.user_id == user.id))
            db.execute(delete(CashBalance).where(CashBalance.user_id == user.id))

        frames = {t: data.get_price_history(t) for t in {p[0] for p in PLAN}}
        added, skipped = 0, set()
        for ticker, kind, days_ago, shares in PLAN:
            frame = frames.get(ticker)
            trade_date = _weekday(today - timedelta(days=days_ago))
            price = _close_on(frame, trade_date) if frame is not None and not frame.empty else None
            if price is None or (kind == "sell" and ticker in skipped):
                skipped.add(ticker)
                continue
            db.add(Transaction(user_id=user.id, ticker=ticker, type=kind, trade_date=trade_date,
                               quantity=Decimal(shares), price=price, fees=FEES, note=None))
            added += 1
        for label, currency, amount in CASH:
            db.add(CashBalance(user_id=user.id, label=label, currency=currency, amount=Decimal(amount)))
        db.commit()
    return {"transactions": added, "skipped": sorted(skipped)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--username", default="demo")
    parser.add_argument("--reset", action="store_true", help="wipe and rebuild an existing demo portfolio")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9_.-]{3,50}", args.username):
        sys.exit("Username must be 3-50 characters: letters, numbers, dots, dashes, underscores.")

    supplied = os.environ.get("DEMO_PASSWORD")
    password = supplied or secrets.token_urlsafe(12)
    result = seed(args.username, password, reset=args.reset)
    print(f"Added {result['transactions']} trades and {len(CASH)} cash accounts for '{args.username}'.")
    if result["skipped"]:
        print(f"No price history for: {', '.join(result['skipped'])} (skipped).")
    print(f"\nUsername: {args.username}")
    print(f"Password: {password}" if not supplied else "Password: (the DEMO_PASSWORD you provided)")


if __name__ == "__main__":
    main()
