"""Repository for portfolio snapshot CRUD operations."""

import datetime
from decimal import Decimal
from typing import Optional

from ...core.models import PortfolioSnapshot
from ..query import BaseRepository, RowMapper


class SnapshotsRepository(BaseRepository[PortfolioSnapshot]):
    _table = "portfolio_snapshots"
    _mapper = RowMapper(PortfolioSnapshot)

    def upsert(self, snapshot: PortfolioSnapshot) -> PortfolioSnapshot:
        """Insert or replace a snapshot for (portfolio_id, date).

        Safe to call multiple times on the same day — updates the existing record.
        """
        db = self._db()
        db.conn.execute(
            """INSERT OR REPLACE INTO portfolio_snapshots
               (portfolio_id, date, holdings_value, cash_balance, total_value,
                cost_basis, unrealized_pnl)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                snapshot.portfolio_id,
                snapshot.date,
                str(snapshot.holdings_value),
                str(snapshot.cash_balance),
                str(snapshot.total_value),
                str(snapshot.cost_basis),
                str(snapshot.unrealized_pnl),
            ),
        )
        self._commit(db)
        row = db.conn.execute(
            "SELECT * FROM portfolio_snapshots WHERE portfolio_id = ? AND date = ?",
            (snapshot.portfolio_id, snapshot.date),
        ).fetchone()
        return self._mapper.map(row)

    def list_by_portfolio(
        self,
        portfolio_id: int,
        since_date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[PortfolioSnapshot]:
        """Return snapshots ordered oldest-first, optionally filtered by start date."""
        q = self._query().where("portfolio_id = ?", portfolio_id)
        if since_date:
            q = q.where("date >= ?", since_date)
        q = q.order_by("date ASC")
        if limit:
            q = q.limit(limit)
        return self._mapper.map_all(q.fetch_all(self._db().conn))

    def get_by_date(self, portfolio_id: int, date: str) -> Optional[PortfolioSnapshot]:
        row = (
            self._query()
            .where("portfolio_id = ?", portfolio_id)
            .where("date = ?", date)
            .fetch_one(self._db().conn)
        )
        return self._mapper.map(row) if row else None

    def get_oldest(self, portfolio_id: int) -> Optional[PortfolioSnapshot]:
        row = (
            self._query()
            .where("portfolio_id = ?", portfolio_id)
            .order_by("date ASC")
            .limit(1)
            .fetch_one(self._db().conn)
        )
        return self._mapper.map(row) if row else None


def backfill_snapshots(
    portfolio_id: int,
    since_date: str,
    interval: str = "1wk",
    console=None,
) -> int:
    """Fetch historical prices from yfinance and create missing snapshots.

    For each weekly (or daily) date between since_date and today that has no
    existing snapshot, reconstructs the portfolio value from transactions +
    historical prices and saves it to portfolio_snapshots.

    Args:
        portfolio_id: Portfolio to backfill.
        since_date:   ISO date "YYYY-MM-DD" — start of the gap to fill.
        interval:     yfinance interval ("1d" or "1wk").
        console:      Optional Rich Console for progress output.

    Returns:
        Number of new snapshots created.
    """
    from ...core.models import TransactionType
    from ...external.price_fetcher import PriceFetcher
    from ..repositories.cash_repo import CashRepository
    from ..repositories.holdings_repo import HoldingsRepository
    from ..repositories.transactions_repo import TransactionsRepository

    holdings_repo = HoldingsRepository()
    tx_repo = TransactionsRepository()
    cash_repo = CashRepository()
    snapshots_repo = SnapshotsRepository()

    holdings = holdings_repo.list_by_portfolio(portfolio_id)
    if not holdings:
        return 0

    # All transactions per holding, sorted chronologically
    holding_txs: dict[int, list] = {
        h.id: sorted(tx_repo.list_by_holding(h.id), key=lambda t: t.transaction_date)
        for h in holdings
    }

    # All cash transactions, sorted chronologically
    all_cash = sorted(cash_repo.list_by_portfolio(portfolio_id), key=lambda c: c.transaction_date)

    # Generate target dates at the requested interval
    step = datetime.timedelta(weeks=1) if interval == "1wk" else datetime.timedelta(days=1)
    since = datetime.date.fromisoformat(since_date)
    today = datetime.date.today()
    target_dates: list[str] = []
    cur = since
    while cur <= today:
        target_dates.append(cur.isoformat())
        cur += step
    if today.isoformat() not in target_dates:
        target_dates.append(today.isoformat())

    # Only fill dates that have no existing snapshot
    existing = {s.date for s in snapshots_repo.list_by_portfolio(portfolio_id, since_date=since_date)}
    missing = [d for d in target_dates if d not in existing]
    if not missing:
        return 0

    fetch_start = min(missing)
    fetch_end = (today + datetime.timedelta(days=1)).isoformat()

    # Fetch price series for each holding that has a ticker
    price_series: dict[int, dict[str, Decimal]] = {}
    for h in holdings:
        if not h.ticker:
            continue
        if console:
            console.print(f"  [dim]Fetching {h.ticker}...[/dim]")
        series = PriceFetcher.fetch_price_series(h.ticker, fetch_start, fetch_end, interval)
        if series:
            price_series[h.id] = series

    # For each missing date, compute values and upsert a snapshot
    _ZERO = Decimal("0")
    _CENT = Decimal("0.01")
    created = 0

    for date_str in sorted(missing):
        # Cash balance: cumulative sum of all cash transactions up to this date
        cash_balance = sum(
            (ct.amount for ct in all_cash if ct.transaction_date.date().isoformat() <= date_str),
            _ZERO,
        )

        holdings_value = _ZERO
        cost_basis = _ZERO

        for h in holdings:
            # Shares held and cost basis on this date
            shares = _ZERO
            buy_cost = _ZERO
            for tx in holding_txs.get(h.id, []):
                if tx.transaction_date.date().isoformat() > date_str:
                    break
                if tx.transaction_type == TransactionType.BUY:
                    shares += tx.quantity
                    buy_cost += tx.quantity * tx.price
                elif tx.transaction_type == TransactionType.SELL:
                    # Reduce cost proportionally to shares sold
                    if shares > _ZERO:
                        buy_cost -= buy_cost * (tx.quantity / shares)
                    shares -= tx.quantity

            shares = max(shares, _ZERO)
            buy_cost = max(buy_cost, _ZERO)
            if shares == _ZERO:
                continue

            # Closest historical price on or before this date
            series = price_series.get(h.id, {})
            available = sorted(d for d in series if d <= date_str)
            if not available:
                continue
            price = series[available[-1]]

            holdings_value += shares * price
            cost_basis += buy_cost

        total = holdings_value + cash_balance
        pnl = holdings_value - cost_basis

        snapshots_repo.upsert(PortfolioSnapshot(
            portfolio_id=portfolio_id,
            date=date_str,
            holdings_value=holdings_value.quantize(_CENT),
            cash_balance=cash_balance.quantize(_CENT),
            total_value=total.quantize(_CENT),
            cost_basis=cost_basis.quantize(_CENT),
            unrealized_pnl=pnl.quantize(_CENT),
        ))
        created += 1

    return created


def take_snapshot_for_portfolio(portfolio_id: int) -> PortfolioSnapshot:
    """Collect current portfolio state and upsert as today's snapshot.

    Safe to call multiple times per day — updates the existing record.
    Returns the saved snapshot.
    """
    from ...core.finance.returns import total_cost_basis, total_value
    from ..repositories.cash_repo import CashRepository
    from ..repositories.holdings_repo import HoldingsRepository

    holdings_repo = HoldingsRepository()
    cash_repo = CashRepository()
    snapshots_repo = SnapshotsRepository()

    holdings = holdings_repo.list_by_portfolio_with_prices(portfolio_id)
    h_value = total_value(holdings)
    cost = total_cost_basis(holdings)
    cash = cash_repo.get_balance(portfolio_id)
    total = h_value + cash
    pnl = h_value - cost

    today = datetime.date.today().isoformat()
    snapshot = PortfolioSnapshot(
        portfolio_id=portfolio_id,
        date=today,
        holdings_value=h_value,
        cash_balance=cash,
        total_value=total,
        cost_basis=cost,
        unrealized_pnl=pnl,
    )
    return snapshots_repo.upsert(snapshot)
