"""Tests for core.tax.abgeltungssteuer.

All expected values are computed from the legal formulas:
  Abgeltungssteuer = taxable_gain × 0.25          (§ 32d EStG)
  Solidaritätszuschlag = abgeltungssteuer × 0.055  (§ 4 SolZG)
"""

from decimal import Decimal

import pytest

from portfolio_tracker.core.tax.abgeltungssteuer import (
    ABGELTUNGSSTEUER_RATE,
    SOLI_RATE,
    calculate_abgeltungssteuer,
    calculate_soli,
)


class TestConstants:
    def test_abgeltungssteuer_rate(self):
        assert ABGELTUNGSSTEUER_RATE == Decimal("0.25")

    def test_soli_rate(self):
        assert SOLI_RATE == Decimal("0.055")


class TestCalculateAbgeltungssteuer:
    def test_round_number(self):
        # 1000 × 0.25 = 250.00
        assert calculate_abgeltungssteuer(Decimal("1000")) == Decimal("250.00")

    def test_zero(self):
        assert calculate_abgeltungssteuer(Decimal("0")) == Decimal("0.00")

    def test_small_amount(self):
        # 100 × 0.25 = 25.00
        assert calculate_abgeltungssteuer(Decimal("100")) == Decimal("25.00")

    def test_large_amount(self):
        # 98000 × 0.25 = 24500.00
        assert calculate_abgeltungssteuer(Decimal("98000")) == Decimal("24500.00")

    def test_rounding_half_up(self):
        # 3.335 × 0.25 = 0.83375 → rounds to 0.83
        result = calculate_abgeltungssteuer(Decimal("3.335"))
        assert result == Decimal("0.83")

    def test_returns_two_decimal_places(self):
        result = calculate_abgeltungssteuer(Decimal("1234.56"))
        assert result == result.quantize(Decimal("0.01"))


class TestCalculateSoli:
    def test_standard_case(self):
        # 250.00 × 0.055 = 13.75
        assert calculate_soli(Decimal("250.00")) == Decimal("13.75")

    def test_zero(self):
        assert calculate_soli(Decimal("0")) == Decimal("0.00")

    def test_large_tax(self):
        # 24500.00 × 0.055 = 1347.50
        assert calculate_soli(Decimal("24500.00")) == Decimal("1347.50")

    def test_rounding(self):
        # 125.00 × 0.055 = 6.875 → rounds to 6.88
        assert calculate_soli(Decimal("125.00")) == Decimal("6.88")

    def test_returns_two_decimal_places(self):
        result = calculate_soli(Decimal("750.00"))
        assert result == result.quantize(Decimal("0.01"))


class TestCombinedTax:
    """Verify Abgeltungssteuer + Soli together for common scenarios."""

    def test_full_pipeline_1000_gain(self):
        # taxable = 1000
        # abgelt  = 250.00
        # soli    = 13.75
        # total   = 263.75
        abgelt = calculate_abgeltungssteuer(Decimal("1000"))
        soli = calculate_soli(abgelt)
        assert abgelt == Decimal("250.00")
        assert soli == Decimal("13.75")
        assert abgelt + soli == Decimal("263.75")

    def test_full_pipeline_3000_gain(self):
        # taxable = 3000
        # abgelt  = 750.00
        # soli    = 41.25
        abgelt = calculate_abgeltungssteuer(Decimal("3000"))
        soli = calculate_soli(abgelt)
        assert abgelt == Decimal("750.00")
        assert soli == Decimal("41.25")
        assert abgelt + soli == Decimal("791.25")
