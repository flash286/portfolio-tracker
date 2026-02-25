"""Tests for core.tax.freistellungsauftrag.

Freistellungsauftrag limits per § 20 Abs. 9 EStG:
  €1,000 — single filers
  €2,000 — jointly assessed couples
"""

from decimal import Decimal

import pytest

from portfolio_tracker.core.tax.freistellungsauftrag import (
    DEFAULT_FSA_JOINT,
    DEFAULT_FSA_SINGLE,
    apply_freistellungsauftrag,
)


class TestConstants:
    def test_joint_fsa(self):
        assert DEFAULT_FSA_JOINT == Decimal("2000")

    def test_single_fsa(self):
        assert DEFAULT_FSA_SINGLE == Decimal("1000")


class TestApplyFreistellungsauftrag:
    def test_gain_below_fsa(self):
        # taxable=700, fsa=1000 → used=700, remaining=0
        used, remaining = apply_freistellungsauftrag(Decimal("700"), Decimal("1000"))
        assert used == Decimal("700")
        assert remaining == Decimal("0")

    def test_gain_exactly_fsa(self):
        # taxable=1000, fsa=1000 → used=1000, remaining=0
        used, remaining = apply_freistellungsauftrag(Decimal("1000"), Decimal("1000"))
        assert used == Decimal("1000")
        assert remaining == Decimal("0")

    def test_gain_above_fsa(self):
        # taxable=1500, fsa=1000 → used=1000, remaining=500
        used, remaining = apply_freistellungsauftrag(Decimal("1500"), Decimal("1000"))
        assert used == Decimal("1000")
        assert remaining == Decimal("500")

    def test_gain_far_above_fsa(self):
        # taxable=10000, fsa=2000 → used=2000, remaining=8000
        used, remaining = apply_freistellungsauftrag(Decimal("10000"), Decimal("2000"))
        assert used == Decimal("2000")
        assert remaining == Decimal("8000")

    def test_zero_gain(self):
        used, remaining = apply_freistellungsauftrag(Decimal("0"), Decimal("2000"))
        assert used == Decimal("0")
        assert remaining == Decimal("0")

    def test_zero_fsa(self):
        # fsa=0 → nothing sheltered
        used, remaining = apply_freistellungsauftrag(Decimal("1000"), Decimal("0"))
        assert used == Decimal("0")
        assert remaining == Decimal("1000")

    def test_used_plus_remaining_equals_taxable(self):
        taxable = Decimal("3750.50")
        fsa = Decimal("2000")
        used, remaining = apply_freistellungsauftrag(taxable, fsa)
        assert used + remaining == taxable
