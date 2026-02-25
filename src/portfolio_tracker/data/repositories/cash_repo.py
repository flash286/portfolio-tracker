"""Repository for cash transaction CRUD operations."""

from decimal import Decimal
from typing import Optional

from ...core.models import CashTransaction
from ..query import BaseRepository, RowMapper


class CashRepository(BaseRepository[CashTransaction]):
    _table = "cash_transactions"
    _mapper = RowMapper(CashTransaction)

    def create(
        self, tx: CashTransaction, source_id: Optional[str] = None
    ) -> Optional[CashTransaction]:
        db = self._db()
        if source_id is not None:
            cursor = db.conn.execute(
                """INSERT OR IGNORE INTO cash_transactions
                   (portfolio_id, cash_type, amount, transaction_date, description, source_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    tx.portfolio_id,
                    tx.cash_type.value,
                    str(tx.amount),
                    tx.transaction_date.isoformat(),
                    tx.description,
                    source_id,
                ),
            )
            if cursor.rowcount == 0:
                return None
        else:
            cursor = db.conn.execute(
                """INSERT INTO cash_transactions
                   (portfolio_id, cash_type, amount, transaction_date, description)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    tx.portfolio_id,
                    tx.cash_type.value,
                    str(tx.amount),
                    tx.transaction_date.isoformat(),
                    tx.description,
                ),
            )
        self._commit(db)
        return self.get_by_id(cursor.lastrowid)

    def list_by_portfolio(self, portfolio_id: int) -> list[CashTransaction]:
        rows = (
            self._query()
            .where("portfolio_id = ?", portfolio_id)
            .order_by("transaction_date DESC")
            .fetch_all(self._db().conn)
        )
        return self._mapper.map_all(rows)

    def get_balance(self, portfolio_id: int) -> Decimal:
        """Compute current cash balance by summing all cash transactions."""
        db = self._db()
        row = db.conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as balance FROM cash_transactions WHERE portfolio_id = ?",
            (portfolio_id,),
        ).fetchone()
        return Decimal(str(row["balance"]))

    def delete_by_portfolio(self, portfolio_id: int) -> int:
        """Delete all cash transactions for a portfolio. Returns count deleted."""
        db = self._db()
        cursor = db.conn.execute(
            "DELETE FROM cash_transactions WHERE portfolio_id = ?", (portfolio_id,)
        )
        self._commit(db)
        return cursor.rowcount
