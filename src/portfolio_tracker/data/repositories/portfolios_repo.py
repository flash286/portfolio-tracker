"""Repository for portfolio CRUD operations."""

from datetime import datetime
from typing import Optional

from ...core.models import Portfolio
from ..database import get_db


class PortfoliosRepository:
    def create(self, name: str, description: str = "") -> Portfolio:
        db = get_db()
        cursor = db.conn.execute(
            "INSERT INTO portfolios (name, description) VALUES (?, ?)",
            (name, description),
        )
        if not db._in_transaction:
            db.conn.commit()
        return self.get_by_id(cursor.lastrowid)

    def get_by_id(self, portfolio_id: int) -> Optional[Portfolio]:
        db = get_db()
        row = db.conn.execute(
            "SELECT * FROM portfolios WHERE id = ?", (portfolio_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_portfolio(row)

    def get_by_name(self, name: str) -> Optional[Portfolio]:
        db = get_db()
        row = db.conn.execute(
            "SELECT * FROM portfolios WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_portfolio(row)

    def list_all(self) -> list[Portfolio]:
        db = get_db()
        rows = db.conn.execute(
            "SELECT * FROM portfolios ORDER BY created_at DESC"
        ).fetchall()
        return [self._row_to_portfolio(r) for r in rows]

    def delete(self, portfolio_id: int) -> bool:
        db = get_db()
        cursor = db.conn.execute(
            "DELETE FROM portfolios WHERE id = ?", (portfolio_id,)
        )
        if not db._in_transaction:
            db.conn.commit()
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_portfolio(row) -> Portfolio:
        return Portfolio(
            id=row["id"],
            name=row["name"],
            description=row["description"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
