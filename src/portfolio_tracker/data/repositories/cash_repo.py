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
        if source_id is not None:
            return self._insert_with_source_id(tx, source_id)
        return self._insert(tx)

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
