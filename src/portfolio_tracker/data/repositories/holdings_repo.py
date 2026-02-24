"""Repository for holdings CRUD operations."""

from decimal import Decimal
from typing import Optional

from ...core.models import AssetType, Holding
from ..database import get_db


class HoldingsRepository:
    def create(
        self,
        portfolio_id: int,
        isin: str,
        asset_type: AssetType,
        name: str = "",
        ticker: str = "",
        teilfreistellung_rate: Decimal = Decimal("0"),
    ) -> Holding:
        db = get_db()
        cursor = db.conn.execute(
            """INSERT INTO holdings
               (portfolio_id, isin, asset_type, name, ticker, shares, cost_basis, teilfreistellung_rate)
               VALUES (?, ?, ?, ?, ?, '0', '0', ?)""",
            (portfolio_id, isin.upper(), asset_type.value, name, ticker.upper(),
             str(teilfreistellung_rate)),
        )
        if not db._in_transaction:
            db.conn.commit()
        return self.get_by_id(cursor.lastrowid)

    def get_by_id(self, holding_id: int) -> Optional[Holding]:
        db = get_db()
        row = db.conn.execute(
            "SELECT * FROM holdings WHERE id = ?", (holding_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_holding(row)

    def get_by_isin(self, portfolio_id: int, isin: str) -> Optional[Holding]:
        db = get_db()
        row = db.conn.execute(
            "SELECT * FROM holdings WHERE portfolio_id = ? AND isin = ?",
            (portfolio_id, isin.upper()),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_holding(row)

    def list_by_portfolio(self, portfolio_id: int) -> list[Holding]:
        db = get_db()
        rows = db.conn.execute(
            "SELECT * FROM holdings WHERE portfolio_id = ? ORDER BY asset_type, isin",
            (portfolio_id,),
        ).fetchall()
        return [self._row_to_holding(r) for r in rows]

    def update_shares_and_cost(self, holding_id: int, shares: Decimal, cost_basis: Decimal):
        db = get_db()
        db.conn.execute(
            "UPDATE holdings SET shares = ?, cost_basis = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (str(shares), str(cost_basis), holding_id),
        )
        if not db._in_transaction:
            db.conn.commit()

    def update_teilfreistellung_rate(self, holding_id: int, rate: Decimal):
        db = get_db()
        db.conn.execute(
            "UPDATE holdings SET teilfreistellung_rate = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (str(rate), holding_id),
        )
        if not db._in_transaction:
            db.conn.commit()

    def delete(self, holding_id: int) -> bool:
        db = get_db()
        cursor = db.conn.execute("DELETE FROM holdings WHERE id = ?", (holding_id,))
        if not db._in_transaction:
            db.conn.commit()
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_holding(row) -> Holding:
        return Holding(
            id=row["id"],
            portfolio_id=row["portfolio_id"],
            isin=row["isin"],
            asset_type=AssetType(row["asset_type"]),
            name=row["name"] or "",
            ticker=row["ticker"] or "",
            shares=Decimal(str(row["shares"])),
            cost_basis=Decimal(str(row["cost_basis"])),
            teilfreistellung_rate=Decimal(str(row["teilfreistellung_rate"])),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
