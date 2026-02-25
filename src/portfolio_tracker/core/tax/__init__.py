"""German investment tax engine.

High-level entry point:
    from portfolio_tracker.core.tax import calculate_german_tax

Tax calculation pipeline for a realized gain:
  1. Teilfreistellung   (§ 20 InvStG)     — partial fund exemption
  2. Freistellungsauftrag (§ 20 Abs. 9 EStG) — annual tax-free allowance
  3. Abgeltungssteuer 25% + Soli 5.5%    (§ 32d EStG / § 4 SolZG)

Sub-modules (importable individually for testing or reuse):
    abgeltungssteuer    — flat tax + Solidaritätszuschlag
    freistellungsauftrag — annual tax-free allowance
    teilfreistellung    — partial exemption for fund type
    vorabpauschale      — annual prepayment on accumulating funds (§ 18 InvStG)
"""

from decimal import Decimal
from typing import Optional

from ..models import TaxInfo
from .abgeltungssteuer import (
    ABGELTUNGSSTEUER_RATE,
    SOLI_RATE,
    calculate_abgeltungssteuer,
    calculate_soli,
)
from .freistellungsauftrag import (
    DEFAULT_FSA_JOINT,
    DEFAULT_FSA_SINGLE,
    apply_freistellungsauftrag,
    get_freistellungsauftrag,
)
from .teilfreistellung import (
    MIXED_FUND_RATE,
    TFS_RATES,
    apply_teilfreistellung,
    weighted_portfolio_tfs,
)
from .vorabpauschale import (
    BASISERTRAG_FACTOR,
    BASISZINS,
    VorabpauschaleResult,
    calculate_vorabpauschale,
)

__all__ = [
    "calculate_german_tax",
    # abgeltungssteuer
    "ABGELTUNGSSTEUER_RATE",
    "SOLI_RATE",
    "calculate_abgeltungssteuer",
    "calculate_soli",
    # freistellungsauftrag
    "DEFAULT_FSA_JOINT",
    "DEFAULT_FSA_SINGLE",
    "apply_freistellungsauftrag",
    "get_freistellungsauftrag",
    # teilfreistellung
    "TFS_RATES",
    "MIXED_FUND_RATE",
    "apply_teilfreistellung",
    "weighted_portfolio_tfs",
    # vorabpauschale
    "BASISZINS",
    "BASISERTRAG_FACTOR",
    "VorabpauschaleResult",
    "calculate_vorabpauschale",
]


def calculate_german_tax(
    realized_gain: Decimal,
    freistellungsauftrag: Optional[Decimal] = None,
    teilfreistellung_rate: Decimal = Decimal("0"),
) -> TaxInfo:
    """Calculate German capital gains tax on a realized gain.

    Applies the full German tax pipeline in the correct legal order:
      1. Teilfreistellung reduces the taxable base by the fund's TFS rate.
      2. Freistellungsauftrag shelters remaining gains up to the annual limit.
      3. Abgeltungssteuer (25%) and Solidaritätszuschlag (5.5%) applied to
         whatever remains.

    Args:
        realized_gain: Total gain before tax (pre-Teilfreistellung).
            Use a negative value for a loss — no tax will be calculated.
        freistellungsauftrag: Annual tax-free allowance in EUR.
            Reads from config.json if not provided (pt setup run).
            Typical values: €1,000 (single) / €2,000 (joint filing).
        teilfreistellung_rate: TFS exemption rate for the fund type.
            0.30 — equity ETF (Aktienfonds, >51% equities)
            0.15 — mixed fund (Mischfonds, 25–51% equities)
            0.00 — bond ETF / direct stock (default)

    Returns:
        TaxInfo with all intermediate values:
            gross_gain, teilfreistellung_exempt, freistellungsauftrag_used,
            taxable_gain, abgeltungssteuer, solidaritaetszuschlag,
            total_tax, net_gain.

    References:
        § 20 InvStG  — Teilfreistellung
        § 20 Abs. 9 EStG — Freistellungsauftrag
        § 32d EStG   — Abgeltungssteuer
        § 4 SolZG    — Solidaritätszuschlag
    """
    if freistellungsauftrag is None:
        freistellungsauftrag = get_freistellungsauftrag()

    info = TaxInfo(gross_gain=realized_gain)

    if realized_gain <= 0:
        info.net_gain = realized_gain
        return info

    # Step 1: Teilfreistellung (§ 20 InvStG)
    info.teilfreistellung_exempt, taxable_after_tfs = apply_teilfreistellung(
        realized_gain, teilfreistellung_rate
    )

    # Step 2: Freistellungsauftrag (§ 20 Abs. 9 EStG)
    info.freistellungsauftrag_used, info.taxable_gain = apply_freistellungsauftrag(
        taxable_after_tfs, freistellungsauftrag
    )

    # Step 3: Abgeltungssteuer + Soli (§ 32d EStG / § 4 SolZG)
    if info.taxable_gain > 0:
        info.abgeltungssteuer = calculate_abgeltungssteuer(info.taxable_gain)
        info.solidaritaetszuschlag = calculate_soli(info.abgeltungssteuer)
        info.total_tax = info.abgeltungssteuer + info.solidaritaetszuschlag

    info.net_gain = realized_gain - info.total_tax
    return info
