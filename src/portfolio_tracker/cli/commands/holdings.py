"""Holdings management commands."""

from decimal import Decimal, InvalidOperation

import typer
from rich.console import Console
from rich.table import Table

from ...core.models import AssetType, Holding
from ...data.repositories.cash_repo import CashRepository
from ...data.repositories.holdings_repo import HoldingsRepository
from ...data.repositories.portfolios_repo import PortfoliosRepository

app = typer.Typer(help="Manage holdings")
console = Console()
cash_repo = CashRepository()
repo = HoldingsRepository()
portfolios_repo = PortfoliosRepository()

ASSET_TYPES = [t.value for t in AssetType]


def _display_name(h) -> str:
    """Return best available display name for a holding."""
    if h.name:
        return f"{h.name} ({h.isin})"
    if h.ticker:
        return f"{h.ticker} ({h.isin})"
    return h.isin


@app.command("add")
def add(
    portfolio_id: int = typer.Argument(..., help="Portfolio ID"),
    isin: str = typer.Argument(..., help="ISIN (e.g. US0378331005, DE000A0D8Q49)"),
    asset_type: str = typer.Argument(..., help=f"Asset type: {', '.join(ASSET_TYPES)}"),
    name: str = typer.Option("", "--name", "-n", help="Human-readable name (e.g. 'Apple Inc.')"),
    ticker: str = typer.Option("", "--ticker", "-t", help="Yahoo Finance ticker for price fetching (e.g. 'AAPL')"),
    tfs_rate: str = typer.Option("0", "--tfs-rate", help="Teilfreistellung rate (0.3 for equity ETFs, 0 for others)"),
):
    """Add a new holding to a portfolio."""
    p = portfolios_repo.get_by_id(portfolio_id)
    if not p:
        console.print(f"[red]Portfolio {portfolio_id} not found[/red]")
        raise typer.Exit(1)

    asset_type = asset_type.lower()
    if asset_type not in ASSET_TYPES:
        console.print(f"[red]Invalid asset type. Choose from: {', '.join(ASSET_TYPES)}[/red]")
        raise typer.Exit(1)

    try:
        tfs_decimal = Decimal(tfs_rate)
        if tfs_decimal < 0 or tfs_decimal > 1:
            raise InvalidOperation
    except InvalidOperation:
        console.print("[red]Invalid --tfs-rate. Must be between 0 and 1 (e.g. 0.3 for equity ETFs)[/red]")
        raise typer.Exit(1)

    existing = repo.get_by_isin(portfolio_id, isin)
    if existing:
        console.print(f"[yellow]{isin} already exists in this portfolio (ID: {existing.id})[/yellow]")
        return

    h = repo.create(Holding(
        portfolio_id=portfolio_id, isin=isin, asset_type=AssetType(asset_type),
        name=name, ticker=ticker, teilfreistellung_rate=tfs_decimal,
    ))
    tfs_info = f"  TFS: {tfs_decimal * 100:.0f}%" if tfs_decimal > 0 else ""
    console.print(f"[green]Added {_display_name(h)} ({h.asset_type.value}) to '{p.name}' (Holding ID: {h.id})[/green]{tfs_info}")  # noqa: E501


@app.command("list")
def list_holdings(portfolio_id: int = typer.Argument(..., help="Portfolio ID")):
    """List all holdings in a portfolio."""
    p = portfolios_repo.get_by_id(portfolio_id)
    if not p:
        console.print(f"[red]Portfolio {portfolio_id} not found[/red]")
        raise typer.Exit(1)

    holdings = repo.list_by_portfolio_with_prices(portfolio_id)
    if not holdings:
        console.print(f"[yellow]No holdings in '{p.name}'. Add one with: pt holdings add {portfolio_id} <ISIN> <TYPE>[/yellow]")  # noqa: E501
        return

    table = Table(title=f"Holdings — {p.name}")
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("ISIN", style="bold")
    table.add_column("Name")
    table.add_column("Ticker")
    table.add_column("Type")
    table.add_column("TFS%", justify="right")
    table.add_column("Shares", justify="right")
    table.add_column("Cost (€)", justify="right")
    table.add_column("Price (€)", justify="right")
    table.add_column("Value (€)", justify="right")
    table.add_column("P&L (€)", justify="right")

    for h in holdings:
        price_str = f"{h.current_price:,.4f}" if h.current_price else "—"
        value_str = f"{h.current_value:,.2f}" if h.current_price else "—"
        pnl = h.unrealized_pnl if h.current_price else None
        if pnl is not None:
            color = "green" if pnl >= 0 else "red"
            pnl_str = f"[{color}]{pnl:,.2f}[/{color}]"
        else:
            pnl_str = "—"
        tfs_str = f"{h.teilfreistellung_rate * 100:.0f}%" if h.teilfreistellung_rate > 0 else "—"

        table.add_row(
            str(h.id),
            h.isin,
            h.name or "—",
            h.ticker or "—",
            h.asset_type.value,
            tfs_str,
            f"{h.shares:,.4f}",
            f"{h.cost_basis:,.2f}",
            price_str,
            value_str,
            pnl_str,
        )

    # Summary footer with totals + cash
    total_cost = sum(h.cost_basis for h in holdings)
    total_val = sum(h.current_value for h in holdings if h.current_price)
    total_pnl = total_val - total_cost
    cash_balance = cash_repo.get_balance(portfolio_id)

    pnl_color = "green" if total_pnl >= 0 else "red"
    table.add_row("", "", "", "", "", "", f"[bold]{total_cost:,.2f}[/bold]", "", f"[bold]{total_val:,.2f}[/bold]", f"[bold {pnl_color}]{total_pnl:,.2f}[/bold {pnl_color}]")  # noqa: E501
    console.print(table)
    console.print(f"  Cash: [green]€{cash_balance:,.2f}[/green]  |  Total: [bold]€{total_val + cash_balance:,.2f}[/bold]\n")  # noqa: E501


@app.command("remove")
def remove(
    holding_id: int = typer.Argument(..., help="Holding ID"),
    force: bool = typer.Option(False, "--force", "-f"),
):
    """Remove a holding from a portfolio."""
    h = repo.get_by_id(holding_id)
    if not h:
        console.print(f"[red]Holding {holding_id} not found[/red]")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Remove {_display_name(h)} and all its transactions?")
        if not confirm:
            console.print("Cancelled.")
            return

    repo.delete(holding_id)
    console.print(f"[green]Removed {_display_name(h)}[/green]")
