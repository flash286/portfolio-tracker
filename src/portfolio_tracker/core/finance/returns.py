"""Portfolio return and allocation calculations.

All functions are pure — they accept Holding objects and return Decimal
values. No database access, no I/O, no side effects.
"""

from decimal import Decimal


def total_value(holdings: list) -> Decimal:
    """Sum the current market value of all priced holdings.

    Holdings without a current price (current_price is None) contribute
    zero to the total — they are simply excluded.

    Args:
        holdings: List of Holding objects.

    Returns:
        Total market value in EUR, or Decimal("0") if no holdings are priced.
    """
    return sum(
        (h.current_value for h in holdings if h.current_price is not None),
        Decimal("0"),
    )


def total_cost_basis(holdings: list) -> Decimal:
    """Sum the cost basis (total purchase cost) across all holdings.

    Args:
        holdings: List of Holding objects.

    Returns:
        Total cost basis in EUR.
    """
    return sum((h.cost_basis for h in holdings), Decimal("0"))


def total_unrealized_pnl(holdings: list) -> Decimal:
    """Calculate total unrealized P&L: market value minus cost basis.

    Positive result = unrealized profit.
    Negative result = unrealized loss.

    Note: Holdings without prices contribute 0 to market value but their
    full cost basis is included, which understates P&L until prices are
    fetched.

    Args:
        holdings: List of Holding objects.

    Returns:
        Unrealized P&L in EUR.
    """
    return total_value(holdings) - total_cost_basis(holdings)


def allocation_by_type(holdings: list) -> dict[str, Decimal]:
    """Calculate allocation percentages grouped by asset type.

    Holdings without a current price are excluded from the calculation.
    The percentages sum to approximately 100% (subject to rounding).

    Args:
        holdings: List of Holding objects with asset_type and current_price.

    Returns:
        Dict mapping asset type string to percentage (e.g. {"etf": Decimal("75.00")}).
        Empty dict if no holdings have prices.
    """
    port_value = total_value(holdings)
    if port_value == 0:
        return {}
    result: dict[str, Decimal] = {}
    for h in holdings:
        if h.current_price is None:
            continue
        pct = (h.current_value / port_value * 100).quantize(Decimal("0.01"))
        key = h.asset_type.value
        result[key] = result.get(key, Decimal("0")) + pct
    return result


def allocation_by_isin(holdings: list) -> dict[str, Decimal]:
    """Calculate allocation percentages per individual holding (by ISIN).

    Holdings without a current price are excluded from the calculation.
    The percentages sum to approximately 100% (subject to rounding).

    Args:
        holdings: List of Holding objects with isin and current_price.

    Returns:
        Dict mapping ISIN string to percentage (e.g. {"IE00BK5BQT80": Decimal("70.00")}).
        Empty dict if no holdings have prices.
    """
    port_value = total_value(holdings)
    if port_value == 0:
        return {}
    result: dict[str, Decimal] = {}
    for h in holdings:
        if h.current_price is None:
            continue
        pct = (h.current_value / port_value * 100).quantize(Decimal("0.01"))
        result[h.isin] = pct
    return result
