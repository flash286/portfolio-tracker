"""Freistellungsauftrag (tax-free savings allowance) for capital income.

§ 20 Abs. 9 EStG: German residents may receive capital income tax-free
up to an annual limit:
  - €1,000 per year — single filers (Einzelveranlagung)
  - €2,000 per year — jointly assessed couples (Zusammenveranlagung)

The FSA is applied *after* Teilfreistellung, reducing the taxable base
before Abgeltungssteuer is calculated.

Unused FSA cannot be carried over to subsequent years. Multiple banks
share the same annual FSA — it is the taxpayer's responsibility to
distribute it across brokers via a Freistellungsauftrag order.
"""

from decimal import Decimal

#: FSA for jointly assessed couples — § 20 Abs. 9 Satz 1 EStG
DEFAULT_FSA_JOINT = Decimal("2000")

#: FSA for single filers — § 20 Abs. 9 Satz 1 EStG
DEFAULT_FSA_SINGLE = Decimal("1000")


def get_freistellungsauftrag() -> Decimal:
    """Read the configured Freistellungsauftrag from config.json.

    Falls back to €2,000 (joint filing) if the config file is missing
    or unreadable. Configure with: pt setup run

    Returns:
        FSA amount as Decimal.
    """
    try:
        from ..config import get_config
        return get_config().freistellungsauftrag
    except Exception:
        return DEFAULT_FSA_JOINT


def apply_freistellungsauftrag(
    taxable_gain: Decimal,
    available_fsa: Decimal,
) -> tuple[Decimal, Decimal]:
    """Apply the Freistellungsauftrag to a taxable gain.

    Args:
        taxable_gain: Gain after Teilfreistellung, before FSA.
        available_fsa: Remaining FSA allowance for the year.

    Returns:
        Tuple of (fsa_used, taxable_after_fsa).

    Examples:
        taxable=700,  fsa=1000 → (700, 0)    — FSA covers all, no tax
        taxable=1500, fsa=1000 → (1000, 500) — partial cover, tax on 500
        taxable=0,    fsa=1000 → (0, 0)      — nothing to shelter
    """
    used = min(taxable_gain, available_fsa)
    remaining = max(taxable_gain - available_fsa, Decimal("0"))
    return used, remaining
