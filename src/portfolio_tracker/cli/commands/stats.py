"""Statistics commands."""

from decimal import Decimal

import typer
from rich.console import Console
from rich.table import Table

from ...core.calculator import PortfolioCalculator
from ...data.repositories.cash_repo import CashRepository
from ...data.repositories.holdings_repo import HoldingsRepository
from ...data.repositories.portfolios_repo import PortfoliosRepository

app = typer.Typer(help="Portfolio statistics")
console = Console()
cash_repo = CashRepository()
holdings_repo = HoldingsRepository()
portfolios_repo = PortfoliosRepository()


@app.command("summary")
def summary(portfolio_id: int = typer.Argument(..., help="Portfolio ID")):
    """Show portfolio summary: value, P&L, allocation."""
    p = portfolios_repo.get_by_id(portfolio_id)
    if not p:
        console.print(f"[red]Portfolio {portfolio_id} not found[/red]")
        raise typer.Exit(1)

    holdings = holdings_repo.list_by_portfolio_with_prices(portfolio_id)
    if not holdings:
        console.print("[yellow]No holdings. Add some first.[/yellow]")
        return

    total_cost = PortfolioCalculator.total_cost_basis(holdings)
    total_val = PortfolioCalculator.total_value(holdings)
    pnl = PortfolioCalculator.total_unrealized_pnl(holdings)
    pnl_pct = (pnl / total_cost * 100).quantize(Decimal("0.01")) if total_cost > 0 else Decimal("0")

    # Weighted Teilfreistellung rate (weighted by current value)
    weighted_tfs = Decimal("0")
    if total_val > 0:
        weighted_tfs = sum(
            (h.current_value / total_val * h.teilfreistellung_rate)
            for h in holdings
            if h.current_price is not None
        )

    # Tax estimate (no Kirchensteuer), with Teilfreistellung
    tax_info = PortfolioCalculator.calculate_german_tax(
        max(pnl, Decimal("0")),
        teilfreistellung_rate=weighted_tfs,
    )

    console.print(f"\n[bold]Portfolio: {p.name}[/bold]\n")

    # Summary table
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Label", style="dim")
    table.add_column("Value", justify="right")

    cash_balance = cash_repo.get_balance(portfolio_id)
    total_portfolio = total_val + cash_balance

    table.add_row("Total Cost Basis", f"€{total_cost:,.2f}")
    table.add_row("Holdings Value", f"€{total_val:,.2f}")
    table.add_row("Cash Balance", f"€{cash_balance:,.2f}")
    table.add_row("[bold]Portfolio Value[/bold]", f"[bold]€{total_portfolio:,.2f}[/bold]")

    color = "green" if pnl >= 0 else "red"
    table.add_row("Unrealized P&L", f"[{color}]€{pnl:,.2f} ({pnl_pct:+.2f}%)[/{color}]")

    if pnl > 0:
        table.add_row("", "")
        table.add_row("[dim]— Steuerberechnung (DE) —[/dim]", "")
        if tax_info.teilfreistellung_exempt > 0:
            tfs_pct = f"{weighted_tfs * 100:.0f}%"
            table.add_row(f"Teilfreistellung ({tfs_pct})", f"[dim]−€{tax_info.teilfreistellung_exempt:,.2f}[/dim]")
        table.add_row("Freistellungsauftrag genutzt", f"€{tax_info.freistellungsauftrag_used:,.2f}")
        table.add_row("Steuerpflichtiger Gewinn", f"€{tax_info.taxable_gain:,.2f}")
        table.add_row("Abgeltungssteuer (25%)", f"€{tax_info.abgeltungssteuer:,.2f}")
        table.add_row("Solidaritätszuschlag (5.5%)", f"€{tax_info.solidaritaetszuschlag:,.2f}")
        table.add_row("Steuer gesamt", f"[red]€{tax_info.total_tax:,.2f}[/red]")
        table.add_row("Nettogewinn", f"[green]€{tax_info.net_gain:,.2f}[/green]")

    console.print(table)
    console.print()


@app.command("allocation")
def allocation(portfolio_id: int = typer.Argument(..., help="Portfolio ID")):
    """Show allocation breakdown by asset type and ISIN."""
    p = portfolios_repo.get_by_id(portfolio_id)
    if not p:
        console.print(f"[red]Portfolio {portfolio_id} not found[/red]")
        raise typer.Exit(1)

    holdings = holdings_repo.list_by_portfolio_with_prices(portfolio_id)
    if not holdings:
        console.print("[yellow]No holdings.[/yellow]")
        return

    total_val = PortfolioCalculator.total_value(holdings)

    # By type
    console.print(f"\n[bold]Allocation by Type — {p.name}[/bold]\n")
    type_alloc = PortfolioCalculator.allocation_by_type(holdings)

    type_table = Table()
    type_table.add_column("Asset Type", style="bold")
    type_table.add_column("Allocation %", justify="right")
    type_table.add_column("Value (€)", justify="right")

    for atype, pct in sorted(type_alloc.items()):
        val = total_val * pct / 100
        type_table.add_row(atype, f"{pct:.2f}%", f"€{val:,.2f}")

    type_table.add_row("[bold]TOTAL[/bold]", "[bold]100.00%[/bold]", f"[bold]€{total_val:,.2f}[/bold]")
    console.print(type_table)

    # By ISIN
    console.print("\n[bold]Allocation by Holding[/bold]\n")
    isin_alloc = PortfolioCalculator.allocation_by_isin(holdings)

    sym_table = Table()
    sym_table.add_column("ISIN", style="bold")
    sym_table.add_column("Name")
    sym_table.add_column("Type")
    sym_table.add_column("Shares", justify="right")
    sym_table.add_column("Price (€)", justify="right")
    sym_table.add_column("Value (€)", justify="right")
    sym_table.add_column("Alloc %", justify="right")

    for h in sorted(holdings, key=lambda x: x.current_value, reverse=True):
        if h.current_price is None:
            continue
        pct = isin_alloc.get(h.isin, Decimal("0"))
        sym_table.add_row(
            h.isin,
            h.name or h.ticker or "—",
            h.asset_type.value,
            f"{h.shares:,.4f}",
            f"{h.current_price:,.4f}",
            f"{h.current_value:,.2f}",
            f"{pct:.2f}%",
        )

    console.print(sym_table)
    console.print()


@app.command("performance")
def performance(
    portfolio_id: int = typer.Argument(..., help="Portfolio ID"),
    period: str = typer.Option("1y", "--period", "-p", help="Period: 1m|3m|6m|1y|2y|all"),
):
    """Show portfolio value history and time-weighted return (requires snapshots)."""
    import datetime

    from ...core.finance.returns import calculate_twr
    from ...data.database import get_db
    from ...data.repositories.snapshots_repo import SnapshotsRepository

    _DAYS = {"1m": 30, "3m": 90, "6m": 180, "1y": 365, "2y": 730, "all": None}
    if period not in _DAYS:
        console.print(f"[red]Unknown period '{period}'. Use: 1m|3m|6m|1y|2y|all[/red]")
        raise typer.Exit(1)

    p = portfolios_repo.get_by_id(portfolio_id)
    if not p:
        console.print(f"[red]Portfolio {portfolio_id} not found[/red]")
        raise typer.Exit(1)

    days = _DAYS[period]
    today = datetime.date.today()
    since_date: str | None = None
    if days is not None:
        since_date = (today - datetime.timedelta(days=days)).isoformat()

    # Use daily prices for short periods, weekly for longer ones
    interval = "1d" if days is not None and days <= 90 else "1wk"
    gap_threshold = datetime.timedelta(weeks=2) if interval == "1wk" else datetime.timedelta(days=3)

    snaps_repo = SnapshotsRepository()
    snaps = snaps_repo.list_by_portfolio(portfolio_id, since_date=since_date)

    # Lazy-load: backfill from yfinance if the period start has no coverage
    period_start = datetime.date.fromisoformat(since_date) if since_date else None
    needs_backfill = len(snaps) < 2 or (
        period_start is not None
        and snaps
        and datetime.date.fromisoformat(snaps[0].date) > period_start + gap_threshold
    )

    if needs_backfill:
        from ...data.repositories.snapshots_repo import backfill_snapshots

        backfill_from = since_date
        if backfill_from is None:
            # period=all: backfill from the first transaction date
            row = get_db().conn.execute(
                "SELECT MIN(date(transaction_date)) AS first_tx FROM transactions "
                "JOIN holdings ON holdings.id = transactions.holding_id "
                "WHERE holdings.portfolio_id = ?",
                (portfolio_id,),
            ).fetchone()
            backfill_from = row["first_tx"] if row and row["first_tx"] else today.isoformat()

        console.print(f"[cyan]Fetching historical prices ({period}, {interval})…[/cyan]")
        n = backfill_snapshots(portfolio_id, backfill_from, interval=interval, console=console)
        console.print(f"[green]Created {n} historical snapshot(s)[/green]\n")
        snaps = snaps_repo.list_by_portfolio(portfolio_id, since_date=since_date)

    if len(snaps) < 2:
        console.print("[yellow]Not enough data — run 'pt prices fetch' first, then retry.[/yellow]")
        return

    # Build TWR sub-periods using cash flows between consecutive snapshots
    db = get_db()
    twr_periods = []
    for i in range(1, len(snaps)):
        s0, s1 = snaps[i - 1], snaps[i]
        row = db.conn.execute(
            """SELECT COALESCE(SUM(CAST(amount AS REAL)), 0) AS net
               FROM cash_transactions
               WHERE portfolio_id = ?
                 AND cash_type IN ('top_up', 'withdrawal')
                 AND date(transaction_date) > ?
                 AND date(transaction_date) <= ?""",
            (portfolio_id, s0.date, s1.date),
        ).fetchone()
        net_flow = Decimal(str(row["net"]))
        twr_periods.append((s0.total_value, s1.total_value, net_flow))

    twr = calculate_twr(twr_periods)
    first, last = snaps[0], snaps[-1]
    simple_return = (
        (last.total_value / first.total_value - Decimal("1")) if first.total_value > 0 else Decimal("0")
    )

    console.print(f"\n[bold]Performance History — {p.name}[/bold]")
    console.print(f"[dim]{first.date} → {last.date}  ({len(snaps)} snapshots)[/dim]\n")

    tbl = Table()
    tbl.add_column("Date")
    tbl.add_column("Holdings €", justify="right")
    tbl.add_column("Cash €", justify="right")
    tbl.add_column("Total €", justify="right")
    tbl.add_column("P&L €", justify="right")
    tbl.add_column("P&L %", justify="right")

    for s in snaps:
        pnl_pct = (s.unrealized_pnl / s.cost_basis * 100) if s.cost_basis > 0 else Decimal("0")
        color = "green" if s.unrealized_pnl >= 0 else "red"
        tbl.add_row(
            s.date,
            f"{s.holdings_value:,.2f}",
            f"{s.cash_balance:,.2f}",
            f"[bold]{s.total_value:,.2f}[/bold]",
            f"[{color}]{s.unrealized_pnl:+,.2f}[/{color}]",
            f"[{color}]{pnl_pct:+.2f}%[/{color}]",
        )

    console.print(tbl)

    sr_color = "green" if simple_return >= 0 else "red"
    twr_color = "green" if twr >= 0 else "red"
    console.print(
        f"\n  Simple Return : [{sr_color}]{simple_return * 100:+.2f}%[/{sr_color}]"
        f"    TWR : [{twr_color}]{twr * 100:+.2f}%[/{twr_color}]\n"
    )
