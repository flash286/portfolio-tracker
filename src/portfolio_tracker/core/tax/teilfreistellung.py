"""Teilfreistellung (partial tax exemption) for investment funds.

§ 20 InvStG (Investmentsteuergesetz): a portion of gains from investment
funds is exempt from tax, reducing the taxable base before Abgeltungssteuer.

Rates (§ 20 Abs. 1–3 InvStG):
  - Aktienfonds  (equity funds, >51% equities):    30%
  - Mischfonds   (mixed funds,  25–51% equities):   15%
  - Rentenfonds  (bond funds,   <25% equities):       0%

Teilfreistellung applies to capital gains, dividends, and Vorabpauschale.
It is applied *before* the Freistellungsauftrag is deducted.
"""

from decimal import Decimal

#: TFS rates by asset type — § 20 Abs. 1–3 InvStG
TFS_RATES: dict[str, Decimal] = {
    "etf":    Decimal("0.3"),   # Aktienfonds (equity ETF, >51% equities)
    "stock":  Decimal("0"),     # Direct equities — no TFS applies
    "bond":   Decimal("0"),     # Rentenfonds (<25% equities) — no TFS
    "crypto": Decimal("0"),     # Crypto — no TFS
}

#: Mixed fund (Mischfonds) rate — § 20 Abs. 2 InvStG
MIXED_FUND_RATE = Decimal("0.15")


def apply_teilfreistellung(
    gain: Decimal,
    rate: Decimal,
) -> tuple[Decimal, Decimal]:
    """Apply Teilfreistellung to a gain.

    Args:
        gain: Total gain before exemption.
        rate: TFS rate (e.g. Decimal("0.3") for equity ETFs).

    Returns:
        Tuple of (exempt_amount, taxable_after_tfs).

    Examples:
        Equity ETF (30% TFS):  gain=1000, rate=0.3 → (300, 700)
        Bond ETF   (0% TFS):   gain=1000, rate=0.0 → (0, 1000)
        Mixed fund (15% TFS):  gain=1000, rate=0.15 → (150, 850)
    """
    exempt = (gain * rate).quantize(Decimal("0.01"))
    return exempt, gain - exempt


def weighted_portfolio_tfs(holdings: list) -> Decimal:
    """Calculate the value-weighted average TFS rate across priced holdings.

    Used for hypothetical portfolio-wide tax estimates (e.g. "if you sold
    everything today"). Holdings without a current price are excluded from
    both numerator and denominator.

    Args:
        holdings: List of Holding objects with current_price and
                  teilfreistellung_rate attributes.

    Returns:
        Weighted average TFS rate, or Decimal("0") if no priced holdings.
    """
    total_value = sum(
        (h.current_value for h in holdings if h.current_price is not None),
        Decimal("0"),
    )
    if total_value == 0:
        return Decimal("0")
    weighted = sum(
        h.current_value * h.teilfreistellung_rate
        for h in holdings
        if h.current_price is not None
    )
    return (weighted / total_value).quantize(Decimal("0.0001"))
