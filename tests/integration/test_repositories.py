"""Integration tests for repository CRUD operations."""

from datetime import datetime
from decimal import Decimal

import pytest

from portfolio_tracker.core.models import (
    AssetType,
    CashTransaction,
    CashTransactionType,
    Holding,
    Portfolio,
    PricePoint,
    TargetAllocation,
    TaxLot,
    Transaction,
    TransactionType,
)
from portfolio_tracker.data.repositories.cash_repo import CashRepository
from portfolio_tracker.data.repositories.holdings_repo import HoldingsRepository
from portfolio_tracker.data.repositories.lots_repo import LotsRepository
from portfolio_tracker.data.repositories.portfolios_repo import PortfoliosRepository
from portfolio_tracker.data.repositories.prices_repo import PricesRepository
from portfolio_tracker.data.repositories.targets_repo import TargetsRepository
from portfolio_tracker.data.repositories.transactions_repo import TransactionsRepository


class TestPortfolioRepository:
    def test_create_and_get(self, isolated_db):
        repo = PortfoliosRepository()
        p = repo.create(Portfolio(name="My Portfolio", description="Test description"))

        assert p.id is not None
        assert p.name == "My Portfolio"
        assert p.description == "Test description"

        fetched = repo.get_by_id(p.id)
        assert fetched.name == "My Portfolio"
        assert fetched.description == "Test description"

    def test_get_by_name(self, isolated_db):
        repo = PortfoliosRepository()
        repo.create(Portfolio(name="Alpha"))
        repo.create(Portfolio(name="Beta"))

        p = repo.get_by_name("Beta")
        assert p is not None
        assert p.name == "Beta"

    def test_get_by_name_not_found(self, isolated_db):
        assert PortfoliosRepository().get_by_name("Nonexistent") is None

    def test_list_all(self, isolated_db):
        repo = PortfoliosRepository()
        repo.create(Portfolio(name="A"))
        repo.create(Portfolio(name="B"))
        repo.create(Portfolio(name="C"))
        assert len(repo.list_all()) == 3

    def test_delete(self, isolated_db):
        repo = PortfoliosRepository()
        p = repo.create(Portfolio(name="ToDelete"))
        assert repo.delete(p.id) is True
        assert repo.get_by_id(p.id) is None

    def test_delete_nonexistent(self, isolated_db):
        assert PortfoliosRepository().delete(9999) is False


class TestHoldingsRepository:
    def _portfolio(self):
        return PortfoliosRepository().create(Portfolio(name="Test"))

    def test_create_and_get_by_id(self, isolated_db):
        p = self._portfolio()
        repo = HoldingsRepository()
        h = repo.create(Holding(
            portfolio_id=p.id, isin="IE00B4L5Y983", asset_type=AssetType.ETF,
            name="World ETF", ticker="IWDA",
        ))

        assert h.id is not None
        assert h.isin == "IE00B4L5Y983"
        assert h.asset_type == AssetType.ETF
        assert h.ticker == "IWDA"
        assert h.shares == Decimal("0")
        assert h.teilfreistellung_rate == Decimal("0")

    def test_create_with_tfs_rate(self, isolated_db):
        """Teilfreistellung rate is stored and retrieved correctly."""
        p = self._portfolio()
        repo = HoldingsRepository()
        h = repo.create(Holding(
            portfolio_id=p.id, isin="IE00B4L5Y983", asset_type=AssetType.ETF,
            teilfreistellung_rate=Decimal("0.3"),
        ))
        assert h.teilfreistellung_rate == Decimal("0.3")

        fetched = repo.get_by_id(h.id)
        assert fetched.teilfreistellung_rate == Decimal("0.3")

    def test_get_by_isin(self, isolated_db):
        p = self._portfolio()
        HoldingsRepository().create(Holding(
            portfolio_id=p.id, isin="IE00B4L5Y983", asset_type=AssetType.ETF,
        ))
        h = HoldingsRepository().get_by_isin(p.id, "IE00B4L5Y983")
        assert h is not None
        assert h.isin == "IE00B4L5Y983"

    def test_unique_constraint(self, isolated_db):
        """Duplicate ISIN in same portfolio raises an integrity error."""
        p = self._portfolio()
        repo = HoldingsRepository()
        repo.create(Holding(portfolio_id=p.id, isin="IE00B4L5Y983", asset_type=AssetType.ETF))
        with pytest.raises(Exception):  # sqlite3.IntegrityError
            repo.create(Holding(portfolio_id=p.id, isin="IE00B4L5Y983", asset_type=AssetType.ETF))

    def test_save_updates_holding(self, isolated_db):
        """save() updates shares and cost_basis correctly."""
        p = self._portfolio()
        h = HoldingsRepository().create(Holding(
            portfolio_id=p.id, isin="IE00B4L5Y983", asset_type=AssetType.ETF,
        ))
        h.shares = Decimal("10.5")
        h.cost_basis = Decimal("1050.00")
        HoldingsRepository().save(h)

        h_after = HoldingsRepository().get_by_id(h.id)
        assert h_after.shares == Decimal("10.5")
        assert h_after.cost_basis == Decimal("1050.00")

    def test_delete_cascades_transactions(self, isolated_db):
        """Deleting a holding removes its transactions via CASCADE."""
        p = self._portfolio()
        h = HoldingsRepository().create(Holding(
            portfolio_id=p.id, isin="IE00B4L5Y983", asset_type=AssetType.ETF,
        ))
        tx_repo = TransactionsRepository()
        tx_repo.create(Transaction(
            holding_id=h.id, transaction_type=TransactionType.BUY,
            quantity=Decimal("10"), price=Decimal("50"), transaction_date=datetime.now(),
        ))

        HoldingsRepository().delete(h.id)
        assert tx_repo.list_by_holding(h.id) == []


class TestCashRepository:
    def _portfolio(self):
        return PortfoliosRepository().create(Portfolio(name="Test"))

    def test_create_and_get(self, isolated_db):
        p = self._portfolio()
        repo = CashRepository()
        tx = repo.create(CashTransaction(
            portfolio_id=p.id, cash_type=CashTransactionType.TOP_UP,
            amount=Decimal("1000"), transaction_date=datetime.now(),
        ))

        assert tx.id is not None
        assert tx.portfolio_id == p.id
        assert tx.amount == Decimal("1000")

    def test_balance_sum(self, isolated_db):
        """Balance is the sum of all cash transaction amounts."""
        p = self._portfolio()
        repo = CashRepository()
        now = datetime.now()

        repo.create(CashTransaction(portfolio_id=p.id, cash_type=CashTransactionType.TOP_UP, amount=Decimal("1000"), transaction_date=now))
        repo.create(CashTransaction(portfolio_id=p.id, cash_type=CashTransactionType.BUY, amount=Decimal("-500"), transaction_date=now))
        repo.create(CashTransaction(portfolio_id=p.id, cash_type=CashTransactionType.DIVIDEND, amount=Decimal("50"), transaction_date=now))
        repo.create(CashTransaction(portfolio_id=p.id, cash_type=CashTransactionType.FEE, amount=Decimal("-10"), transaction_date=now))

        assert repo.get_balance(p.id) == Decimal("540")

    def test_zero_balance_when_empty(self, isolated_db):
        p = self._portfolio()
        assert CashRepository().get_balance(p.id) == Decimal("0")

    def test_list_by_portfolio(self, isolated_db):
        p = self._portfolio()
        repo = CashRepository()
        now = datetime.now()
        repo.create(CashTransaction(portfolio_id=p.id, cash_type=CashTransactionType.TOP_UP, amount=Decimal("100"), transaction_date=now))
        repo.create(CashTransaction(portfolio_id=p.id, cash_type=CashTransactionType.TOP_UP, amount=Decimal("200"), transaction_date=now))
        assert len(repo.list_by_portfolio(p.id)) == 2


class TestPricesRepository:
    def _holding(self):
        p = PortfoliosRepository().create(Portfolio(name="Test"))
        return HoldingsRepository().create(Holding(
            portfolio_id=p.id, isin="IE00B4L5Y983", asset_type=AssetType.ETF,
        ))

    def test_store_and_get_latest(self, isolated_db):
        h = self._holding()
        repo = PricesRepository()

        repo.store_price(PricePoint(holding_id=h.id, price=Decimal("100.00"), fetch_date=datetime.now(), source="test"))
        latest = repo.store_price(PricePoint(holding_id=h.id, price=Decimal("110.50"), fetch_date=datetime.now(), source="test"))

        result = repo.get_latest(h.id)
        assert result.price == Decimal("110.50")
        assert result.id == latest.id

    def test_get_latest_none_when_empty(self, isolated_db):
        h = self._holding()
        assert PricesRepository().get_latest(h.id) is None

    def test_get_history(self, isolated_db):
        h = self._holding()
        repo = PricesRepository()
        for price in [100, 105, 110]:
            repo.store_price(PricePoint(holding_id=h.id, price=Decimal(str(price)), fetch_date=datetime.now(), source="test"))

        history = repo.get_history(h.id)
        assert len(history) == 3
        # History is chronological (oldest first)
        assert history[0].price == Decimal("100")
        assert history[-1].price == Decimal("110")


class TestTargetsRepository:
    def _portfolio(self):
        return PortfoliosRepository().create(Portfolio(name="Test"))

    def test_set_and_get(self, isolated_db):
        p = self._portfolio()
        repo = TargetsRepository()
        t = repo.set_target(TargetAllocation(
            portfolio_id=p.id, asset_type="etf",
            target_percentage=Decimal("80"), rebalance_threshold=Decimal("5"),
        ))

        assert t.portfolio_id == p.id
        assert t.asset_type == "etf"
        assert t.target_percentage == Decimal("80")

    def test_upsert_updates_existing(self, isolated_db):
        p = self._portfolio()
        repo = TargetsRepository()
        repo.set_target(TargetAllocation(portfolio_id=p.id, asset_type="etf", target_percentage=Decimal("80")))
        repo.set_target(TargetAllocation(portfolio_id=p.id, asset_type="etf", target_percentage=Decimal("90")))

        t = repo.get(p.id, "etf")
        assert t.target_percentage == Decimal("90")

    def test_list_by_portfolio(self, isolated_db):
        p = self._portfolio()
        repo = TargetsRepository()
        repo.set_target(TargetAllocation(portfolio_id=p.id, asset_type="etf", target_percentage=Decimal("70")))
        repo.set_target(TargetAllocation(portfolio_id=p.id, asset_type="bond", target_percentage=Decimal("30")))

        targets = repo.list_by_portfolio(p.id)
        assert len(targets) == 2

    def test_delete(self, isolated_db):
        p = self._portfolio()
        repo = TargetsRepository()
        repo.set_target(TargetAllocation(portfolio_id=p.id, asset_type="etf", target_percentage=Decimal("100")))
        assert repo.delete(p.id, "etf") is True
        assert repo.get(p.id, "etf") is None


class TestLotsRepository:
    def _holding(self):
        p = PortfoliosRepository().create(Portfolio(name="Test"))
        return HoldingsRepository().create(Holding(
            portfolio_id=p.id, isin="IE00B4L5Y983", asset_type=AssetType.ETF,
        ))

    def test_create_and_get(self, isolated_db):
        h = self._holding()
        repo = LotsRepository()
        now = datetime.now()
        lot = repo.create(TaxLot(
            holding_id=h.id, acquired_date=now,
            quantity=Decimal("10"), cost_per_unit=Decimal("100.00"),
            quantity_remaining=Decimal("10"),
        ))

        assert lot.id is not None
        assert lot.holding_id == h.id
        assert lot.quantity == Decimal("10")
        assert lot.cost_per_unit == Decimal("100.00")
        assert lot.quantity_remaining == Decimal("10")

    def test_get_open_lots_fifo_order(self, isolated_db):
        """Open lots are returned oldest-first (FIFO)."""
        h = self._holding()
        repo = LotsRepository()
        from datetime import timedelta
        base = datetime(2024, 1, 1)
        repo.create(TaxLot(holding_id=h.id, acquired_date=base + timedelta(days=30), quantity=Decimal("5"), cost_per_unit=Decimal("110"), quantity_remaining=Decimal("5")))
        repo.create(TaxLot(holding_id=h.id, acquired_date=base, quantity=Decimal("10"), cost_per_unit=Decimal("100"), quantity_remaining=Decimal("10")))  # oldest
        repo.create(TaxLot(holding_id=h.id, acquired_date=base + timedelta(days=60), quantity=Decimal("3"), cost_per_unit=Decimal("120"), quantity_remaining=Decimal("3")))

        lots = repo.get_open_lots_fifo(h.id)
        assert len(lots) == 3
        assert lots[0].cost_per_unit == Decimal("100")   # oldest first
        assert lots[1].cost_per_unit == Decimal("110")
        assert lots[2].cost_per_unit == Decimal("120")

    def test_reduce_lot(self, isolated_db):
        h = self._holding()
        repo = LotsRepository()
        lot = repo.create(TaxLot(
            holding_id=h.id, acquired_date=datetime.now(),
            quantity=Decimal("10"), cost_per_unit=Decimal("100"),
            quantity_remaining=Decimal("10"),
        ))

        repo.reduce_lot(lot.id, Decimal("4"))
        updated = repo.get_by_id(lot.id)
        assert updated.quantity_remaining == Decimal("6")

    def test_fully_consumed_lot_excluded_from_open(self, isolated_db):
        h = self._holding()
        repo = LotsRepository()
        lot = repo.create(TaxLot(
            holding_id=h.id, acquired_date=datetime.now(),
            quantity=Decimal("10"), cost_per_unit=Decimal("100"),
            quantity_remaining=Decimal("10"),
        ))

        repo.reduce_lot(lot.id, Decimal("10"))
        open_lots = repo.get_open_lots_fifo(h.id)
        assert len(open_lots) == 0

    def test_get_fifo_cost_basis(self, isolated_db):
        """FIFO cost basis = sum(quantity_remaining * cost_per_unit) for open lots."""
        h = self._holding()
        repo = LotsRepository()
        now = datetime.now()
        lot1 = repo.create(TaxLot(holding_id=h.id, acquired_date=now, quantity=Decimal("10"), cost_per_unit=Decimal("100"), quantity_remaining=Decimal("10")))
        lot2 = repo.create(TaxLot(holding_id=h.id, acquired_date=now, quantity=Decimal("5"), cost_per_unit=Decimal("120"), quantity_remaining=Decimal("5")))

        # Before any reduction: 10*100 + 5*120 = 1600
        assert repo.get_fifo_cost_basis(h.id) == Decimal("1600")

        # Fully consume lot1
        repo.reduce_lot(lot1.id, Decimal("10"))
        # Now: 0*100 + 5*120 = 600
        assert repo.get_fifo_cost_basis(h.id) == Decimal("600")

    def test_list_by_holding_includes_consumed(self, isolated_db):
        """list_by_holding returns all lots, including fully consumed."""
        h = self._holding()
        repo = LotsRepository()
        lot = repo.create(TaxLot(
            holding_id=h.id, acquired_date=datetime.now(),
            quantity=Decimal("5"), cost_per_unit=Decimal("100"),
            quantity_remaining=Decimal("5"),
        ))
        repo.reduce_lot(lot.id, Decimal("5"))  # fully consumed

        all_lots = repo.list_by_holding(h.id)
        assert len(all_lots) == 1
        assert all_lots[0].quantity_remaining == Decimal("0")


class TestDecimalStorage:
    """Verify financial values are stored as TEXT (not REAL) to preserve precision."""

    def _holding(self):
        p = PortfoliosRepository().create(Portfolio(name="Test"))
        return HoldingsRepository().create(Holding(
            portfolio_id=p.id, isin="IE00B4L5Y983", asset_type=AssetType.ETF,
        ))

    def test_holdings_shares_stored_as_text(self, isolated_db):
        h = self._holding()
        h.shares = Decimal("10.123456789")
        h.cost_basis = Decimal("1012.34")
        HoldingsRepository().save(h)

        from portfolio_tracker.data.database import get_db
        db = get_db()
        row = db.conn.execute(
            "SELECT shares, cost_basis FROM holdings WHERE id = ?", (h.id,)
        ).fetchone()
        assert isinstance(row["shares"], str), f"Expected str, got {type(row['shares'])}"
        assert isinstance(row["cost_basis"], str)

    def test_price_history_stored_as_text(self, isolated_db):
        h = self._holding()
        PricesRepository().store_price(PricePoint(
            holding_id=h.id, price=Decimal("99.9999"), fetch_date=datetime.now(), source="test",
        ))
        from portfolio_tracker.data.database import get_db
        db = get_db()
        row = db.conn.execute(
            "SELECT price FROM price_history WHERE holding_id = ?", (h.id,)
        ).fetchone()
        assert isinstance(row["price"], str)

    def test_cash_transactions_stored_as_text(self, isolated_db):
        p = PortfoliosRepository().create(Portfolio(name="Test"))
        CashRepository().create(CashTransaction(
            portfolio_id=p.id, cash_type=CashTransactionType.TOP_UP,
            amount=Decimal("1000.50"), transaction_date=datetime.now(),
        ))
        from portfolio_tracker.data.database import get_db
        db = get_db()
        row = db.conn.execute(
            "SELECT amount FROM cash_transactions WHERE portfolio_id = ?", (p.id,)
        ).fetchone()
        assert isinstance(row["amount"], str)

    def test_transactions_stored_as_text(self, isolated_db):
        h = self._holding()
        TransactionsRepository().create(Transaction(
            holding_id=h.id, transaction_type=TransactionType.BUY,
            quantity=Decimal("3.14159"), price=Decimal("99.99"),
            transaction_date=datetime.now(),
        ))
        from portfolio_tracker.data.database import get_db
        db = get_db()
        row = db.conn.execute(
            "SELECT quantity, price FROM transactions WHERE holding_id = ?", (h.id,)
        ).fetchone()
        assert isinstance(row["quantity"], str)
        assert isinstance(row["price"], str)
