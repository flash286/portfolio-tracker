"""Repository for price history."""

from typing import Optional

from ...core.models import PricePoint
from ..query import BaseRepository, RowMapper


class PricesRepository(BaseRepository[PricePoint]):
    _table = "price_history"
    _mapper = RowMapper(PricePoint)

    def store_price(self, price_point: PricePoint) -> PricePoint:
        return self._insert(price_point)

    def get_latest(self, holding_id: int) -> Optional[PricePoint]:
        row = (
            self._query()
            .where("holding_id = ?", holding_id)
            .order_by("fetch_date DESC")
            .limit(1)
            .fetch_one(self._db().conn)
        )
        return self._mapper.map(row) if row else None

    def get_history(self, holding_id: int, limit: int = 90) -> list[PricePoint]:
        rows = (
            self._query()
            .where("holding_id = ?", holding_id)
            .order_by("fetch_date DESC")
            .limit(limit)
            .fetch_all(self._db().conn)
        )
        return self._mapper.map_all(reversed(rows))
