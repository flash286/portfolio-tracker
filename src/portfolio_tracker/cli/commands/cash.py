"""Cash balance management commands."""

from datetime import datetime
from decimal import Decimal

import typer
from rich.console import Console
from rich.table import Table

from ...core.models import CashTransactionType
from ...data.repositories.cash_repo import CashRepository
from ...data.repositories.portfolios_repo import PortfoliosRepository

app = typer.Typer(help="Cash balance management")
console = Console()
cash_repo = CashRepository()
portfolios_repo = PortfoliosRepository()


@app.command("balance")
def balance(portfolio_id: int = typer.Argument(..., help="Portfolio ID")):
    """Show current cash balance for a portfolio."""
    p = portfolios_repo.get_by_id(portfolio_id)
    if not p:
        console.print(f"[red]Portfolio {portfolio_id} not found[/red]")
        raise typer.Exit(1)

    bal = cash_repo.get_balance(portfolio_id)
    console.print(f"\n[bold]{p.name}[/bold] — Cash Balance: [green]€{bal:,.2f}[/green]\n")


@app.command("history")
def history(
    portfolio_id: int = typer.Argument(..., help="Portfolio ID"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max rows"),
):
    """Show cash transaction history."""
    p = portfolios_repo.get_by_id(portfolio_id)
    if not p:
        console.print(f"[red]Portfolio {portfolio_id} not found[/red]")
        raise typer.Exit(1)

    txs = cash_repo.list_by_portfolio(portfolio_id)
    if not txs:
        console.print("[yellow]No cash transactions found[/yellow]")
        return

    table = Table(title=f"Cash Transactions — {p.name}")
    table.add_column("ID", style="dim")
    table.add_column("Date")
    table.add_column("Type")
    table.add_column("Amount (€)", justify="right")
    table.add_column("Description")

    for tx in txs[:limit]:
        color = "green" if tx.amount > 0 else "red"
        table.add_row(
            str(tx.id),
            tx.transaction_date.strftime("%Y-%m-%d"),
            tx.cash_type.value,
            f"[{color}]{tx.amount:,.2f}[/{color}]",
            tx.description,
        )

    console.print(table)
    bal = cash_repo.get_balance(portfolio_id)
    console.print(f"\n  Current balance: [bold green]€{bal:,.2f}[/bold green]\n")


@app.command("add")
def add(
    portfolio_id: int = typer.Argument(..., help="Portfolio ID"),
    amount: float = typer.Argument(..., help="Amount in EUR (positive = deposit, negative = withdrawal)"),
    description: str = typer.Option("", "--desc", "-d", help="Description"),
    cash_type: str = typer.Option("top_up", "--type", "-t", help="Type: top_up, withdrawal, fee"),
):
    """Add a manual cash transaction."""
    p = portfolios_repo.get_by_id(portfolio_id)
    if not p:
        console.print(f"[red]Portfolio {portfolio_id} not found[/red]")
        raise typer.Exit(1)

    try:
        ct = CashTransactionType(cash_type)
    except ValueError:
        valid = ", ".join(t.value for t in CashTransactionType)
        console.print(f"[red]Invalid type '{cash_type}'. Valid: {valid}[/red]")
        raise typer.Exit(1)

    tx = cash_repo.create(
        portfolio_id, ct, Decimal(str(amount)), datetime.now(), description=description,
    )
    bal = cash_repo.get_balance(portfolio_id)
    console.print(f"[green]✓[/green] Added {ct.value} of €{amount:,.2f}")
    console.print(f"  New balance: [bold green]€{bal:,.2f}[/bold green]")
