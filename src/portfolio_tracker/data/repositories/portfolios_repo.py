"""Repository for portfolio CRUD operations."""

from typing import Optional

from ...core.models import Portfolio
from ..query import BaseRepository, RowMapper


class PortfoliosRepository(BaseRepository[Portfolio]):
    _table = "portfolios"
    _mapper = RowMapper(Portfolio)

    def create(self, portfolio: Portfolio) -> Portfolio:
        return self._insert(portfolio)

    def get_by_name(self, name: str) -> Optional[Portfolio]:
        row = self._query().where("name = ?", name).fetch_one(self._db().conn)
        return self._mapper.map(row) if row else None

    def list_all(self) -> list[Portfolio]:
        rows = self._query().order_by("created_at DESC").fetch_all(self._db().conn)
        return self._mapper.map_all(rows)
