"""Tests for core.tax.teilfreistellung.

Teilfreistellung rates per § 20 InvStG:
  Equity ETF (Aktienfonds):  30%
  Mixed fund (Mischfonds):   15%
  Bond ETF / stock:           0%
"""

from decimal import Decimal

import pytest

from portfolio_tracker.core.tax.teilfreistellung import (
    MIXED_FUND_RATE,
    TFS_RATES,
    apply_teilfreistellung,
    weighted_portfolio_tfs,
)
from portfolio_tracker.core.models import AssetType, Holding


def _holding(isin, asset_type, shares, cost_basis, current_price=None, tfs_rate="0"):
    return Holding(
        portfolio_id=1,
        isin=isin,
        asset_type=AssetType(asset_type),
        shares=Decimal(str(shares)),
        cost_basis=Decimal(str(cost_basis)),
        current_price=Decimal(str(current_price)) if current_price else None,
        teilfreistellung_rate=Decimal(tfs_rate),
    )


class TestTFSRates:
    def test_equity_etf_rate(self):
        assert TFS_RATES["etf"] == Decimal("0.3")

    def test_stock_rate(self):
        assert TFS_RATES["stock"] == Decimal("0")

    def test_bond_rate(self):
        assert TFS_RATES["bond"] == Decimal("0")

    def test_crypto_rate(self):
        assert TFS_RATES["crypto"] == Decimal("0")

    def test_mixed_fund_rate(self):
        assert MIXED_FUND_RATE == Decimal("0.15")


class TestApplyTeilfreistellung:
    def test_equity_etf_30pct(self):
        # gain=1000, rate=0.3 → exempt=300, taxable=700
        exempt, taxable = apply_teilfreistellung(Decimal("1000"), Decimal("0.3"))
        assert exempt == Decimal("300.00")
        assert taxable == Decimal("700.00")

    def test_mixed_fund_15pct(self):
        # gain=1000, rate=0.15 → exempt=150, taxable=850
        exempt, taxable = apply_teilfreistellung(Decimal("1000"), Decimal("0.15"))
        assert exempt == Decimal("150.00")
        assert taxable == Decimal("850.00")

    def test_bond_etf_zero(self):
        # gain=1000, rate=0.0 → exempt=0, taxable=1000
        exempt, taxable = apply_teilfreistellung(Decimal("1000"), Decimal("0"))
        assert exempt == Decimal("0.00")
        assert taxable == Decimal("1000")

    def test_exempt_plus_taxable_equals_gain(self):
        gain = Decimal("12345.67")
        exempt, taxable = apply_teilfreistellung(gain, Decimal("0.3"))
        assert exempt + taxable == gain

    def test_zero_gain(self):
        exempt, taxable = apply_teilfreistellung(Decimal("0"), Decimal("0.3"))
        assert exempt == Decimal("0.00")
        assert taxable == Decimal("0.00")

    def test_rounding(self):
        # gain=333.33, rate=0.3 → exempt=99.999 → 100.00
        exempt, taxable = apply_teilfreistellung(Decimal("333.33"), Decimal("0.3"))
        assert exempt == Decimal("100.00")
        assert taxable == Decimal("233.33")


class TestWeightedPortfolioTFS:
    def test_single_equity_etf(self):
        holdings = [_holding("IE00BK5BQT80", "etf", 10, 1000, 100, "0.3")]
        # 100% in equity ETF → weighted TFS = 0.30
        assert weighted_portfolio_tfs(holdings) == Decimal("0.3000")

    def test_mixed_portfolio(self):
        # Equity ETF: value=700, TFS=0.3
        # Bond ETF:   value=300, TFS=0.0
        # weighted = (700×0.3 + 300×0.0) / 1000 = 210/1000 = 0.21
        holdings = [
            _holding("ISIN1", "etf", 7, 700, 100, "0.3"),
            _holding("ISIN2", "bond", 3, 300, 100, "0.0"),
        ]
        assert weighted_portfolio_tfs(holdings) == Decimal("0.2100")

    def test_no_priced_holdings(self):
        holdings = [_holding("ISIN1", "etf", 10, 1000, tfs_rate="0.3")]
        assert weighted_portfolio_tfs(holdings) == Decimal("0")

    def test_empty_list(self):
        assert weighted_portfolio_tfs([]) == Decimal("0")
