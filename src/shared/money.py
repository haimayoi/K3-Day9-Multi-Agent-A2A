"""Money rounding helper — use this everywhere, don't call round() directly.

Plain round() uses banker's rounding and floating point can make e.g.
round(2.675, 2) == 2.67 instead of 2.68. Decimal + ROUND_HALF_UP avoids that
surprise and keeps every agent's rounding identical.
"""

from decimal import ROUND_HALF_UP, Decimal


def round_brl(value: float) -> float:
    """Round a BRL amount to exactly 2 decimal places."""
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def sum_brl(values) -> float:
    """Sum a list of BRL amounts and round the result once, at the end."""
    total = sum(Decimal(str(v)) for v in values)
    return float(total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def within_tolerance(a: float, b: float, tolerance: float) -> bool:
    """True if |a - b| <= tolerance (use for the 0.10 BRL reconciliation check)."""
    return abs(Decimal(str(a)) - Decimal(str(b))) <= Decimal(str(tolerance))
