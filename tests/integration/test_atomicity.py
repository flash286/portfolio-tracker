"""Integration tests verifying atomic database operations."""

from datetime import datetime
from decimal import Decimal

import pytest

from portfolio_tracker.core.models import (
    AssetType,
    CashTransaction,
    CashTransactionType,
    Holding,
    Portfolio,
    Transaction,
    TransactionType,
)
from portfolio_tracker.data.repositories.cash_repo import CashRepository
from portfolio_tracker.data.repositories.holdings_repo import HoldingsRepository
from portfolio_tracker.data.repositories.portfolios_repo import PortfoliosRepository
from portfolio_tracker.data.repositories.transactions_repo import TransactionsRepository


def _make_portfolio(name="Test"):
    return PortfoliosRepository().create(Portfolio(name=name))


def _make_holding(portfolio_id, isin="IE00B4L5Y983", ticker="IWDA"):
    return HoldingsRepository().create(Holding(
        portfolio_id=portfolio_id, isin=isin, asset_type=AssetType.ETF, ticker=ticker,
    ))


class TestTransactionContextManager:
    def test_rollback_on_error(self, isolated_db):
        """db.transaction() rolls back all writes when an exception is raised."""
        portfolios_repo = PortfoliosRepository()

        with pytest.raises(RuntimeError):
            with isolated_db.transaction():
                portfolios_repo.create(Portfolio(name="Should Be Rolled Back"))
                raise RuntimeError("Forced rollback")

        assert portfolios_repo.list_all() == []

    def test_commit_on_success(self, isolated_db):
        """db.transaction() commits all writes on success."""
        portfolios_repo = PortfoliosRepository()
        holdings_repo = HoldingsRepository()

        with isolated_db.transaction():
            p = portfolios_repo.create(Portfolio(name="Committed Portfolio"))
            holdings_repo.create(Holding(
                portfolio_id=p.id, isin="IE00B4L5Y983", asset_type=AssetType.ETF, ticker="IWDA",
            ))

        portfolios = portfolios_repo.list_all()
        assert len(portfolios) == 1
        holdings = holdings_repo.list_by_portfolio(portfolios[0].id)
        assert len(holdings) == 1

    def test_in_transaction_flag_resets_after_success(self, isolated_db):
        """_in_transaction flag is False after a successful transaction."""
        assert isolated_db._in_transaction is False
        with isolated_db.transaction():
            assert isolated_db._in_transaction is True
        assert isolated_db._in_transaction is False

    def test_in_transaction_flag_resets_after_error(self, isolated_db):
        """_in_transaction flag is False even after a failed transaction."""
        with pytest.raises(RuntimeError):
            with isolated_db.transaction():
                raise RuntimeError("error")
        assert isolated_db._in_transaction is False


class TestBuyAtomicity:
    def test_buy_is_atomic_on_cash_failure(self, isolated_db, monkeypatch):
        """If cash recording fails, tx and holding update are both rolled back."""
        p = _make_portfolio()
        h = _make_holding(p.id)

        holdings_repo = HoldingsRepository()
        tx_repo = TransactionsRepository()
        cash_repo = CashRepository()

        qty = Decimal("10")
        prc = Decimal("50")
        now = datetime.now()

        def failing_cash_create(self, *args, **kwargs):
            raise RuntimeError("Cash DB error")

        monkeypatch.setattr(CashRepository, "create", failing_cash_create)

        with pytest.raises(RuntimeError):
            with isolated_db.transaction():
                tx_repo.create(Transaction(
                    holding_id=h.id, transaction_type=TransactionType.BUY,
                    quantity=qty, price=prc, transaction_date=now,
                ))
                h.shares = qty
                h.cost_basis = qty * prc
                holdings_repo.save(h)
                cash_repo.create(CashTransaction(
                    portfolio_id=p.id, cash_type=CashTransactionType.BUY,
                    amount=-(qty * prc), transaction_date=now,
                ))

        # Everything rolled back
        h_after = HoldingsRepository().get_by_id(h.id)
        assert h_after.shares == Decimal("0")
        assert tx_repo.list_by_holding(h.id) == []
        assert cash_repo.get_balance(p.id) == Decimal("0")

    def test_sell_records_atomically(self, isolated_db):
        """Full buy then sell path commits atomically."""
        p = _make_portfolio()
        h = _make_holding(p.id)

        holdings_repo = HoldingsRepository()
        tx_repo = TransactionsRepository()
        cash_repo = CashRepository()
        now = datetime.now()

        # BUY
        with isolated_db.transaction():
            tx_repo.create(Transaction(
                holding_id=h.id, transaction_type=TransactionType.BUY,
                quantity=Decimal("10"), price=Decimal("50"), transaction_date=now,
            ))
            h.shares = Decimal("10")
            h.cost_basis = Decimal("500")
            holdings_repo.save(h)
            cash_repo.create(CashTransaction(
                portfolio_id=p.id, cash_type=CashTransactionType.BUY,
                amount=Decimal("-500"), transaction_date=now,
            ))

        # SELL
        h = holdings_repo.get_by_id(h.id)  # refresh
        with isolated_db.transaction():
            tx_repo.create(Transaction(
                holding_id=h.id, transaction_type=TransactionType.SELL,
                quantity=Decimal("5"), price=Decimal("60"), transaction_date=now,
            ))
            h.shares = Decimal("5")
            h.cost_basis = Decimal("250")
            holdings_repo.save(h)
            cash_repo.create(CashTransaction(
                portfolio_id=p.id, cash_type=CashTransactionType.SELL,
                amount=Decimal("300"), transaction_date=now,
            ))

        h_after = holdings_repo.get_by_id(h.id)
        assert h_after.shares == Decimal("5")
        assert len(tx_repo.list_by_holding(h.id)) == 2
        assert cash_repo.get_balance(p.id) == Decimal("-200")  # -500 + 300


class TestRebalanceAtomicity:
    def test_rebalance_execute_is_atomic(self, isolated_db, monkeypatch):
        """If one trade in a rebalance fails, all trades are rolled back."""
        p = _make_portfolio()
        h1 = _make_holding(p.id, "IE00B4L5Y983", "IWDA")
        h2 = _make_holding(p.id, "IE00BM67HT60", "XDWT")

        holdings_repo = HoldingsRepository()
        tx_repo = TransactionsRepository()
        h1.shares = Decimal("10")
        h1.cost_basis = Decimal("1000")
        holdings_repo.save(h1)

        call_count = [0]
        original_create = TransactionsRepository.create

        def failing_on_second_call(self, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] >= 2:
                raise RuntimeError("Second trade fails")
            return original_create(self, *args, **kwargs)

        monkeypatch.setattr(TransactionsRepository, "create", failing_on_second_call)

        now = datetime.now()
        with pytest.raises(RuntimeError):
            with isolated_db.transaction():
                # First trade
                tx_repo.create(Transaction(
                    holding_id=h1.id, transaction_type=TransactionType.SELL,
                    quantity=Decimal("5"), price=Decimal("100"), transaction_date=now,
                ))
                h1.shares = Decimal("5")
                h1.cost_basis = Decimal("500")
                holdings_repo.save(h1)
                # Second trade (fails)
                tx_repo.create(Transaction(
                    holding_id=h2.id, transaction_type=TransactionType.BUY,
                    quantity=Decimal("5"), price=Decimal("100"), transaction_date=now,
                ))

        # All changes rolled back
        h1_after = HoldingsRepository().get_by_id(h1.id)
        assert h1_after.shares == Decimal("10")  # original value restored
        assert tx_repo.list_by_holding(h1.id) == []  # no committed transactions
