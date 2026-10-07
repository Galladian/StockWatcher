import re
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import data
from .auth import current_user
from .db import get_db
from .models import Transaction, User
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


@router.delete("/transactions/{tx_id}", status_code=204)
def delete_transaction(tx_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    # Filtering by user_id means you can only ever touch your own rows
    tx = db.scalar(select(Transaction).where(Transaction.id == tx_id, Transaction.user_id == user.id))
    if tx is None:
        raise HTTPException(404, "Transaction not found")
    db.delete(tx)
    db.commit()


@router.get("/summary")
def summary(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Current holdings, value, day change and P&L, worked out from the ledger."""
    txs = db.scalars(select(Transaction).where(Transaction.user_id == user.id)).all()
    quotes = data.get_quotes(sorted({t.ticker for t in txs}))
    return compute_portfolio(txs, quotes)
