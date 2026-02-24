"""Tests for PortfolioCalculator."""

from decimal import Decimal

import pytest

from portfolio_tracker.core.calculator import PortfolioCalculator
from portfolio_tracker.core.models import AssetType, Holding, TaxInfo


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
    def test_basic(self):
        holdings = [
            _holding("US0378331005", "stock", 10, 1500, 200),
            _holding("US9229087690", "etf", 5, 2000, 500),
        ]
        assert PortfolioCalculator.total_value(holdings) == Decimal("4500")

    def test_no_price(self):
        holdings = [_holding("US0378331005", "stock", 10, 1500)]
        assert PortfolioCalculator.total_value(holdings) == Decimal("0")

    def test_empty(self):
        assert PortfolioCalculator.total_value([]) == Decimal("0")


class TestPnL:
    def test_profit(self):
        holdings = [_holding("US0378331005", "stock", 10, 1500, 200)]
        assert PortfolioCalculator.total_unrealized_pnl(holdings) == Decimal("500")

    def test_loss(self):
        holdings = [_holding("US0378331005", "stock", 10, 1500, 100)]
        assert PortfolioCalculator.total_unrealized_pnl(holdings) == Decimal("-500")


class TestAllocation:
    def test_by_type(self):
        holdings = [
            _holding("US0378331005", "stock", 10, 1000, 100),
            _holding("CRYPTO-BTC", "crypto", 1, 500, 1000),
        ]
        alloc = PortfolioCalculator.allocation_by_type(holdings)
        assert alloc["stock"] == Decimal("50.00")
        assert alloc["crypto"] == Decimal("50.00")

    def test_by_isin(self):
        holdings = [
            _holding("US0378331005", "stock", 10, 1000, 100),
            _holding("US5949181045", "stock", 5, 500, 200),
        ]
        alloc = PortfolioCalculator.allocation_by_isin(holdings)
        assert alloc["US0378331005"] == Decimal("50.00")
        assert alloc["US5949181045"] == Decimal("50.00")


class TestGermanTax:
    def test_within_freistellungsauftrag(self):
        info = PortfolioCalculator.calculate_german_tax(
            Decimal("1500"), Decimal("2000")
        )
        assert info.taxable_gain == Decimal("0")
        assert info.total_tax == Decimal("0")
        assert info.net_gain == Decimal("1500")
        assert info.freistellungsauftrag_used == Decimal("1500")

    def test_above_freistellungsauftrag(self):
        info = PortfolioCalculator.calculate_german_tax(
            Decimal("5000"), Decimal("2000")
        )
        assert info.taxable_gain == Decimal("3000")
        assert info.abgeltungssteuer == Decimal("750.00")  # 25% of 3000
        assert info.solidaritaetszuschlag == Decimal("41.25")  # 5.5% of 750
        assert info.total_tax == Decimal("791.25")
        assert info.net_gain == Decimal("4208.75")

    def test_loss(self):
        info = PortfolioCalculator.calculate_german_tax(Decimal("-1000"))
        assert info.total_tax == Decimal("0")
        assert info.net_gain == Decimal("-1000")

    def test_zero(self):
        info = PortfolioCalculator.calculate_german_tax(Decimal("0"))
        assert info.total_tax == Decimal("0")
        assert info.net_gain == Decimal("0")
