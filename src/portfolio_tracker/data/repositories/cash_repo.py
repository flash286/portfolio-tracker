"""Repository for cash transaction CRUD operations."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from ...core.models import CashTransaction, CashTransactionType
from ..database import get_db


class CashRepository:
    def create(
        self,
        portfolio_id: int,
        cash_type: CashTransactionType,
        amount: Decimal,
        transaction_date: datetime,
        description: str = "",
    ) -> CashTransaction:
        db = get_db()
        cursor = db.conn.execute(
            """INSERT INTO cash_transactions
               (portfolio_id, cash_type, amount, transaction_date, description)
               VALUES (?, ?, ?, ?, ?)""",
            (
                portfolio_id,
                cash_type.value,
                str(amount),
                transaction_date.isoformat(),
                description,
            ),
        )
        if not db._in_transaction:
            db.conn.commit()
        return self.get_by_id(cursor.lastrowid)

    def get_by_id(self, tx_id: int) -> Optional[CashTransaction]:
        db = get_db()
        row = db.conn.execute(
            "SELECT * FROM cash_transactions WHERE id = ?", (tx_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_cash_tx(row)

    def list_by_portfolio(self, portfolio_id: int) -> list[CashTransaction]:
        db = get_db()
        rows = db.conn.execute(
            "SELECT * FROM cash_transactions WHERE portfolio_id = ? ORDER BY transaction_date DESC",
            (portfolio_id,),
        ).fetchall()
        return [self._row_to_cash_tx(r) for r in rows]

    def get_balance(self, portfolio_id: int) -> Decimal:
        """Compute current cash balance by summing all cash transactions."""
        db = get_db()
        row = db.conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as balance FROM cash_transactions WHERE portfolio_id = ?",
            (portfolio_id,),
        ).fetchone()
        return Decimal(str(row["balance"]))

    def delete(self, tx_id: int) -> bool:
        db = get_db()
        cursor = db.conn.execute("DELETE FROM cash_transactions WHERE id = ?", (tx_id,))
        if not db._in_transaction:
            db.conn.commit()
        return cursor.rowcount > 0

    def delete_by_portfolio(self, portfolio_id: int) -> int:
        """Delete all cash transactions for a portfolio. Returns count deleted."""
        db = get_db()
        cursor = db.conn.execute(
            "DELETE FROM cash_transactions WHERE portfolio_id = ?", (portfolio_id,)
        )
        if not db._in_transaction:
            db.conn.commit()
        return cursor.rowcount

    @staticmethod
    def _row_to_cash_tx(row) -> CashTransaction:
        return CashTransaction(
            id=row["id"],
            portfolio_id=row["portfolio_id"],
            cash_type=CashTransactionType(row["cash_type"]),
            amount=Decimal(str(row["amount"])),
            transaction_date=datetime.fromisoformat(row["transaction_date"]),
            description=row["description"] or "",
            created_at=row["created_at"],
        )
