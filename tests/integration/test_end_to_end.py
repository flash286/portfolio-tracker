"""End-to-end integration test.

Simulates the full user journey:
  1. Revolut CSV import (two holdings, buys, dividends, cash flows)
  2. Idempotency — re-importing the same file produces zero new rows
  3. Holdings verification — shares and cost basis match the imported data
  4. Cash balance — all cash flows sum correctly
  5. Portfolio calculations — value, P&L, allocation via core.finance
  6. German tax calculation — TFS + FSA + Abgeltungssteuer pipeline
  7. Vorabpauschale — annual prepayment tax for accumulating ETFs

Demo portfolio
--------------
Two ETFs bought in January 2023:

  VWCE  100 shares @ €100  =  €10,000 cost  (equity ETF, TFS 30%)
  IS3C   50 shares @ €80   =   €4,000 cost  (bond ETF,   TFS 0%, distributing)

Cash flows:
  Top-up             +€15,000
  Buy VWCE           −€10,000
  Buy IS3C            −€4,000
  Dividend IS3C ×2   +€100 total
  Robo fee                −€20
  ──────────────────────────
  Balance              €1,080

Current prices (injected without network calls):
  VWCE → €130   (unrealised gain: 100 × €30 = €3,000)
  IS3C → €90    (unrealised gain:  50 × €10 = €500)
  Total unrealised P&L: €3,500
"""

import textwrap
from decimal import Decimal

import pytest

from portfolio_tracker.core.finance import (
    allocation_by_type,
    total_cost_basis,
    total_unrealized_pnl,
    total_value,
)
from portfolio_tracker.core.tax import calculate_german_tax
from portfolio_tracker.core.tax.teilfreistellung import weighted_portfolio_tfs
from portfolio_tracker.core.tax.vorabpauschale import calculate_vorabpauschale
from portfolio_tracker.data.repositories.cash_repo import CashRepository
from portfolio_tracker.data.repositories.holdings_repo import HoldingsRepository
from portfolio_tracker.data.repositories.prices_repo import PricesRepository
from portfolio_tracker.importers.revolut import RevolutImporter

# ---------------------------------------------------------------------------
# Demo CSV — all buys in 2023 so full holdings are held on Jan 1 2024
# ---------------------------------------------------------------------------

DEMO_CSV = textwrap.dedent("""\
    Type,Ticker,Date,Quantity,Price per share,Total Amount
    CASH TOP-UP,,2023-01-01T00:00:00Z,,,EUR 15000.00
    BUY - MARKET,VWCE,2023-01-15T10:00:00Z,100,EUR 100.00,EUR 10000.00
    BUY - MARKET,IS3C,2023-01-20T10:00:00Z,50,EUR 80.00,EUR 4000.00
    DIVIDEND,IS3C,2023-06-15T10:00:00Z,,,EUR 50.00
    DIVIDEND,IS3C,2023-12-15T10:00:00Z,,,EUR 50.00
    ROBO MANAGEMENT FEE,,2023-12-31T10:00:00Z,,,EUR -20.00
""")

# Current prices injected without yfinance network call
VWCE_PRICE = Decimal("130")
IS3C_PRICE = Decimal("90")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def csv_file(tmp_path):
    """Write demo CSV to a temp file."""
    p = tmp_path / "revolut_transactions.csv"
    p.write_text(DEMO_CSV, encoding="utf-8")
    return p


@pytest.fixture
def import_result(csv_file, isolated_db):
    """Run the Revolut importer and return the ImportResult."""
    importer = RevolutImporter(
        portfolio_name="Demo Revolut",
        dry_run=False,
        interactive=False,
    )
    return importer.run(csv_file)


@pytest.fixture
def portfolio_with_prices(import_result, isolated_db):
    """Inject current prices and attach them to holdings (mirrors stats.py logic)."""
    holdings_repo = HoldingsRepository()
    prices_repo = PricesRepository()

    price_map = {"VWCE": VWCE_PRICE, "IS3C": IS3C_PRICE}

    holdings = holdings_repo.list_by_portfolio(import_result.portfolio_id)
    for h in holdings:
        if h.ticker in price_map:
            from datetime import datetime

            from portfolio_tracker.core.models import PricePoint
            prices_repo.store_price(PricePoint(
                holding_id=h.id, price=price_map[h.ticker],
                fetch_date=datetime.now(), source="test",
            ))

    # Attach latest price to each holding (mirrors how CLI commands do it)
    holdings = holdings_repo.list_by_portfolio(import_result.portfolio_id)
    for h in holdings:
        latest = prices_repo.get_latest(h.id)
        if latest:
            h.current_price = latest.price

    return holdings


# ---------------------------------------------------------------------------
# 1. Import counts
# ---------------------------------------------------------------------------

class TestImportCounts:
    def test_holdings_created(self, import_result):
        assert import_result.holdings_created == 2

    def test_holdings_reused(self, import_result):
        assert import_result.holdings_skipped == 0

    def test_buys_imported(self, import_result):
        assert import_result.buys_imported == 2

    def test_dividends_imported(self, import_result):
        assert import_result.dividends_imported == 2

    def test_cash_rows_imported(self, import_result):
        # 1 top-up + 2 buy-cash + 2 dividend-cash + 1 fee = 6
        assert import_result.cash_imported == 6

    def test_no_skips_on_first_run(self, import_result):
        assert import_result.buys_skipped == 0
        assert import_result.dividends_skipped == 0
        assert import_result.cash_skipped == 0

    def test_no_unknown_tickers(self, import_result):
        assert import_result.unknown_tickers == []

    def test_no_warnings(self, import_result):
        assert import_result.warnings == []

    def test_not_dry_run(self, import_result):
        assert import_result.dry_run is False


# ---------------------------------------------------------------------------
# 2. Idempotency — re-running on the same file produces zero new rows
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_second_import_skips_all(self, csv_file, import_result, isolated_db):
        importer = RevolutImporter(
            portfolio_name="Demo Revolut",
            dry_run=False,
            interactive=False,
        )
        result2 = importer.run(csv_file)

        assert result2.buys_imported == 0
        assert result2.dividends_imported == 0
        assert result2.cash_imported == 0

        assert result2.buys_skipped == 2
        assert result2.dividends_skipped == 2
        assert result2.cash_skipped == 6

    def test_second_import_reuses_holdings(self, csv_file, import_result, isolated_db):
        importer = RevolutImporter(
            portfolio_name="Demo Revolut",
            dry_run=False,
            interactive=False,
        )
        result2 = importer.run(csv_file)

        assert result2.holdings_created == 0
        assert result2.holdings_skipped == 2

    def test_dry_run_shows_counts_without_writing(self, csv_file, isolated_db):
        importer = RevolutImporter(
            portfolio_name="Dry Test",
            dry_run=True,
            interactive=False,
        )
        result = importer.run(csv_file)

        assert result.dry_run is True
        assert result.buys_imported == 2
        assert result.dividends_imported == 2

        # Nothing actually written — portfolio shouldn't exist
        from portfolio_tracker.data.repositories.portfolios_repo import PortfoliosRepository
        assert PortfoliosRepository().get_by_name("Dry Test") is None


# ---------------------------------------------------------------------------
# 3. Holdings state after import
# ---------------------------------------------------------------------------

class TestHoldingsState:
    def _holdings_by_ticker(self, portfolio_id):
        repo = HoldingsRepository()
        return {h.ticker: h for h in repo.list_by_portfolio(portfolio_id)}

    def test_vwce_shares(self, import_result):
        holdings = self._holdings_by_ticker(import_result.portfolio_id)
        assert holdings["VWCE"].shares == Decimal("100")

    def test_vwce_cost_basis(self, import_result):
        holdings = self._holdings_by_ticker(import_result.portfolio_id)
        assert holdings["VWCE"].cost_basis == Decimal("10000")

    def test_is3c_shares(self, import_result):
        holdings = self._holdings_by_ticker(import_result.portfolio_id)
        assert holdings["IS3C"].shares == Decimal("50")

    def test_is3c_cost_basis(self, import_result):
        holdings = self._holdings_by_ticker(import_result.portfolio_id)
        assert holdings["IS3C"].cost_basis == Decimal("4000")

    def test_vwce_tfs_rate(self, import_result):
        holdings = self._holdings_by_ticker(import_result.portfolio_id)
        assert holdings["VWCE"].teilfreistellung_rate == Decimal("0.3")

    def test_is3c_tfs_rate(self, import_result):
        # IS3C is a bond ETF — no TFS
        holdings = self._holdings_by_ticker(import_result.portfolio_id)
        assert holdings["IS3C"].teilfreistellung_rate == Decimal("0")


# ---------------------------------------------------------------------------
# 4. Cash balance
# ---------------------------------------------------------------------------

class TestCashBalance:
    def test_total_balance(self, import_result):
        cash_repo = CashRepository()
        balance = cash_repo.get_balance(import_result.portfolio_id)
        # +15000 −10000 −4000 +50 +50 −20 = 1080
        assert balance == Decimal("1080")

    def test_balance_unchanged_after_second_import(self, csv_file, import_result, isolated_db):
        """Re-importing must not double-count cash flows."""
        importer = RevolutImporter(
            portfolio_name="Demo Revolut",
            dry_run=False,
            interactive=False,
        )
        importer.run(csv_file)

        cash_repo = CashRepository()
        balance = cash_repo.get_balance(import_result.portfolio_id)
        assert balance == Decimal("1080")


# ---------------------------------------------------------------------------
# 5. Portfolio value and allocation (core.finance)
# ---------------------------------------------------------------------------

class TestPortfolioCalculations:
    def test_total_value(self, portfolio_with_prices):
        # VWCE: 100 × 130 = 13000, IS3C: 50 × 90 = 4500
        assert total_value(portfolio_with_prices) == Decimal("13000") + Decimal("4500")

    def test_total_cost_basis(self, portfolio_with_prices):
        assert total_cost_basis(portfolio_with_prices) == Decimal("14000")

    def test_total_unrealized_pnl(self, portfolio_with_prices):
        # 17500 - 14000 = 3500
        assert total_unrealized_pnl(portfolio_with_prices) == Decimal("3500")

    def test_allocation_by_type_has_etf_and_bond(self, portfolio_with_prices):
        alloc = allocation_by_type(portfolio_with_prices)
        assert "etf" in alloc
        assert "bond" in alloc

    def test_allocation_sums_to_100(self, portfolio_with_prices):
        alloc = allocation_by_type(portfolio_with_prices)
        total = sum(alloc.values())
        # Allow ±0.02 for rounding across holdings
        assert abs(total - Decimal("100")) <= Decimal("0.02")

    def test_vwce_dominates_allocation(self, portfolio_with_prices):
        # VWCE: 13000/17500 ≈ 74.3% > IS3C: 25.7%
        alloc = allocation_by_type(portfolio_with_prices)
        assert alloc["etf"] > alloc["bond"]

    def test_weighted_tfs(self, portfolio_with_prices):
        # weighted = (13000 × 0.3 + 4500 × 0) / 17500 = 3900/17500 ≈ 0.2229
        w_tfs = weighted_portfolio_tfs(portfolio_with_prices)
        assert w_tfs == Decimal("0.2229")


# ---------------------------------------------------------------------------
# 6. German tax calculation (core.tax)
# ---------------------------------------------------------------------------

class TestTaxCalculation:
    """
    Verify the full tax pipeline on the unrealised P&L of €3,500.

    Pipeline (weighted TFS = 0.2229, FSA = €2,000):
      tfs_exempt          = 3500 × 0.2229 = 780.15
      taxable_after_tfs   = 3500 − 780.15 = 2719.85
      fsa_used            = min(2719.85, 2000) = 2000
      taxable_gain        = 2719.85 − 2000 = 719.85
      abgeltungssteuer    = 719.85 × 0.25  = 179.96
      solidaritaetszusch. = 179.96 × 0.055 = 9.90
      total_tax           = 189.86
    """

    GAIN = Decimal("3500")
    FSA = Decimal("2000")
    W_TFS = Decimal("0.2229")

    @pytest.fixture
    def tax_info(self):
        return calculate_german_tax(self.GAIN, self.FSA, self.W_TFS)

    def test_tfs_exempt(self, tax_info):
        assert tax_info.teilfreistellung_exempt == Decimal("780.15")

    def test_taxable_after_fsa(self, tax_info):
        assert tax_info.taxable_gain == Decimal("719.85")

    def test_fsa_used(self, tax_info):
        assert tax_info.freistellungsauftrag_used == Decimal("2000")

    def test_abgeltungssteuer(self, tax_info):
        assert tax_info.abgeltungssteuer == Decimal("179.96")

    def test_soli(self, tax_info):
        assert tax_info.solidaritaetszuschlag == Decimal("9.90")

    def test_total_tax(self, tax_info):
        assert tax_info.total_tax == Decimal("189.86")

    def test_net_gain(self, tax_info):
        # 3500 - 189.86 = 3310.14
        assert tax_info.net_gain == Decimal("3310.14")

    def test_no_tax_below_fsa(self):
        """Gain fully within FSA → zero tax."""
        info = calculate_german_tax(Decimal("1500"), Decimal("2000"), Decimal("0.3"))
        # tfs_exempt = 450, taxable_after_tfs = 1050
        # fsa covers 1050 → taxable_gain = 0
        assert info.total_tax == Decimal("0")
        assert info.taxable_gain == Decimal("0")


# ---------------------------------------------------------------------------
# 7. Vorabpauschale for holdings held through 2023
# ---------------------------------------------------------------------------

class TestVorabpauschale:
    """
    Both holdings were bought in 2023, so on Jan 1 2024:
      VWCE: 100 shares held, price_jan1 = €100, price_dec31 = €130
      IS3C:  50 shares held, price_jan1 = €80,  price_dec31 = €90

    Using Basiszins 2024 = 2.29% (BASISZINS[2024]).
    """

    YEAR = 2024

    @pytest.fixture
    def vwce_vp(self):
        return calculate_vorabpauschale(
            ticker="VWCE",
            isin="IE00BK5BQT80",
            year=self.YEAR,
            shares_jan1=Decimal("100"),
            price_jan1=Decimal("100"),
            price_dec31=Decimal("130"),
            teilfreistellung_rate=Decimal("0.3"),
            is_distributing=False,
        )

    @pytest.fixture
    def is3c_vp(self):
        return calculate_vorabpauschale(
            ticker="IS3C",
            isin="IE00B9M6RS56",
            year=self.YEAR,
            shares_jan1=Decimal("50"),
            price_jan1=Decimal("80"),
            price_dec31=Decimal("90"),
            teilfreistellung_rate=Decimal("0"),
            is_distributing=True,  # paid dividends
        )

    # VWCE — equity ETF, capped by basisertrag (gain >> basisertrag)
    def test_vwce_basisertrag_per_share(self, vwce_vp):
        # 100 × 0.0229 × 0.7 = 1.6030
        assert vwce_vp.basisertrag_per_share == Decimal("1.6030")

    def test_vwce_vorabpauschale(self, vwce_vp):
        # min(1.6030, 30) × 100 = 160.30
        assert vwce_vp.vorabpauschale == Decimal("160.30")

    def test_vwce_tfs_exempt(self, vwce_vp):
        # 160.30 × 0.3 = 48.09
        assert vwce_vp.tfs_exempt == Decimal("48.09")

    def test_vwce_taxable_vp(self, vwce_vp):
        # 160.30 - 48.09 = 112.21
        assert vwce_vp.taxable_vp == Decimal("112.21")

    # IS3C — bond ETF, distributing, no TFS
    def test_is3c_basisertrag_per_share(self, is3c_vp):
        # 80 × 0.0229 × 0.7 = 1.2824
        assert is3c_vp.basisertrag_per_share == Decimal("1.2824")

    def test_is3c_vorabpauschale(self, is3c_vp):
        # min(1.2824, 10) × 50 = 64.12
        assert is3c_vp.vorabpauschale == Decimal("64.12")

    def test_is3c_no_tfs(self, is3c_vp):
        assert is3c_vp.tfs_exempt == Decimal("0.00")
        assert is3c_vp.taxable_vp == is3c_vp.vorabpauschale

    def test_is3c_distributing_flag(self, is3c_vp):
        assert is3c_vp.is_distributing is True

    def test_combined_vp_tax(self, vwce_vp, is3c_vp):
        """Tax on combined Vorabpauschale from both holdings."""
        total_taxable_vp = vwce_vp.taxable_vp + is3c_vp.taxable_vp
        # 112.21 + 64.12 = 176.33 — well within €2,000 FSA → no tax
        assert total_taxable_vp == Decimal("176.33")

        tax = calculate_german_tax(total_taxable_vp, Decimal("2000"))
        assert tax.total_tax == Decimal("0")
        assert tax.freistellungsauftrag_used == total_taxable_vp

    def test_zero_basiszins_year_no_vp(self):
        """Years with Basiszins = 0 (2020–2022) produce no Vorabpauschale."""
        for year in (2020, 2021, 2022):
            result = calculate_vorabpauschale(
                ticker="VWCE",
                isin="IE00BK5BQT80",
                year=year,
                shares_jan1=Decimal("100"),
                price_jan1=Decimal("100"),
                price_dec31=Decimal("120"),
                teilfreistellung_rate=Decimal("0.3"),
            )
            assert result.vorabpauschale == Decimal("0.00"), \
                f"Expected 0 VP for year {year} (Basiszins=0)"
