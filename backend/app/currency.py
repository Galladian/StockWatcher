"""Currency helpers. All holdings are in USD; rates are 'units of currency per 1 USD'."""
from decimal import Decimal

SUPPORTED = ["NZD", "USD", "AUD", "GBP", "EUR", "CAD", "JPY"]  # NZD first on purpose

_TOTAL_KEYS = ["market_value", "cost_basis", "day_change", "unrealized", "realized", "dividends", "total_return"]
_HOLDING_KEYS = ["avg_cost", "cost_basis", "price", "prev_close", "market_value", "day_change", "unrealized"]


def _per_usd(rates: dict, ccy: str) -> Decimal | None:
    return Decimal(1) if ccy == "USD" else rates.get(ccy)


def convert(amount: Decimal, src: str, dst: str, rates: dict) -> Decimal | None:
    """Convert via USD. None if either rate is unavailable."""
    a, b = _per_usd(rates, src), _per_usd(rates, dst)
    if not a or not b:
        return None
    return amount / a * b


def scale_summary(summary: dict, factor: float) -> None:
    """Multiply every money figure in a USD summary by `factor` (in place). Percentages are unchanged."""
    if factor == 1.0:
        return
    for k in _TOTAL_KEYS:
        summary["totals"][k] *= factor
    for h in summary["holdings"]:
        for k in _HOLDING_KEYS:
            if h.get(k) is not None:
                h[k] *= factor
