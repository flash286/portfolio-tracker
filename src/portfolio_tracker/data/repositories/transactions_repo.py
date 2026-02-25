"""Repository for transaction CRUD operations."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from ...core.models import Transaction, TransactionType
from ..database import get_db


class TransactionsRepository:
    def create(
        self,
        holding_id: int,
        transaction_type: TransactionType,
        quantity: Decimal,
        price: Decimal,
        transaction_date: datetime,
        notes: str = "",
        realized_gain: Optional[Decimal] = None,
        source_id: Optional[str] = None,
    ) -> Optional[Transaction]:
        db = get_db()
        total_value = str(quantity * price)
        if source_id is not None:
            cursor = db.conn.execute(
                """INSERT OR IGNORE INTO transactions
                   (holding_id, transaction_type, quantity, price, total_value, realized_gain,
                    transaction_date, notes, source_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    holding_id,
                    transaction_type.value,
                    str(quantity),
                    str(price),
                    total_value,
                    str(realized_gain) if realized_gain is not None else None,
                    transaction_date.isoformat(),
                    notes,
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
                    holding_id,
                    transaction_type.value,
                    str(quantity),
                    str(price),
                    total_value,
                    str(realized_gain) if realized_gain is not None else None,
                    transaction_date.isoformat(),
                    notes,
                ),
            )
        if not db._in_transaction:
            db.conn.commit()
        return self.get_by_id(cursor.lastrowid)

    def get_by_id(self, tx_id: int) -> Optional[Transaction]:
        db = get_db()
        row = db.conn.execute(
            "SELECT * FROM transactions WHERE id = ?", (tx_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_tx(row)

    def list_by_holding(self, holding_id: int) -> list[Transaction]:
        db = get_db()
        rows = db.conn.execute(
            "SELECT * FROM transactions WHERE holding_id = ? ORDER BY transaction_date DESC",
            (holding_id,),
        ).fetchall()
        return [self._row_to_tx(r) for r in rows]

    def list_by_portfolio(self, portfolio_id: int) -> list[Transaction]:
        db = get_db()
        rows = db.conn.execute(
            """SELECT t.* FROM transactions t
               JOIN holdings h ON t.holding_id = h.id
               WHERE h.portfolio_id = ?
               ORDER BY t.transaction_date DESC""",
            (portfolio_id,),
        ).fetchall()
        return [self._row_to_tx(r) for r in rows]

    def list_sells_by_portfolio_year(self, portfolio_id: int, year: int) -> list[Transaction]:
        db = get_db()
        rows = db.conn.execute(
            """SELECT t.* FROM transactions t
               JOIN holdings h ON t.holding_id = h.id
               WHERE h.portfolio_id = ?
                 AND t.transaction_type = 'sell'
                 AND strftime('%Y', t.transaction_date) = ?
               ORDER BY t.transaction_date""",
            (portfolio_id, str(year)),
        ).fetchall()
        return [self._row_to_tx(r) for r in rows]

    def delete(self, tx_id: int) -> bool:
        db = get_db()
        cursor = db.conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        if not db._in_transaction:
            db.conn.commit()
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_tx(row) -> Transaction:
        rg = row["realized_gain"]
        return Transaction(
            id=row["id"],
            holding_id=row["holding_id"],
            transaction_type=TransactionType(row["transaction_type"]),
            quantity=Decimal(str(row["quantity"])),
            price=Decimal(str(row["price"])),
            transaction_date=datetime.fromisoformat(row["transaction_date"]),
            notes=row["notes"] or "",
            realized_gain=Decimal(str(rg)) if rg is not None else None,
            created_at=row["created_at"],
        )
