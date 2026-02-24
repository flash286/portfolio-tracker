"""Tests for Rebalancer."""

from decimal import Decimal

import pytest

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
