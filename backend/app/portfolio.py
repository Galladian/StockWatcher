import re
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import data
from .auth import current_user
from .breakdown import compute_breakdown
from .currency import SUPPORTED, convert, scale_summary
from .history import compute_history
from .db import get_db
from .models import CashBalance, Transaction, User
from .positions import compute_portfolio

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

_TICKER = re.compile(r"^[A-Z0-9.\-]{1,10}$")


class TransactionIn(BaseModel):
    ticker: str
    type: Literal["buy", "sell", "dividend"]
    trade_date: date
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    price: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    fees: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=6)
    note: str | None = Field(default=None, max_length=200)

    @field_validator("ticker")
    @classmethod
    def _ticker(cls, v: str) -> str:
        v = v.strip().upper()
        if not _TICKER.match(v):
            raise ValueError("Ticker must be 1-10 letters, numbers, dots or dashes")
        return v

    @field_validator("trade_date")
    @classmethod
    def _not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Date can't be in the future")
        return v

    @field_validator("note")
    @classmethod
    def _blank_note(cls, v: str | None) -> str | None:
        return (v or "").strip() or None


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ticker: str
    type: str
    trade_date: date
    quantity: Decimal
    price: Decimal
    fees: Decimal
    note: str | None


@router.get("/transactions", response_model=list[TransactionOut])
def list_transactions(user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = (
        select(Transaction)
        .where(Transaction.user_id == user.id)
        .order_by(Transaction.trade_date.desc(), Transaction.id.desc())
    )
    return db.scalars(stmt).all()


@router.post("/transactions", response_model=TransactionOut, status_code=201)
def add_transaction(body: TransactionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    tx = Transaction(user_id=user.id, **body.model_dump())
    db.add(tx)
    db.commit()
    return tx


@router.put("/transactions/{tx_id}", response_model=TransactionOut)
def update_transaction(tx_id: int, body: TransactionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    # Filtering by user_id means you can only ever touch your own rows
    tx = db.scalar(select(Transaction).where(Transaction.id == tx_id, Transaction.user_id == user.id))
    if tx is None:
        raise HTTPException(404, "Transaction not found")
    for field, value in body.model_dump().items():
        setattr(tx, field, value)
    db.commit()
    return tx


@router.delete("/transactions/{tx_id}", status_code=204)
def delete_transaction(tx_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    # Filtering by user_id means you can only ever touch your own rows
    tx = db.scalar(select(Transaction).where(Transaction.id == tx_id, Transaction.user_id == user.id))
    if tx is None:
        raise HTTPException(404, "Transaction not found")
    db.delete(tx)
    db.commit()


class CashIn(BaseModel):
    label: str | None = Field(default=None, max_length=60)
    currency: str
    amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)

    @field_validator("currency")
    @classmethod
    def _currency(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in SUPPORTED:
            raise ValueError(f"Currency must be one of {', '.join(SUPPORTED)}")
        return v

    @field_validator("label")
    @classmethod
    def _label(cls, v: str | None) -> str | None:
        return (v or "").strip() or None


def _own_cash(db: Session, user: User, cash_id: int) -> CashBalance:
    row = db.scalar(select(CashBalance).where(CashBalance.id == cash_id, CashBalance.user_id == user.id))
    if row is None:
        raise HTTPException(404, "Cash account not found")
    return row


@router.post("/cash", status_code=201)
def add_cash(body: CashIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = CashBalance(user_id=user.id, label=body.label or "Cash", currency=body.currency, amount=body.amount)
    db.add(row)
    db.commit()
    return {"id": row.id}


@router.put("/cash/{cash_id}")
def update_cash(cash_id: int, body: CashIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = _own_cash(db, user, cash_id)
    row.label, row.currency, row.amount = body.label or "Cash", body.currency, body.amount
    db.commit()
    return {"id": row.id}


@router.delete("/cash/{cash_id}", status_code=204)
def delete_cash(cash_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(_own_cash(db, user, cash_id))
    db.commit()


def _build_summary(currency: str, user: User, db: Session) -> dict:
    """Holdings, cash, total value, day change and P&L, shown in the chosen currency."""
    currency = currency.upper()
    if currency not in SUPPORTED:
        raise HTTPException(400, f"currency must be one of {SUPPORTED}")

    txs = db.scalars(select(Transaction).where(Transaction.user_id == user.id)).all()
    cash_rows = db.scalars(select(CashBalance).where(CashBalance.user_id == user.id).order_by(CashBalance.id)).all()

    result = compute_portfolio(txs, data.get_quotes(sorted({t.ticker for t in txs})))  # in USD
    warnings = result["warnings"]

    rates = data.get_fx_rates({currency, *(c.currency for c in cash_rows)})
    shown = currency
    if currency != "USD" and not rates.get(currency):
        warnings.append(f"The {currency} exchange rate is unavailable right now, so values are shown in USD.")
        shown = "USD"
    factor = 1.0 if shown == "USD" else float(rates[shown])
    scale_summary(result, factor)

    cash_out, cash_total = [], Decimal(0)
    for c in cash_rows:
        value = convert(c.amount, c.currency, shown, rates)
        if value is None:
            warnings.append(f"Cash '{c.label}': the {c.currency} exchange rate is unavailable, so it is left out of the total.")
        else:
            cash_total += value
        cash_out.append({"id": c.id, "label": c.label, "currency": c.currency,
                         "amount": float(c.amount), "value": None if value is None else float(value)})

    totals = result["totals"]
    total_value = totals["market_value"] + float(cash_total)
    totals["cash"] = float(cash_total)
    totals["total_value"] = total_value
    # Weights are shares of the whole portfolio, cash included
    for h in result["holdings"]:
        h["weight"] = h["market_value"] / total_value * 100 if h["market_value"] is not None and total_value > 0 else None
    for c in cash_out:
        c["weight"] = c["value"] / total_value * 100 if c["value"] is not None and total_value > 0 else None

    result.update(currency=shown, fx_rate=factor if shown != "USD" else None, cash=cash_out)
    return result


@router.get("/summary")
def summary(currency: str = Query("NZD"), user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _build_summary(currency, user, db)


@router.get("/breakdown")
def breakdown(currency: str = Query("NZD"), user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Sector split, concentration and other portfolio characteristics, in the chosen currency."""
    s = _build_summary(currency, user, db)
    profiles = data.get_profiles([h["ticker"] for h in s["holdings"]])
    out = compute_breakdown(s, profiles)
    out["currency"] = s["currency"]
    out["warnings"] = s["warnings"] + out["warnings"]
    return out


@router.get("/history")
def history(currency: str = Query("NZD"), user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Daily value of your stocks, and the money you put in, in the chosen currency."""
    currency = currency.upper()
    if currency not in SUPPORTED:
        raise HTTPException(400, f"currency must be one of {SUPPORTED}")
    txs = db.scalars(select(Transaction).where(Transaction.user_id == user.id)).all()
    result = compute_history(txs, data.get_price_histories(sorted({t.ticker for t in txs})))
    warnings = result["warnings"]

    rates = data.get_fx_rates({currency})
    shown = currency
    if currency != "USD" and not rates.get(currency):
        warnings.append(f"The {currency} exchange rate is unavailable right now, so values are shown in USD.")
        shown = "USD"
    factor = 1.0 if shown == "USD" else float(rates[shown])
    for p in result["points"]:  # today's rate for the whole history, like the rest of the app
        for k in ("value", "invested", "income"):
            p[k] = round(p[k] * factor, 2)
    return {"currency": shown, "fx_rate": factor if shown != "USD" else None, "points": result["points"], "warnings": warnings}
