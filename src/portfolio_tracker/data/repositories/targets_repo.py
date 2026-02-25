"""Repository for target allocations."""

from typing import Optional

from ...core.models import TargetAllocation
from ..query import BaseRepository, RowMapper


class TargetsRepository(BaseRepository[TargetAllocation]):
    _table = "target_allocations"
    _mapper = RowMapper(TargetAllocation)

    def set_target(self, target: TargetAllocation) -> TargetAllocation:
        db = self._db()
        db.conn.execute(
            """INSERT INTO target_allocations (portfolio_id, asset_type, target_percentage, rebalance_threshold)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(portfolio_id, asset_type) DO UPDATE SET
                 target_percentage = excluded.target_percentage,
                 rebalance_threshold = excluded.rebalance_threshold,
                 updated_at = CURRENT_TIMESTAMP""",
            (target.portfolio_id, target.asset_type,
             str(target.target_percentage), str(target.rebalance_threshold)),
        )
        self._commit(db)
        return self.get(target.portfolio_id, target.asset_type)

    def get(self, portfolio_id: int, asset_type: str) -> Optional[TargetAllocation]:
        row = (
            self._query()
            .where("portfolio_id = ?", portfolio_id)
            .where("asset_type = ?", asset_type)
            .fetch_one(self._db().conn)
        )
        return self._mapper.map(row) if row else None

    def list_by_portfolio(self, portfolio_id: int) -> list[TargetAllocation]:
        rows = (
            self._query()
            .where("portfolio_id = ?", portfolio_id)
            .order_by("asset_type")
            .fetch_all(self._db().conn)
        )
        return self._mapper.map_all(rows)

    def delete(self, portfolio_id: int, asset_type: str) -> bool:
        db = self._db()
        cursor = db.conn.execute(
            "DELETE FROM target_allocations WHERE portfolio_id = ? AND asset_type = ?",
            (portfolio_id, asset_type),
        )
        self._commit(db)
        return cursor.rowcount > 0
