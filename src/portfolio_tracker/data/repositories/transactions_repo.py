"""Repository for transaction CRUD operations."""

from typing import Optional

from ...core.models import Transaction, TransactionType
from ..query import BaseRepository, QueryBuilder, RowMapper


class TransactionsRepository(BaseRepository[Transaction]):
    _table = "transactions"
    _mapper = RowMapper(Transaction)

    def create(
        self, tx: Transaction, source_id: Optional[str] = None
    ) -> Optional[Transaction]:
        db = self._db()
        total_value = str(tx.quantity * tx.price)
        if source_id is not None:
            cursor = db.conn.execute(
                """INSERT OR IGNORE INTO transactions
                   (holding_id, transaction_type, quantity, price, total_value, realized_gain,
                    transaction_date, notes, source_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    tx.holding_id,
                    tx.transaction_type.value,
                    str(tx.quantity),
                    str(tx.price),
                    total_value,
                    str(tx.realized_gain) if tx.realized_gain is not None else None,
                    tx.transaction_date.isoformat(),
                    tx.notes,
                    source_id,
                ),
            )
            if cursor.rowcount == 0:
                return None
        else:
            cursor = db.conn.execute(
                """INSERT INTO transactions
                   (holding_id, transaction_type, quantity, price, total_value, realized_gain,
                    transaction_date, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    tx.holding_id,
                    tx.transaction_type.value,
                    str(tx.quantity),
                    str(tx.price),
                    total_value,
                    str(tx.realized_gain) if tx.realized_gain is not None else None,
                    tx.transaction_date.isoformat(),
                    tx.notes,
                ),
            )
        self._commit(db)
        return self.get_by_id(cursor.lastrowid)

    def list_by_holding(self, holding_id: int) -> list[Transaction]:
        rows = (
            self._query()
            .where("holding_id = ?", holding_id)
            .order_by("transaction_date DESC")
            .fetch_all(self._db().conn)
        )
        return self._mapper.map_all(rows)

    def list_by_portfolio(self, portfolio_id: int) -> list[Transaction]:
        rows = (
            QueryBuilder("transactions t")
            .select("t.*")
            .join("JOIN holdings h ON t.holding_id = h.id")
            .where("h.portfolio_id = ?", portfolio_id)
            .order_by("t.transaction_date DESC")
            .fetch_all(self._db().conn)
        )
        return self._mapper.map_all(rows)

    def list_sells_by_portfolio_year(self, portfolio_id: int, year: int) -> list[Transaction]:
        rows = (
            QueryBuilder("transactions t")
            .select("t.*")
            .join("JOIN holdings h ON t.holding_id = h.id")
            .where("h.portfolio_id = ?", portfolio_id)
            .where("t.transaction_type = ?", TransactionType.SELL.value)
            .where("strftime('%Y', t.transaction_date) = ?", str(year))
            .order_by("t.transaction_date")
            .fetch_all(self._db().conn)
        )
        return self._mapper.map_all(rows)
