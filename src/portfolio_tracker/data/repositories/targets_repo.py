"""Repository for target allocations."""

from decimal import Decimal
from typing import Optional

from ...core.models import TargetAllocation
from ..database import get_db


class TargetsRepository:
    def set_target(
        self, portfolio_id: int, asset_type: str, target_pct: Decimal, threshold: Decimal = Decimal("5.0")
    ) -> TargetAllocation:
        db = get_db()
        db.conn.execute(
            """INSERT INTO target_allocations (portfolio_id, asset_type, target_percentage, rebalance_threshold)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(portfolio_id, asset_type) DO UPDATE SET
                 target_percentage = excluded.target_percentage,
                 rebalance_threshold = excluded.rebalance_threshold,
                 updated_at = CURRENT_TIMESTAMP""",
            (portfolio_id, asset_type, float(target_pct), float(threshold)),
        )
        db.conn.commit()
        return self.get(portfolio_id, asset_type)

    def get(self, portfolio_id: int, asset_type: str) -> Optional[TargetAllocation]:
        db = get_db()
        row = db.conn.execute(
            "SELECT * FROM target_allocations WHERE portfolio_id = ? AND asset_type = ?",
            (portfolio_id, asset_type),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_target(row)

    def list_by_portfolio(self, portfolio_id: int) -> list[TargetAllocation]:
        db = get_db()
        rows = db.conn.execute(
            "SELECT * FROM target_allocations WHERE portfolio_id = ? ORDER BY asset_type",
            (portfolio_id,),
        ).fetchall()
        return [self._row_to_target(r) for r in rows]

    def delete(self, portfolio_id: int, asset_type: str) -> bool:
        db = get_db()
        cursor = db.conn.execute(
            "DELETE FROM target_allocations WHERE portfolio_id = ? AND asset_type = ?",
            (portfolio_id, asset_type),
        )
        db.conn.commit()
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_target(row) -> TargetAllocation:
        return TargetAllocation(
            id=row["id"],
            portfolio_id=row["portfolio_id"],
            asset_type=row["asset_type"],
            target_percentage=Decimal(str(row["target_percentage"])),
            rebalance_threshold=Decimal(str(row["rebalance_threshold"])),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
