"""Repository for FIFO tax lots."""

import dataclasses
from decimal import Decimal

from ...core.models import TaxLot
from ..query import BaseRepository, RowMapper


class LotsRepository(BaseRepository[TaxLot]):
    _table = "tax_lots"
    _mapper = RowMapper(TaxLot)

    def create(self, lot: TaxLot) -> TaxLot:
        # Business rule: new lot always starts fully available
        lot = dataclasses.replace(lot, quantity_remaining=lot.quantity)
        return self._insert(lot)

    def get_open_lots_fifo(self, holding_id: int) -> list[TaxLot]:
        """Return lots with remaining quantity > 0, ordered FIFO (oldest first)."""
        rows = (
            self._query()
            .where("holding_id = ?", holding_id)
            .order_by("acquired_date ASC, id ASC")
            .fetch_all(self._db().conn)
        )
        # Filter in Python to avoid TEXT > 0 SQL comparison issues
        return [self._mapper.map(r) for r in rows if Decimal(r["quantity_remaining"]) > 0]

    def list_by_holding(self, holding_id: int) -> list[TaxLot]:
        """All lots for a holding, including fully consumed ones."""
        rows = (
            self._query()
            .where("holding_id = ?", holding_id)
            .order_by("acquired_date ASC, id ASC")
            .fetch_all(self._db().conn)
        )
        return self._mapper.map_all(rows)

    def reduce_lot(self, lot_id: int, qty_consumed: Decimal):
        """Reduce quantity_remaining of a lot by qty_consumed."""
        db = self._db()
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
        self._commit(db)

    def get_fifo_cost_basis(self, holding_id: int) -> Decimal:
        """Sum of (quantity_remaining × cost_per_unit) for all open lots."""
        db = self._db()
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
