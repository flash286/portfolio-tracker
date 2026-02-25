"""Repository for holdings CRUD operations."""

import dataclasses
from typing import Optional

from ...core.models import Holding
from ..query import BaseRepository, RowMapper


class HoldingsRepository(BaseRepository[Holding]):
    _table = "holdings"
    _mapper = RowMapper(Holding)
    _insert_skip = frozenset({"id", "created_at", "updated_at", "current_price"})

    def create(self, holding: Holding) -> Holding:
        holding = dataclasses.replace(
            holding, isin=holding.isin.upper(), ticker=holding.ticker.upper()
        )
        return self._insert(holding)

    def get_by_isin(self, portfolio_id: int, isin: str) -> Optional[Holding]:
        row = (
            self._query()
            .where("portfolio_id = ?", portfolio_id)
            .where("isin = ?", isin.upper())
            .fetch_one(self._db().conn)
        )
        return self._mapper.map(row) if row else None

    def list_by_portfolio(self, portfolio_id: int) -> list[Holding]:
        rows = (
            self._query()
            .where("portfolio_id = ?", portfolio_id)
            .order_by("asset_type, isin")
            .fetch_all(self._db().conn)
        )
        return self._mapper.map_all(rows)

    def list_by_portfolio_with_prices(self, portfolio_id: int) -> list[Holding]:
        """Load holdings and attach the latest price to each."""
        from .prices_repo import PricesRepository
        holdings = self.list_by_portfolio(portfolio_id)
        prices_repo = PricesRepository()
        for h in holdings:
            latest = prices_repo.get_latest(h.id)
            if latest:
                h.current_price = latest.price
        return holdings
