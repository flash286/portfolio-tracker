"""Tests for core.tax.vorabpauschale.

Reference values are computed from the § 18 InvStG formula:
  Basisertrag/Anteil = Kurs_01.01 × Basiszins × 0.7
  Vorabpauschale     = min(Basisertrag, Fondszuwachs) × Anteile
  Steuerpflichtig    = Vorabpauschale × (1 − TFS)
"""

from decimal import Decimal

import pytest

from portfolio_tracker.core.tax.vorabpauschale import (
    BASISZINS,
    BASISERTRAG_FACTOR,
    VorabpauschaleResult,
    calculate_vorabpauschale,
)


class TestConstants:
    def test_basisertrag_factor(self):
        assert BASISERTRAG_FACTOR == Decimal("0.7")

    def test_basiszins_2024(self):
        assert BASISZINS[2024] == Decimal("0.0229")

    def test_basiszins_2023(self):
        assert BASISZINS[2023] == Decimal("0.0255")

    def test_basiszins_zero_years(self):
        for year in (2020, 2021, 2022):
            assert BASISZINS[year] == Decimal("0"), f"Expected 0 for {year}"

    def test_basiszins_missing_year_defaults_to_zero(self):
        # Unknown future year → treated as 0 (no VP owed)
        assert BASISZINS.get(2099, Decimal("0")) == Decimal("0")


class TestCalculateVorabpauschale:
    """Reference case: 10 shares, price Jan1=€100, Dec31=€110, year=2024 (2.29%)."""

    def _result_2024(self, **overrides):
        defaults = dict(
            ticker="VWCE",
            isin="IE00BK5BQT80",
            year=2024,
            shares_jan1=Decimal("10"),
            price_jan1=Decimal("100"),
            price_dec31=Decimal("110"),
            teilfreistellung_rate=Decimal("0.3"),
        )
        defaults.update(overrides)
        return calculate_vorabpauschale(**defaults)

    def test_basisertrag_per_share(self):
        # 100 × 0.0229 × 0.7 = 1.6030
        r = self._result_2024()
        assert r.basisertrag_per_share == Decimal("1.6030")

    def test_fondszuwachs_per_share(self):
        # 110 - 100 = 10
        r = self._result_2024()
        assert r.fondszuwachs_per_share == Decimal("10")

    def test_vorabpauschale_capped_by_basisertrag(self):
        # min(1.6030, 10) × 10 = 16.03
        r = self._result_2024()
        assert r.vorabpauschale == Decimal("16.03")

    def test_tfs_exempt(self):
        # 16.03 × 0.3 = 4.809 → 4.81
        r = self._result_2024()
        assert r.tfs_exempt == Decimal("4.81")

    def test_taxable_vp(self):
        # 16.03 - 4.81 = 11.22
        r = self._result_2024()
        assert r.taxable_vp == Decimal("11.22")

    def test_fund_declined_zero_vp(self):
        # If Dec31 < Jan1, Fondszuwachs = 0 → VP = 0
        r = self._result_2024(price_dec31=Decimal("90"))
        assert r.fondszuwachs_per_share == Decimal("0")
        assert r.vorabpauschale == Decimal("0.00")
        assert r.taxable_vp == Decimal("0.00")

    def test_zero_basiszins_year_zero_vp(self):
        # Years 2020-2022 have Basiszins = 0 → no VP
        r = self._result_2024(year=2021)
        assert r.basisertrag_per_share == Decimal("0.0000")
        assert r.vorabpauschale == Decimal("0.00")

    def test_bond_etf_zero_tfs(self):
        # Bond ETF, TFS=0 → taxable_vp = vorabpauschale
        r = self._result_2024(teilfreistellung_rate=Decimal("0"))
        assert r.tfs_exempt == Decimal("0.00")
        assert r.taxable_vp == r.vorabpauschale

    def test_is_distributing_flag(self):
        r = self._result_2024(is_distributing=True)
        assert r.is_distributing is True

    def test_result_metadata(self):
        r = self._result_2024()
        assert r.ticker == "VWCE"
        assert r.isin == "IE00BK5BQT80"
        assert r.year == 2024
        assert r.shares_jan1 == Decimal("10")

    def test_vp_capped_by_fondszuwachs(self):
        # Small gain: Basisertrag > Fondszuwachs → capped at Fondszuwachs
        # shares=100, price_jan1=1000, dec31=1001 (gain=1), Basiszins=2.29%
        # Basisertrag/share = 1000 × 0.0229 × 0.7 = 16.03
        # Fondszuwachs/share = 1
        # VP = min(16.03, 1) × 100 = 100.00
        r = calculate_vorabpauschale(
            ticker="X",
            isin="XX0000000000",
            year=2024,
            shares_jan1=Decimal("100"),
            price_jan1=Decimal("1000"),
            price_dec31=Decimal("1001"),
            teilfreistellung_rate=Decimal("0"),
        )
        assert r.fondszuwachs_per_share == Decimal("1")
        assert r.vorabpauschale == Decimal("100.00")
