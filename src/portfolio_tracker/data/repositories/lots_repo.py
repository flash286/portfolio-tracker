"""Repository for FIFO tax lots."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from ...core.models import TaxLot
from ..database import get_db


class LotsRepository:
    def create(
        self,
        holding_id: int,
        acquired_date: datetime,
        quantity: Decimal,
        cost_per_unit: Decimal,
        buy_transaction_id: Optional[int] = None,
    ) -> TaxLot:
        db = get_db()
        cursor = db.conn.execute(
            """INSERT INTO tax_lots
               (holding_id, buy_transaction_id, acquired_date, quantity, cost_per_unit, quantity_remaining)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                holding_id,
                buy_transaction_id,
                acquired_date.isoformat(),
                str(quantity),
                str(cost_per_unit),
                str(quantity),  # initially fully available
            ),
        )
        if not db._in_transaction:
            db.conn.commit()
        return self.get_by_id(cursor.lastrowid)

    def get_by_id(self, lot_id: int) -> Optional[TaxLot]:
        db = get_db()
        row = db.conn.execute(
            "SELECT * FROM tax_lots WHERE id = ?", (lot_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_lot(row)

    def get_open_lots_fifo(self, holding_id: int) -> list[TaxLot]:
        """Return lots with remaining quantity > 0, ordered FIFO (oldest first)."""
        db = get_db()
        rows = db.conn.execute(
            """SELECT * FROM tax_lots
               WHERE holding_id = ?
               ORDER BY acquired_date ASC, id ASC""",
            (holding_id,),
        ).fetchall()
        # Filter in Python to avoid TEXT > 0 SQL comparison issues
        return [self._row_to_lot(r) for r in rows if Decimal(r["quantity_remaining"]) > 0]

    def list_by_holding(self, holding_id: int) -> list[TaxLot]:
        """All lots for a holding, including fully consumed ones."""
        db = get_db()
        rows = db.conn.execute(
            "SELECT * FROM tax_lots WHERE holding_id = ? ORDER BY acquired_date ASC, id ASC",
            (holding_id,),
        ).fetchall()
        return [self._row_to_lot(r) for r in rows]

    def reduce_lot(self, lot_id: int, qty_consumed: Decimal):
        """Reduce quantity_remaining of a lot by qty_consumed."""
        db = get_db()
        row = db.conn.execute(
            "SELECT quantity_remaining FROM tax_lots WHERE id = ?", (lot_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Tax lot {lot_id} not found")
        new_qty = Decimal(row["quantity_remaining"]) - qty_consumed
        db.conn.execute(
            "UPDATE tax_lots SET quantity_remaining = ? WHERE id = ?",
            (str(new_qty), lot_id),
        )
        if not db._in_transaction:
            db.conn.commit()

    def get_fifo_cost_basis(self, holding_id: int) -> Decimal:
        """Sum of (quantity_remaining × cost_per_unit) for all open lots."""
        db = get_db()
        rows = db.conn.execute(
            "SELECT quantity_remaining, cost_per_unit FROM tax_lots WHERE holding_id = ?",
            (holding_id,),
        ).fetchall()
        total = Decimal("0")
        for row in rows:
            qty_remaining = Decimal(row["quantity_remaining"])
            if qty_remaining > 0:
                total += qty_remaining * Decimal(row["cost_per_unit"])
        return total

    @staticmethod
    def _row_to_lot(row) -> TaxLot:
        return TaxLot(
            id=row["id"],
            holding_id=row["holding_id"],
            buy_transaction_id=row["buy_transaction_id"],
            acquired_date=datetime.fromisoformat(row["acquired_date"]),
            quantity=Decimal(row["quantity"]),
            cost_per_unit=Decimal(row["cost_per_unit"]),
            quantity_remaining=Decimal(row["quantity_remaining"]),
            created_at=row["created_at"],
        )
