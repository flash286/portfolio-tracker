"""Data collection functions for the portfolio dashboard."""

import datetime as _dt
from datetime import datetime
from decimal import Decimal

import typer

from ...core.calculator import PortfolioCalculator
from ...core.config import get_config
from ...core.rebalancer import Rebalancer
from ...data.repositories.cash_repo import CashRepository
from ...data.repositories.holdings_repo import HoldingsRepository
from ...data.repositories.portfolios_repo import PortfoliosRepository
from ...data.repositories.targets_repo import TargetsRepository
from ...data.repositories.transactions_repo import TransactionsRepository


def _decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Not serializable: {type(obj)}")


def _get_cash_balance(portfolio_id: int) -> Decimal:
    """Get cash balance from the database."""
    cash_repo = CashRepository()
    return cash_repo.get_balance(portfolio_id)


def _collect_vp_fsa(portfolio_id: int) -> dict:
    """Read Vorabpauschale FSA usage from cache (populated by pt tax vorabpauschale)."""
    from ...data.database import get_db
    db = get_db()
    rows = db.conn.execute(
        """SELECT year, taxable_vp, fsa_used FROM vorabpauschale_cache
           WHERE portfolio_id = ? ORDER BY year DESC LIMIT 3""",
        (portfolio_id,),
    ).fetchall()
    if not rows:
        return {"vp_entries": []}
    entries = [
        {"year": r["year"], "taxable_vp": Decimal(r["taxable_vp"]), "fsa_used": Decimal(r["fsa_used"])}
        for r in rows
    ]
    return {"vp_entries": entries}


def _collect_realized(portfolio_id: int, holding_by_id: dict, calc) -> dict:
    """Collect current-year realized gains from sell transactions."""
    tx_repo = TransactionsRepository()
    current_year = datetime.now().year
    sells = tx_repo.list_sells_by_portfolio_year(portfolio_id, current_year)

    sell_rows = []
    realized_total_gain = Decimal("0")
    realized_tfs_exempt = Decimal("0")

    for sell in sells:
        h = holding_by_id.get(sell.holding_id)
        tfs_rate = h.teilfreistellung_rate if h else Decimal("0")
        gain = sell.realized_gain if sell.realized_gain is not None else Decimal("0")
        gain_exempt = (gain * tfs_rate).quantize(Decimal("0.01")) if gain > 0 else Decimal("0")
        realized_total_gain += gain
        realized_tfs_exempt += gain_exempt
        sell_rows.append({
            "date": sell.transaction_date.strftime("%Y-%m-%d"),
            "ticker": (h.ticker or h.name or h.isin[:8]) if h else "?",
            "quantity": sell.quantity,
            "price": sell.price,
            "realized_gain": gain,
            "tfs_rate": float(tfs_rate),
        })

    realized_taxable = realized_total_gain - realized_tfs_exempt
    realized_tax_info = calc.calculate_german_tax(max(realized_taxable, Decimal("0")))

    return {
        "year": current_year,
        "sell_count": len(sells),
        "total_gain": realized_total_gain,
        "tfs_exempt": realized_tfs_exempt,
        "taxable": realized_taxable,
        "fsa_used": realized_tax_info.freistellungsauftrag_used,
        "taxable_after_fsa": realized_tax_info.taxable_gain,
        "total_tax": realized_tax_info.total_tax,
        "net_gain": realized_tax_info.net_gain,
        "sells": sell_rows,
    }


def _collect_snapshots(portfolio_id: int) -> list[dict]:
    """Return last 365 days of snapshots for the performance chart."""
    from ...data.repositories.snapshots_repo import SnapshotsRepository
    since = (_dt.date.today() - _dt.timedelta(days=365)).isoformat()
    snaps = SnapshotsRepository().list_by_portfolio(portfolio_id, since_date=since)
    return [
        {
            "date": s.date,
            "holdings_value": s.holdings_value,
            "cash_balance": s.cash_balance,
            "total_value": s.total_value,
        }
        for s in snaps
    ]


def _collect_data(portfolio_id: int) -> dict:
    """Collect all portfolio data into a JSON-serializable dict."""
    portfolios_repo = PortfoliosRepository()
    holdings_repo = HoldingsRepository()
    targets_repo = TargetsRepository()
    tx_repo = TransactionsRepository()

    portfolio = portfolios_repo.get_by_id(portfolio_id)
    if not portfolio:
        raise typer.Exit(1)

    holdings = holdings_repo.list_by_portfolio_with_prices(portfolio_id)

    calc = PortfolioCalculator
    total_value = calc.total_value(holdings)
    total_cost = calc.total_cost_basis(holdings)
    total_pnl = calc.total_unrealized_pnl(holdings)
    pnl_pct = (total_pnl / total_cost * 100).quantize(Decimal("0.01")) if total_cost > 0 else Decimal("0")

    alloc_by_type = calc.allocation_by_type(holdings)
    alloc_by_isin = calc.allocation_by_isin(holdings)

    # Weighted TFS rate across all holdings (by value weight)
    weighted_tfs = Decimal("0")
    if total_value > 0:
        weighted_tfs = sum(
            (h.current_value / total_value * h.teilfreistellung_rate)
            for h in holdings if h.current_price is not None
        )
    tax_info = calc.calculate_german_tax(
        max(total_pnl, Decimal("0")),
        teilfreistellung_rate=weighted_tfs,
    )

    # Targets & rebalancing
    targets = targets_repo.list_by_portfolio(portfolio_id)
    deviations = {}
    if targets:
        reb = Rebalancer(holdings, targets)
        deviations = reb.check_deviation()

    # Transactions summary & cash balance
    all_tx = tx_repo.list_by_portfolio(portfolio_id)
    # Dividends are stored with quantity=0, price=dividend_amount
    total_dividends = sum(
        (t.price for t in all_tx if t.transaction_type.value == "dividend"),
        Decimal("0"),
    )

    # Cash balance from the database
    cash_balance = _get_cash_balance(portfolio_id)

    # Holdings lookup by id (for realized gains section)
    holding_by_id = {h.id: h for h in holdings}

    # Holdings detail
    holdings_data = []
    for h in holdings:
        holdings_data.append({
            "id": h.id,
            "isin": h.isin,
            "name": h.name,
            "ticker": h.ticker,
            "asset_type": h.asset_type.value,
            "tfs_rate": float(h.teilfreistellung_rate),
            "shares": h.shares,
            "cost_basis": h.cost_basis,
            "current_price": h.current_price,
            "current_value": h.current_value if h.current_price else Decimal("0"),
            "pnl": h.unrealized_pnl if h.current_price else Decimal("0"),
            "pnl_pct": h.unrealized_pnl_pct if h.current_price else Decimal("0"),
            "weight": alloc_by_isin.get(h.isin, Decimal("0")),
        })

    # Sort by value desc
    holdings_data.sort(key=lambda x: float(x["current_value"]), reverse=True)

    # Build ISIN → short name lookup (from holdings + well-known tickers)
    isin_names = {
        # Portfolio A targets
        "IE00BK5BQT80": "VWCE",
        "IE00BMC38736": "VVSM",
        "IE00BGV5VN51": "XAIX",
        "IE00BYZK4776": "HEAL",
        "IE00BG47KH54": "VAGF",
    }
    for h in holdings:
        isin_names[h.isin] = h.ticker or h.name or h.isin[:8]

    # Deviation data for chart
    deviation_data = []
    for key, info in deviations.items():
        name = isin_names.get(key, key[:8])
        deviation_data.append({
            "key": key,
            "name": name,
            "current": info["current"],
            "target": info["target"],
            "deviation": info["deviation"],
            "needs_rebalance": info["needs_rebalance"],
        })

    deviation_data.sort(key=lambda x: float(x["target"]), reverse=True)

    return {
        "portfolio_id": portfolio_id,
        "portfolio_name": portfolio.name,
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "holdings_value": total_value,
            "cash_balance": cash_balance,
            "total_value": total_value + cash_balance,
            "total_cost": total_cost,
            "total_pnl": total_pnl,
            "pnl_pct": pnl_pct,
            "total_dividends": total_dividends,
            "holdings_count": len(holdings),
        },
        "tax": {
            "gross_gain": tax_info.gross_gain,
            "tfs_exempt": tax_info.teilfreistellung_exempt,
            "tfs_rate_pct": float(weighted_tfs * 100),
            "freistellungsauftrag_used": tax_info.freistellungsauftrag_used,
            "taxable_gain": tax_info.taxable_gain,
            "abgeltungssteuer": tax_info.abgeltungssteuer,
            "soli": tax_info.solidaritaetszuschlag,
            "total_tax": tax_info.total_tax,
            "net_gain": tax_info.net_gain,
            **_collect_vp_fsa(portfolio_id),
        },
        "freistellungsauftrag": float(get_config().freistellungsauftrag),
        "ai": {
            "provider": get_config().ai_provider,
            "api_key": get_config().ai_api_key,
            "model": get_config().ai_model,
        },
        "allocation_by_type": {k: v for k, v in alloc_by_type.items()},
        "holdings": holdings_data,
        "deviations": deviation_data,
        "realized": _collect_realized(portfolio_id, holding_by_id, calc),
        "snapshots": _collect_snapshots(portfolio_id),
    }
