"""Abgeltungssteuer (flat capital gains tax) and Solidaritätszuschlag.

§ 32d EStG: 25% flat withholding tax on all capital income (Kapitalerträge),
including dividends, realized gains, and Vorabpauschale.

§ 4 SolZG: Solidaritätszuschlag = 5.5% of Abgeltungssteuer.
Note: Soli was abolished for most income taxpayers in 2021, but continues
to apply to Abgeltungssteuer without a de-minimis threshold.

Kirchensteuer (church tax) is not handled here — it is optional and
configured via config.json (typically 8% in Bavaria/BW, 9% elsewhere).
"""

from decimal import Decimal

#: Flat capital gains withholding tax rate — § 32d Abs. 1 EStG
ABGELTUNGSSTEUER_RATE = Decimal("0.25")

#: Solidarity surcharge on Abgeltungssteuer — § 4 Abs. 1 SolZG
SOLI_RATE = Decimal("0.055")


def calculate_abgeltungssteuer(taxable_gain: Decimal) -> Decimal:
    """Calculate Abgeltungssteuer (25% of taxable gain).

    § 32d EStG — flat withholding tax applied after Teilfreistellung
    and Freistellungsauftrag have reduced the taxable base.

    Args:
        taxable_gain: Gain after TFS and FSA deductions, must be ≥ 0.

    Returns:
        Abgeltungssteuer rounded to 2 decimal places.
    """
    return (taxable_gain * ABGELTUNGSSTEUER_RATE).quantize(Decimal("0.01"))


def calculate_soli(abgeltungssteuer: Decimal) -> Decimal:
    """Calculate Solidaritätszuschlag (5.5% of Abgeltungssteuer).

    § 4 SolZG — applied to the tax amount, not the underlying gain.

    Args:
        abgeltungssteuer: Abgeltungssteuer amount (output of calculate_abgeltungssteuer).

    Returns:
        Solidaritätszuschlag rounded to 2 decimal places.
    """
    return (abgeltungssteuer * SOLI_RATE).quantize(Decimal("0.01"))
