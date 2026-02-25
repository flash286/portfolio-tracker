"""Portfolio statistics calculator — backward-compatible wrapper.

The math has been extracted into focused sub-modules:
    core.tax      — German tax engine (Abgeltungssteuer, TFS, VP, FSA)
    core.finance  — Portfolio value and allocation calculations

Prefer importing directly from those modules:
    from portfolio_tracker.core.tax import calculate_german_tax
    from portfolio_tracker.core.tax.vorabpauschale import BASISZINS
    from portfolio_tracker.core.finance import total_value, allocation_by_isin

PortfolioCalculator is kept so that existing callers continue to work
without modification.
"""

from decimal import Decimal
from typing import Optional

from .finance import (
    allocation_by_isin,
    allocation_by_type,
    total_cost_basis,
    total_unrealized_pnl,
    total_value,
)
from .tax import (
    BASISZINS,
    VorabpauschaleResult,
    calculate_german_tax,
    calculate_vorabpauschale,
)

__all__ = [
    "BASISZINS",
    "VorabpauschaleResult",
    "PortfolioCalculator",
]


class PortfolioCalculator:
    """Thin delegation wrapper — all logic lives in core.tax / core.finance."""

    @staticmethod
    def total_value(holdings):
        return total_value(holdings)

    @staticmethod
    def total_cost_basis(holdings):
        return total_cost_basis(holdings)

    @staticmethod
    def total_unrealized_pnl(holdings):
        return total_unrealized_pnl(holdings)

    @staticmethod
    def allocation_by_type(holdings):
        return allocation_by_type(holdings)

    @staticmethod
    def allocation_by_isin(holdings):
        return allocation_by_isin(holdings)

    @staticmethod
    def calculate_german_tax(
        realized_gain: Decimal,
        freistellungsauftrag: Optional[Decimal] = None,
        teilfreistellung_rate: Decimal = Decimal("0"),
    ):
        return calculate_german_tax(realized_gain, freistellungsauftrag, teilfreistellung_rate)

    @staticmethod
    def calculate_vorabpauschale(*args, **kwargs):
        return calculate_vorabpauschale(*args, **kwargs)
