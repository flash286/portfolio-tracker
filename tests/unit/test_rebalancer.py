"""Tests for Rebalancer."""

from decimal import Decimal

from portfolio_tracker.core.models import (
    AssetType,
    Holding,
    TargetAllocation,
    TransactionType,
)
from portfolio_tracker.core.rebalancer import Rebalancer


def _holding(isin, asset_type, shares, cost_basis, current_price):
    return Holding(
        portfolio_id=1,
        isin=isin,
        asset_type=AssetType(asset_type),
        shares=Decimal(str(shares)),
        cost_basis=Decimal(str(cost_basis)),
        current_price=Decimal(str(current_price)),
    )


def _target(asset_type, pct, threshold=5):
    return TargetAllocation(
        portfolio_id=1,
        asset_type=asset_type,
        target_percentage=Decimal(str(pct)),
        rebalance_threshold=Decimal(str(threshold)),
    )


class TestModeDetection:
    def test_by_isin_mode_when_isin_target(self):
        """Target with ISIN-format string triggers by_isin=True."""
        targets = [_target("IE00B4L5Y983", 100)]
        r = Rebalancer([], targets)
        assert r.by_isin is True

    def test_by_type_mode_when_asset_type_target(self):
        """Target with asset type name triggers by_isin=False."""
        targets = [_target("etf", 100)]
        r = Rebalancer([], targets)
        assert r.by_isin is False


class TestCheckDeviation:
    def test_within_threshold(self):
        holdings = [
            _holding("US0378331005", "stock", 10, 1000, 100),  # 1000 = ~50%
            _holding("CRYPTO-BTC", "crypto", 1, 500, 1000),    # 1000 = ~50%
        ]
        targets = [_target("stock", 50), _target("crypto", 50)]
        r = Rebalancer(holdings, targets)
        devs = r.check_deviation()
        assert not devs["stock"]["needs_rebalance"]
        assert not devs["crypto"]["needs_rebalance"]

    def test_deviation_detected(self):
        holdings = [
            _holding("US0378331005", "stock", 10, 1000, 150),  # 1500 = 75%
            _holding("CRYPTO-BTC", "crypto", 1, 500, 500),     # 500 = 25%
        ]
        targets = [_target("stock", 50), _target("crypto", 50)]
        r = Rebalancer(holdings, targets)
        devs = r.check_deviation()
        assert devs["stock"]["needs_rebalance"]
        assert devs["crypto"]["needs_rebalance"]


class TestSuggestTrades:
    def test_suggests_sell_overweight_buy_underweight(self):
        holdings = [
            _holding("US0378331005", "stock", 10, 1000, 150),  # 1500 = 75%
            _holding("CRYPTO-BTC", "crypto", 1, 500, 500),     # 500 = 25%
        ]
        targets = [_target("stock", 50), _target("crypto", 50)]
        r = Rebalancer(holdings, targets)
        trades = r.suggest_trades()

        assert len(trades) == 2
        sell = next(t for t in trades if t.action == TransactionType.SELL)
        buy = next(t for t in trades if t.action == TransactionType.BUY)

        assert sell.isin == "US0378331005"
        assert buy.isin == "CRYPTO-BTC"
        assert sell.shares > Decimal("0")
        assert buy.shares > Decimal("0")

    def test_no_trades_when_balanced(self):
        holdings = [
            _holding("US0378331005", "stock", 10, 1000, 100),
            _holding("CRYPTO-BTC", "crypto", 1, 500, 1000),
        ]
        targets = [_target("stock", 50), _target("crypto", 50)]
        r = Rebalancer(holdings, targets)
        trades = r.suggest_trades()
        assert len(trades) == 0

    def test_empty_portfolio(self):
        r = Rebalancer([], [_target("stock", 100)])
        trades = r.suggest_trades()
        assert len(trades) == 0

    def test_sell_clamped_to_available_shares(self):
        """Suggested sell never exceeds shares actually held."""
        holdings = [
            _holding("US0378331005", "stock", 1, 100, 200),   # only 1 share held
            _holding("CRYPTO-BTC", "crypto", 100, 500, 1),    # underweight
        ]
        targets = [_target("stock", 50), _target("crypto", 50)]
        r = Rebalancer(holdings, targets)
        trades = r.suggest_trades()
        sell = next((t for t in trades if t.action == TransactionType.SELL), None)
        if sell:
            assert sell.shares <= Decimal("1")

    def test_suggest_trades_by_isin(self):
        """Rebalancing by ISIN targets works for specific holdings."""
        holdings = [
            _holding("IE00B4L5Y983", "etf", 10, 1000, 100),   # value=1000, 66.7%
            _holding("IE00BK5BQT80", "etf", 5, 500, 100),     # value=500, 33.3%
        ]
        targets = [
            _target("IE00B4L5Y983", 50),
            _target("IE00BK5BQT80", 50),
        ]
        r = Rebalancer(holdings, targets)
        assert r.by_isin is True
        trades = r.suggest_trades()
        actions = {t.isin: t.action for t in trades}
        assert actions.get("IE00B4L5Y983") == TransactionType.SELL
        assert actions.get("IE00BK5BQT80") == TransactionType.BUY

    def test_untracked_asset_flagged_for_rebalance(self):
        """Asset in portfolio with no matching target is flagged needs_rebalance=True."""
        holdings = [_holding("US0378331005", "stock", 10, 1000, 100)]
        targets = [_target("etf", 100)]  # etf target, but portfolio has stock
        r = Rebalancer(holdings, targets)
        devs = r.check_deviation()
        assert "stock" in devs
        assert devs["stock"]["needs_rebalance"] is True
