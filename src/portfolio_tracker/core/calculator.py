"""Portfolio statistics calculator."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from .models import AssetType, Holding, TaxInfo

# Basiszins published by BMF each January (§ 18 Abs. 4 InvStG)
# Negative years → 0 (no Vorabpauschale due)
BASISZINS: dict[int, Decimal] = {
    2021: Decimal("0"),
    2022: Decimal("0"),
    2023: Decimal("0.0255"),
    2024: Decimal("0.0229"),
    2025: Decimal("0.0253"),
}


@dataclass
class VorabpauschaleResult:
    """Per-holding Vorabpauschale calculation result."""
    ticker: str
    isin: str
    year: int
    shares_jan1: Decimal
    price_jan1: Decimal
    price_dec31: Decimal
    basisertrag_per_share: Decimal    # price_jan1 × basiszins × 0.7
    fondszuwachs_per_share: Decimal   # price_dec31 - price_jan1 (min 0)
    vorabpauschale: Decimal           # min(basisertrag, fondszuwachs) × shares
    tfs_rate: Decimal
    tfs_exempt: Decimal               # vorabpauschale × tfs_rate
    taxable_vp: Decimal               # vorabpauschale - tfs_exempt
    is_distributing: bool = False     # if True, actual distributions may reduce VP


class PortfolioCalculator:
    # German tax constants
    ABGELTUNGSSTEUER_RATE = Decimal("0.25")
    SOLI_RATE = Decimal("0.055")  # 5.5% of Abgeltungssteuer
    DEFAULT_FREISTELLUNGSAUFTRAG = Decimal("2000")  # Married couple (Zusammenveranlagung)

    @staticmethod
    def total_value(holdings: list[Holding]) -> Decimal:
        return sum(
            (h.current_value for h in holdings if h.current_price is not None),
            Decimal("0"),
        )

    @staticmethod
    def total_cost_basis(holdings: list[Holding]) -> Decimal:
        return sum((h.cost_basis for h in holdings), Decimal("0"))

    @staticmethod
    def total_unrealized_pnl(holdings: list[Holding]) -> Decimal:
        value = PortfolioCalculator.total_value(holdings)
        cost = PortfolioCalculator.total_cost_basis(holdings)
        return value - cost

    @staticmethod
    def allocation_by_type(holdings: list[Holding]) -> dict[str, Decimal]:
        """Returns allocation % grouped by asset_type."""
        total = PortfolioCalculator.total_value(holdings)
        if total == 0:
            return {}
        result: dict[str, Decimal] = {}
        for h in holdings:
            if h.current_price is None:
                continue
            pct = (h.current_value / total * 100).quantize(Decimal("0.01"))
            key = h.asset_type.value
            result[key] = result.get(key, Decimal("0")) + pct
        return result

    @staticmethod
    def allocation_by_isin(holdings: list[Holding]) -> dict[str, Decimal]:
        """Returns allocation % per individual ISIN."""
        total = PortfolioCalculator.total_value(holdings)
        if total == 0:
            return {}
        result: dict[str, Decimal] = {}
        for h in holdings:
            if h.current_price is None:
                continue
            pct = (h.current_value / total * 100).quantize(Decimal("0.01"))
            result[h.isin] = pct
        return result

    @staticmethod
    def calculate_german_tax(
        realized_gain: Decimal,
        freistellungsauftrag: Decimal = DEFAULT_FREISTELLUNGSAUFTRAG,
        teilfreistellung_rate: Decimal = Decimal("0"),
    ) -> TaxInfo:
        """
        Calculate German capital gains tax (Abgeltungssteuer).
        - 25% flat tax on gains
        - 5.5% Solidaritätszuschlag on the tax
        - Freistellungsauftrag: €1,000 (single) / €2,000 (married) tax-free
        - Teilfreistellung: 30% exemption for equity ETFs (§ 20 InvStG)
        - No Kirchensteuer (user not a church member)
        """
        info = TaxInfo(gross_gain=realized_gain)

        if realized_gain <= 0:
            info.net_gain = realized_gain
            return info

        # Apply Teilfreistellung first (reduces taxable base)
        info.teilfreistellung_exempt = (
            realized_gain * teilfreistellung_rate
        ).quantize(Decimal("0.01"))
        taxable_after_tfs = realized_gain - info.teilfreistellung_exempt

        # Apply Freistellungsauftrag to TFS-reduced base
        info.freistellungsauftrag_used = min(taxable_after_tfs, freistellungsauftrag)
        info.taxable_gain = max(taxable_after_tfs - freistellungsauftrag, Decimal("0"))

        if info.taxable_gain > 0:
            info.abgeltungssteuer = (
                info.taxable_gain * PortfolioCalculator.ABGELTUNGSSTEUER_RATE
            ).quantize(Decimal("0.01"))
            info.solidaritaetszuschlag = (
                info.abgeltungssteuer * PortfolioCalculator.SOLI_RATE
            ).quantize(Decimal("0.01"))
            info.total_tax = info.abgeltungssteuer + info.solidaritaetszuschlag

        info.net_gain = realized_gain - info.total_tax
        return info

    @staticmethod
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
        """
        Calculate Vorabpauschale for one holding for one year.

        Formula (§ 18 InvStG):
          Basisertrag = Kurs_01.01 × Basiszins × 0.7
          Vorabpauschale = min(Basisertrag, max(Fondszuwachs, 0)) × Anteile
          Steuerpflichtig = Vorabpauschale × (1 − Teilfreistellung)
        """
        basiszins = BASISZINS.get(year, Decimal("0"))
        basisertrag_per_share = (price_jan1 * basiszins * Decimal("0.7")).quantize(Decimal("0.0001"))
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
