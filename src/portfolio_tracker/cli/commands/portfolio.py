"""Portfolio management commands."""

import typer
from rich.console import Console
from rich.table import Table

from ...core.calculator import PortfolioCalculator
from ...core.models import Portfolio
from ...data.repositories.cash_repo import CashRepository
from ...data.repositories.holdings_repo import HoldingsRepository
from ...data.repositories.portfolios_repo import PortfoliosRepository

app = typer.Typer(help="Manage portfolios")
console = Console()
cash_repo = CashRepository()
repo = PortfoliosRepository()
holdings_repo = HoldingsRepository()


@app.command("create")
def create(
    name: str = typer.Argument(..., help="Portfolio name"),
    description: str = typer.Option("", "--desc", "-d", help="Description"),
):
    """Create a new portfolio."""
    try:
        p = repo.create(Portfolio(name=name, description=description))
        console.print(f"[green]Portfolio '{p.name}' created (ID: {p.id})[/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command("list")
def list_portfolios():
    """List all portfolios."""
    portfolios = repo.list_all()
    if not portfolios:
        console.print("[yellow]No portfolios yet. Create one with: pt portfolio create <name>[/yellow]")
        return

    table = Table(title="Portfolios")
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Name", style="bold")
    table.add_column("Description")
    table.add_column("Created")

    for p in portfolios:
        table.add_row(str(p.id), p.name, p.description, str(p.created_at)[:10])

    console.print(table)


@app.command("show")
def show(portfolio_id: int = typer.Argument(..., help="Portfolio ID")):
    """Show portfolio summary."""
    p = repo.get_by_id(portfolio_id)
    if not p:
        console.print(f"[red]Portfolio {portfolio_id} not found[/red]")
        raise typer.Exit(1)

    holdings = holdings_repo.list_by_portfolio_with_prices(portfolio_id)
    total_cost = PortfolioCalculator.total_cost_basis(holdings)
    total_val = PortfolioCalculator.total_value(holdings)
    pnl = total_val - total_cost

    console.print(f"\n[bold]{p.name}[/bold]  (ID: {p.id})")
    if p.description:
        console.print(f"  {p.description}")
    cash_balance = cash_repo.get_balance(portfolio_id)
    total_portfolio = total_val + cash_balance

    console.print(f"  Holdings: {len(holdings)}")
    console.print(f"  Cost basis: €{total_cost:,.2f}")
    if total_val > 0:
        color = "green" if pnl >= 0 else "red"
        console.print(f"  Holdings value: €{total_val:,.2f}")
        console.print(f"  Cash balance: €{cash_balance:,.2f}")
        console.print(f"  [bold]Portfolio value: €{total_portfolio:,.2f}[/bold]")
        console.print(f"  Unrealized P&L: [{color}]€{pnl:,.2f}[/{color}]")
    console.print()


@app.command("delete")
def delete(
    portfolio_id: int = typer.Argument(..., help="Portfolio ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a portfolio and all its data."""
    p = repo.get_by_id(portfolio_id)
    if not p:
        console.print(f"[red]Portfolio {portfolio_id} not found[/red]")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Delete portfolio '{p.name}' and all its holdings?")
        if not confirm:
            console.print("Cancelled.")
            return

    repo.delete(portfolio_id)
    console.print(f"[green]Portfolio '{p.name}' deleted.[/green]")
