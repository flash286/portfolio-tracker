"""Snapshot commands — take and inspect portfolio snapshots."""

import typer
from rich.console import Console
from rich.table import Table

from ...data.repositories.portfolios_repo import PortfoliosRepository
from ...data.repositories.snapshots_repo import backfill_snapshots, take_snapshot_for_portfolio

app = typer.Typer(help="Portfolio value snapshots")
console = Console()
portfolios_repo = PortfoliosRepository()


@app.command("take")
def take(portfolio_id: int = typer.Argument(..., help="Portfolio ID")):
    """Record today's portfolio value as a snapshot (safe to run multiple times)."""
    p = portfolios_repo.get_by_id(portfolio_id)
    if not p:
        console.print(f"[red]Portfolio {portfolio_id} not found[/red]")
        raise typer.Exit(1)

    snap = take_snapshot_for_portfolio(portfolio_id)

    if snap.holdings_value == 0 and snap.total_value > 0:
        console.print("[yellow]Warning: holdings value is 0 — run 'pt prices fetch' first[/yellow]")

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Label", style="dim")
    table.add_column("Value", justify="right")
    table.add_row("Date", snap.date)
    table.add_row("Holdings Value", f"€{snap.holdings_value:,.2f}")
    table.add_row("Cash Balance", f"€{snap.cash_balance:,.2f}")
    table.add_row("[bold]Total Value[/bold]", f"[bold]€{snap.total_value:,.2f}[/bold]")
    table.add_row("Cost Basis", f"€{snap.cost_basis:,.2f}")
    color = "green" if snap.unrealized_pnl >= 0 else "red"
    table.add_row("Unrealized P&L", f"[{color}]€{snap.unrealized_pnl:+,.2f}[/{color}]")

    console.print(f"\n[green]Snapshot recorded — '{p.name}' on {snap.date}[/green]\n")
    console.print(table)
    console.print()


@app.command("backfill")
def backfill(
    portfolio_id: int = typer.Argument(..., help="Portfolio ID"),
    since: str = typer.Option("", "--since", "-s", help="Start date YYYY-MM-DD (default: first transaction)"),
    interval: str = typer.Option("1wk", "--interval", "-i", help="Price interval: 1d or 1wk"),
):
    """Fetch historical prices and fill missing snapshots from yfinance."""
    import datetime

    p = portfolios_repo.get_by_id(portfolio_id)
    if not p:
        console.print(f"[red]Portfolio {portfolio_id} not found[/red]")
        raise typer.Exit(1)

    if interval not in ("1d", "1wk"):
        console.print("[red]interval must be '1d' or '1wk'[/red]")
        raise typer.Exit(1)

    since_date = since or None
    if since_date is None:
        from ...data.database import get_db
        row = get_db().conn.execute(
            "SELECT MIN(date(transaction_date)) AS first_tx FROM transactions "
            "JOIN holdings ON holdings.id = transactions.holding_id "
            "WHERE holdings.portfolio_id = ?",
            (portfolio_id,),
        ).fetchone()
        since_date = row["first_tx"] if row and row["first_tx"] else datetime.date.today().isoformat()

    console.print(f"[cyan]Backfilling '{p.name}' from {since_date} ({interval})…[/cyan]\n")
    n = backfill_snapshots(portfolio_id, since_date, interval=interval, console=console)
    console.print(f"\n[green]Done — created {n} historical snapshot(s)[/green]")
