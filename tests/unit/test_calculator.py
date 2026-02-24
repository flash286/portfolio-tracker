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


class TestTotalValueEdgeCases:
    def test_all_none_prices(self):
        """Returns 0 when all holdings have no price."""
        holdings = [
            _holding("US0378331005", "stock", 10, 1500),
            _holding("US5949181045", "etf", 5, 2000),
        ]
        assert PortfolioCalculator.total_value(holdings) == Decimal("0")


class TestAllocationEdgeCases:
    def test_some_missing_prices_excluded(self):
        """Holdings without prices are excluded from allocation calculation."""
        holdings = [
            _holding("US0378331005", "stock", 10, 1000, 100),  # value = 1000
            _holding("US5949181045", "etf", 5, 500),           # no price
        ]
        alloc = PortfolioCalculator.allocation_by_type(holdings)
        assert alloc.get("stock") == Decimal("100.00")
        assert "etf" not in alloc


class TestGermanTax:
    def test_within_freistellungsauftrag(self):
        info = PortfolioCalculator.calculate_german_tax(
            Decimal("1500"), Decimal("2000")
        )
        assert info.taxable_gain == Decimal("0")
        assert info.total_tax == Decimal("0")
        assert info.net_gain == Decimal("1500")
        assert info.freistellungsauftrag_used == Decimal("1500")
        assert info.teilfreistellung_exempt == Decimal("0")

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

    def test_custom_freistellungsauftrag_single_person(self):
        """Single person has €1,000 FSA instead of €2,000."""
        info = PortfolioCalculator.calculate_german_tax(
            Decimal("1500"), Decimal("1000")
        )
        assert info.freistellungsauftrag_used == Decimal("1000")
        assert info.taxable_gain == Decimal("500")
        assert info.abgeltungssteuer == Decimal("125.00")  # 25% of 500
        assert info.solidaritaetszuschlag == Decimal("6.88")  # 5.5% of 125, rounded

    def test_large_gain_decimal_precision(self):
        """Large gains are computed with correct Decimal precision."""
        info = PortfolioCalculator.calculate_german_tax(Decimal("100000"))
        # taxable = 100000 - 2000 = 98000
        # abgelt  = 98000 * 0.25 = 24500.00
        # soli    = 24500 * 0.055 = 1347.50
        assert info.taxable_gain == Decimal("98000")
        assert info.abgeltungssteuer == Decimal("24500.00")
        assert info.solidaritaetszuschlag == Decimal("1347.50")
        assert info.total_tax == Decimal("25847.50")


class TestGermanTaxTeilfreistellung:
    def test_equity_etf_30pct_exempt(self):
        """30% Teilfreistellung reduces taxable base for equity ETFs."""
        info = PortfolioCalculator.calculate_german_tax(
            Decimal("1000"),
            freistellungsauftrag=Decimal("0"),  # ignore FSA for clarity
            teilfreistellung_rate=Decimal("0.3"),
        )
        # exempt = 1000 * 0.3 = 300
        # taxable_after_tfs = 700
        # abgelt = 700 * 0.25 = 175
        assert info.teilfreistellung_exempt == Decimal("300.00")
        assert info.taxable_gain == Decimal("700")
        assert info.abgeltungssteuer == Decimal("175.00")

    def test_tfs_applied_before_freistellungsauftrag(self):
        """TFS reduces base first, then FSA applies to the reduced amount."""
        info = PortfolioCalculator.calculate_german_tax(
            Decimal("3000"),
            freistellungsauftrag=Decimal("2000"),
            teilfreistellung_rate=Decimal("0.3"),
        )
        # exempt = 3000 * 0.3 = 900
        # taxable_after_tfs = 2100
        # fsa used = min(2100, 2000) = 2000
        # taxable_gain = 2100 - 2000 = 100
        assert info.teilfreistellung_exempt == Decimal("900.00")
        assert info.freistellungsauftrag_used == Decimal("2000")
        assert info.taxable_gain == Decimal("100")

    def test_no_tfs_by_default(self):
        """Default TFS rate is 0, no exemption applied."""
        info = PortfolioCalculator.calculate_german_tax(Decimal("1000"))
        assert info.teilfreistellung_exempt == Decimal("0")

    def test_tfs_zero_rate_no_effect(self):
        """Explicit TFS rate of 0 has no effect (bond ETF / stock)."""
        info_no_tfs = PortfolioCalculator.calculate_german_tax(Decimal("500"))
        info_zero_tfs = PortfolioCalculator.calculate_german_tax(
            Decimal("500"), teilfreistellung_rate=Decimal("0")
        )
        assert info_no_tfs.total_tax == info_zero_tfs.total_tax
        assert info_zero_tfs.teilfreistellung_exempt == Decimal("0")
