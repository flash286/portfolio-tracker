"""Repository for price history."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from ...core.models import PricePoint
from ..database import get_db


class PricesRepository:
    def store_price(self, holding_id: int, price: Decimal, source: str = "") -> PricePoint:
        db = get_db()
        now = datetime.now()
        cursor = db.conn.execute(
            """INSERT INTO price_history (holding_id, price, fetch_date, source)
               VALUES (?, ?, ?, ?)""",
            (holding_id, str(price), now.isoformat(), source),
        )
        if not db._in_transaction:
            db.conn.commit()
        return PricePoint(
            id=cursor.lastrowid,
            holding_id=holding_id,
            price=price,
            fetch_date=now,
            source=source,
        )

    def get_latest(self, holding_id: int) -> Optional[PricePoint]:
        db = get_db()
        row = db.conn.execute(
            "SELECT * FROM price_history WHERE holding_id = ? ORDER BY fetch_date DESC LIMIT 1",
            (holding_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_price(row)

    def get_history(self, holding_id: int, limit: int = 90) -> list[PricePoint]:
        db = get_db()
        rows = db.conn.execute(
            "SELECT * FROM price_history WHERE holding_id = ? ORDER BY fetch_date DESC LIMIT ?",
            (holding_id, limit),
        ).fetchall()
        return [self._row_to_price(r) for r in reversed(rows)]

    @staticmethod
    def _row_to_price(row) -> PricePoint:
        return PricePoint(
            id=row["id"],
            holding_id=row["holding_id"],
            price=Decimal(str(row["price"])),
            fetch_date=datetime.fromisoformat(row["fetch_date"]),
            source=row["source"] or "",
        )
