from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, DecimalText


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Transaction(Base):
    """One row per buy / sell / dividend. Positions and P&L are derived from these."""
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    ticker: Mapped[str] = mapped_column(String(12), index=True)
    type: Mapped[str] = mapped_column(String(10))          # buy | sell | dividend
    trade_date: Mapped[date] = mapped_column(Date)
    quantity: Mapped[Decimal] = mapped_column(DecimalText)  # shares
    price: Mapped[Decimal] = mapped_column(DecimalText)     # per share (per-share amount for dividends)
    fees: Mapped[Decimal] = mapped_column(DecimalText, default=Decimal("0"))
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class CashBalance(Base):
    """A cash account (brokerage cash, savings, ...). Added to the portfolio's total value."""
    __tablename__ = "cash_balances"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(60))
    currency: Mapped[str] = mapped_column(String(3))
    amount: Mapped[Decimal] = mapped_column(DecimalText)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
