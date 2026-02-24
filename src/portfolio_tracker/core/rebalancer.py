"""Rebalancing engine — target allocation strategy.

Supports two modes:
  - by_type:  targets are per asset_type (etf, bond, stock, crypto)
  - by_isin:  targets are per individual ISIN (for per-ETF rebalancing)

Mode is auto-detected: if any target's asset_type looks like an ISIN
(12 chars, 2 letters + 10 alphanumeric), it uses by_isin mode.
"""

from decimal import Decimal

from .calculator import PortfolioCalculator
from .models import (
    AssetType,
    Holding,
    RebalanceTrade,
    TargetAllocation,
    TransactionType,
)


def _is_isin(s: str) -> bool:
    """Check if a string looks like an ISIN (e.g. IE00BK5BQT80)."""
    return len(s) == 12 and s[:2].isalpha() and s[2:].isalnum()


class Rebalancer:
    def __init__(self, holdings: list[Holding], targets: list[TargetAllocation]):
        self.holdings = holdings
        self.targets = targets
        # Auto-detect mode
        self.by_isin = any(_is_isin(t.asset_type) for t in targets)

    def check_deviation(self) -> dict[str, dict]:
        """
        Returns deviation info per target key (asset_type or ISIN).
        """
        if self.by_isin:
            current_alloc = PortfolioCalculator.allocation_by_isin(self.holdings)
        else:
            current_alloc = PortfolioCalculator.allocation_by_type(self.holdings)

        target_map = {t.asset_type: t for t in self.targets}

        result = {}
        for key, target in target_map.items():
            current_pct = current_alloc.get(key, Decimal("0"))
            deviation = current_pct - target.target_percentage
            result[key] = {
                "current": current_pct,
                "target": target.target_percentage,
                "deviation": deviation,
                "threshold": target.rebalance_threshold,
                "needs_rebalance": abs(deviation) > target.rebalance_threshold,
            }

        # Assets in portfolio but not in targets
        for key, pct in current_alloc.items():
            if key not in result:
                result[key] = {
                    "current": pct,
                    "target": Decimal("0"),
                    "deviation": pct,
                    "threshold": Decimal("0"),
                    "needs_rebalance": True,
                }

        return result

    def suggest_trades(self) -> list[RebalanceTrade]:
        """Generate trade suggestions to bring portfolio back to target allocation."""
        deviations = self.check_deviation()
        portfolio_value = PortfolioCalculator.total_value(self.holdings)

        if portfolio_value == 0:
            return []

        trades: list[RebalanceTrade] = []

        for key, info in deviations.items():
            if not info["needs_rebalance"]:
                continue

            deviation = info["deviation"]
            value_to_adjust = abs(deviation) / 100 * portfolio_value

            # Find matching holdings
            if self.by_isin:
                matching = [
                    h for h in self.holdings
                    if h.isin == key and h.current_price and h.current_price > 0
                ]
            else:
                matching = [
                    h for h in self.holdings
                    if h.asset_type.value == key and h.current_price and h.current_price > 0
                ]

            if not matching:
                continue

            if deviation > 0:
                # Overweight — need to sell
                per_holding_value = value_to_adjust / len(matching)
                for h in matching:
                    shares_to_sell = (per_holding_value / h.current_price).quantize(
                        Decimal("0.0001")
                    )
                    shares_to_sell = min(shares_to_sell, h.shares)
                    if shares_to_sell > 0:
                        label = h.ticker or h.isin
                        trades.append(
                            RebalanceTrade(
                                action=TransactionType.SELL,
                                isin=h.isin,
                                asset_type=h.asset_type,
                                shares=shares_to_sell,
                                current_price=h.current_price,
                                reason=f"{label} overweight by {abs(deviation):.1f}%",
                                name=h.name,
                                ticker=h.ticker,
                            )
                        )
            else:
                # Underweight — need to buy
                per_holding_value = value_to_adjust / len(matching)
                for h in matching:
                    shares_to_buy = (per_holding_value / h.current_price).quantize(
                        Decimal("0.0001")
                    )
                    if shares_to_buy > 0:
                        label = h.ticker or h.isin
                        trades.append(
                            RebalanceTrade(
                                action=TransactionType.BUY,
                                isin=h.isin,
                                asset_type=h.asset_type,
                                shares=shares_to_buy,
                                current_price=h.current_price,
                                reason=f"{label} underweight by {abs(deviation):.1f}%",
                                name=h.name,
                                ticker=h.ticker,
                            )
                        )

        return trades
