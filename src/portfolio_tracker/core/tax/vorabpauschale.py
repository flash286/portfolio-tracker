"""Vorabpauschale — annual prepayment tax on accumulating investment funds.

§ 18 InvStG (Investmentsteuergesetz): accumulating funds (Thesaurierer) that
do not distribute income still owe an annual deemed income (Vorabpauschale),
calculated as a fraction of the fund's starting value for the year.

Formula (§ 18 Abs. 1–4 InvStG):
  Basisertrag    = Kurs_01.01 × Basiszins × 0.7
  Vorabpauschale = min(Basisertrag, max(Fondszuwachs, 0)) × Anteile
  Steuerpflichtig = Vorabpauschale × (1 − Teilfreistellung)

Where:
  Basiszins    — annual base rate published by Bundesbank / BMF
                 (§ 18 Abs. 4 InvStG, typically in January each year)
  0.7          — statutory factor (§ 18 Abs. 4 Satz 1 InvStG)
  Fondszuwachs — actual fund gain for the year (price_dec31 - price_jan1)
  Anteile      — shares held on January 1 of the tax year

If Fondszuwachs ≤ 0, Vorabpauschale is zero (fund didn't grow).
If Basiszins = 0 (as in 2020–2022), no Vorabpauschale is owed.

Distributing funds (Ausschüttende) may have their Vorabpauschale reduced
by actual distributions already taxed during the year. This implementation
flags distributing funds but does not subtract dividends automatically —
the broker handles the final settlement.
"""

from dataclasses import dataclass
from decimal import Decimal

#: Basiszins published by Bundesbank / BMF each January (§ 18 Abs. 4 InvStG).
#: A value of 0 means no Vorabpauschale is owed for that year.
#: Update this dict each January with the newly published rate.
BASISZINS: dict[int, Decimal] = {
    2019: Decimal("0.0052"),
    2020: Decimal("0"),       # negative base rate → no VP owed
    2021: Decimal("0"),       # negative base rate → no VP owed
    2022: Decimal("0"),       # negative base rate → no VP owed
    2023: Decimal("0.0255"),  # BMF publication 2023-01-10
    2024: Decimal("0.0229"),  # BMF publication 2024-01-05
    2025: Decimal("0.0253"),  # BMF publication 2025-01-07
}

#: Statutory factor applied to Basisertrag — § 18 Abs. 4 Satz 1 InvStG
BASISERTRAG_FACTOR = Decimal("0.7")


@dataclass
class VorabpauschaleResult:
    """Per-holding Vorabpauschale calculation result for one calendar year."""

    ticker: str
    isin: str
    year: int
    shares_jan1: Decimal
    price_jan1: Decimal
    price_dec31: Decimal
    basisertrag_per_share: Decimal    #: price_jan1 × basiszins × 0.7
    fondszuwachs_per_share: Decimal   #: max(price_dec31 - price_jan1, 0)
    vorabpauschale: Decimal           #: min(basisertrag, fondszuwachs) × shares
    tfs_rate: Decimal
    tfs_exempt: Decimal               #: vorabpauschale × tfs_rate
    taxable_vp: Decimal               #: vorabpauschale - tfs_exempt
    is_distributing: bool = False     #: True if fund paid dividends this year


def calculate_vorabpauschale(
    ticker: str,
    isin: str,
    year: int,
    shares_jan1: Decimal,
    price_jan1: Decimal,
    price_dec31: Decimal,
    teilfreistellung_rate: Decimal,
    is_distributing: bool = False,
) -> VorabpauschaleResult:
    """Calculate Vorabpauschale for one holding for one calendar year.

    All monetary values must be in EUR. Returns zero Vorabpauschale when
    the fund declined or the Basiszins for the year is 0.

    Args:
        ticker: Exchange ticker symbol (for display and price lookups).
        isin: ISIN of the fund.
        year: Calendar year for which VP is being calculated.
        shares_jan1: Shares held on January 1 of the year.
        price_jan1: Fund NAV/price on January 1 (or first trading day).
        price_dec31: Fund NAV/price on December 31 (or last trading day).
        teilfreistellung_rate: TFS rate for the fund (0.3 equity, 0 bond).
        is_distributing: True if the fund paid distributions during the year.
            Distributing funds' VP may be reduced by actual payouts; this
            flag is informational — the broker applies the final reduction.

    Returns:
        VorabpauschaleResult with all intermediate values.

    References:
        § 18 InvStG — Vorabpauschale
        § 20 InvStG — Teilfreistellung
    """
    basiszins = BASISZINS.get(year, Decimal("0"))
    basisertrag_per_share = (
        price_jan1 * basiszins * BASISERTRAG_FACTOR
    ).quantize(Decimal("0.0001"))
    fondszuwachs_per_share = max(price_dec31 - price_jan1, Decimal("0"))
    vp_per_share = min(basisertrag_per_share, fondszuwachs_per_share)
    vorabpauschale = (vp_per_share * shares_jan1).quantize(Decimal("0.01"))
    tfs_exempt = (vorabpauschale * teilfreistellung_rate).quantize(Decimal("0.01"))
    taxable_vp = vorabpauschale - tfs_exempt

    return VorabpauschaleResult(
        ticker=ticker,
        isin=isin,
        year=year,
        shares_jan1=shares_jan1,
        price_jan1=price_jan1,
        price_dec31=price_dec31,
        basisertrag_per_share=basisertrag_per_share,
        fondszuwachs_per_share=fondszuwachs_per_share,
        vorabpauschale=vorabpauschale,
        tfs_rate=teilfreistellung_rate,
        tfs_exempt=tfs_exempt,
        taxable_vp=taxable_vp,
        is_distributing=is_distributing,
    )
