"""Holdings management commands."""

import typer
from rich.console import Console
from rich.table import Table

from ...core.models import AssetType
from ...data.repositories.holdings_repo import HoldingsRepository
from ...data.repositories.portfolios_repo import PortfoliosRepository
from ...data.repositories.prices_repo import PricesRepository

app = typer.Typer(help="Manage holdings")
console = Console()
repo = HoldingsRepository()
portfolios_repo = PortfoliosRepository()
prices_repo = PricesRepository()

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

    existing = repo.get_by_isin(portfolio_id, isin)
    if existing:
        console.print(f"[yellow]{isin} already exists in this portfolio (ID: {existing.id})[/yellow]")
        return

    h = repo.create(portfolio_id, isin, AssetType(asset_type), name=name, ticker=ticker)
    console.print(f"[green]Added {_display_name(h)} ({h.asset_type.value}) to '{p.name}' (Holding ID: {h.id})[/green]")


@app.command("list")
def list_holdings(portfolio_id: int = typer.Argument(..., help="Portfolio ID")):
    """List all holdings in a portfolio."""
    p = portfolios_repo.get_by_id(portfolio_id)
    if not p:
        console.print(f"[red]Portfolio {portfolio_id} not found[/red]")
        raise typer.Exit(1)

    holdings = repo.list_by_portfolio(portfolio_id)
    if not holdings:
        console.print(f"[yellow]No holdings in '{p.name}'. Add one with: pt holdings add {portfolio_id} <ISIN> <TYPE>[/yellow]")
        return

    # Load latest prices
    for h in holdings:
        latest = prices_repo.get_latest(h.id)
        if latest:
            h.current_price = latest.price

    table = Table(title=f"Holdings — {p.name}")
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("ISIN", style="bold")
    table.add_column("Name")
    table.add_column("Ticker")
    table.add_column("Type")
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

        table.add_row(
            str(h.id),
            h.isin,
            h.name or "—",
            h.ticker or "—",
            h.asset_type.value,
            f"{h.shares:,.4f}",
            f"{h.cost_basis:,.2f}",
            price_str,
            value_str,
            pnl_str,
        )

    console.print(table)


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
