"""Tests for core.finance.returns.

Tests the module-level functions directly (not via PortfolioCalculator).
"""

from decimal import Decimal

import pytest

from portfolio_tracker.core.finance.returns import (
    allocation_by_isin,
    allocation_by_type,
    total_cost_basis,
    total_unrealized_pnl,
    total_value,
)
from portfolio_tracker.core.models import AssetType, Holding


def _holding(isin, asset_type, shares, cost_basis, current_price=None):
    return Holding(
        portfolio_id=1,
        isin=isin,
        asset_type=AssetType(asset_type),
        shares=Decimal(str(shares)),
        cost_basis=Decimal(str(cost_basis)),
        current_price=Decimal(str(current_price)) if current_price else None,
    )


class TestTotalValue:
    def test_single_holding(self):
        # 10 shares × €200 = €2000
        holdings = [_holding("ISIN1", "etf", 10, 1500, 200)]
        assert total_value(holdings) == Decimal("2000")

    def test_multiple_holdings(self):
        holdings = [
            _holding("ISIN1", "stock", 10, 1500, 200),  # 2000
            _holding("ISIN2", "etf", 5, 2000, 500),      # 2500
        ]
        assert total_value(holdings) == Decimal("4500")

    def test_holding_without_price_excluded(self):
        holdings = [
            _holding("ISIN1", "stock", 10, 1500, 200),  # 2000
            _holding("ISIN2", "etf", 5, 2000),           # no price
        ]
        assert total_value(holdings) == Decimal("2000")

    def test_all_without_price(self):
        holdings = [_holding("ISIN1", "stock", 10, 1500)]
        assert total_value(holdings) == Decimal("0")

    def test_empty(self):
        assert total_value([]) == Decimal("0")


class TestTotalCostBasis:
    def test_single(self):
        holdings = [_holding("ISIN1", "etf", 10, 1500)]
        assert total_cost_basis(holdings) == Decimal("1500")

    def test_multiple(self):
        holdings = [
            _holding("ISIN1", "etf", 10, 1500),
            _holding("ISIN2", "stock", 5, 2000),
        ]
        assert total_cost_basis(holdings) == Decimal("3500")

    def test_includes_unpriced_holdings(self):
        # Cost basis is always included, even without price
        holdings = [
            _holding("ISIN1", "etf", 10, 1500, 200),
            _holding("ISIN2", "stock", 5, 2000),  # no price
        ]
        assert total_cost_basis(holdings) == Decimal("3500")

    def test_empty(self):
        assert total_cost_basis([]) == Decimal("0")


class TestTotalUnrealizedPnL:
    def test_profit(self):
        holdings = [_holding("ISIN1", "stock", 10, 1500, 200)]  # value=2000
        assert total_unrealized_pnl(holdings) == Decimal("500")

    def test_loss(self):
        holdings = [_holding("ISIN1", "stock", 10, 1500, 100)]  # value=1000
        assert total_unrealized_pnl(holdings) == Decimal("-500")

    def test_breakeven(self):
        holdings = [_holding("ISIN1", "stock", 10, 1500, 150)]  # value=1500
        assert total_unrealized_pnl(holdings) == Decimal("0")


class TestAllocationByType:
    def test_single_type(self):
        holdings = [_holding("ISIN1", "etf", 10, 1000, 100)]  # value=1000
        alloc = allocation_by_type(holdings)
        assert alloc["etf"] == Decimal("100.00")

    def test_equal_split(self):
        holdings = [
            _holding("ISIN1", "stock", 10, 1000, 100),   # value=1000
            _holding("ISIN2", "crypto", 1, 500, 1000),   # value=1000
        ]
        alloc = allocation_by_type(holdings)
        assert alloc["stock"] == Decimal("50.00")
        assert alloc["crypto"] == Decimal("50.00")

    def test_unpriced_excluded(self):
        holdings = [
            _holding("ISIN1", "stock", 10, 1000, 100),  # value=1000, included
            _holding("ISIN2", "etf", 5, 500),            # no price, excluded
        ]
        alloc = allocation_by_type(holdings)
        assert alloc.get("stock") == Decimal("100.00")
        assert "etf" not in alloc

    def test_empty(self):
        assert allocation_by_type([]) == {}

    def test_all_unpriced(self):
        holdings = [_holding("ISIN1", "etf", 10, 1000)]
        assert allocation_by_type(holdings) == {}


class TestAllocationByISIN:
    def test_single_holding(self):
        holdings = [_holding("IE00BK5BQT80", "etf", 10, 1000, 100)]
        alloc = allocation_by_isin(holdings)
        assert alloc["IE00BK5BQT80"] == Decimal("100.00")

    def test_equal_split(self):
        holdings = [
            _holding("ISIN1", "stock", 10, 1000, 100),  # 1000
            _holding("ISIN2", "stock", 5, 500, 200),     # 1000
        ]
        alloc = allocation_by_isin(holdings)
        assert alloc["ISIN1"] == Decimal("50.00")
        assert alloc["ISIN2"] == Decimal("50.00")

    def test_unequal_split(self):
        holdings = [
            _holding("ISIN1", "etf", 7, 700, 100),   # 700
            _holding("ISIN2", "bond", 3, 300, 100),   # 300
        ]
        alloc = allocation_by_isin(holdings)
        assert alloc["ISIN1"] == Decimal("70.00")
        assert alloc["ISIN2"] == Decimal("30.00")

    def test_empty(self):
        assert allocation_by_isin([]) == {}
