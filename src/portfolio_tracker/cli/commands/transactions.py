"""Transaction commands — buy, sell, list."""

from datetime import datetime
from decimal import Decimal, InvalidOperation

import typer
from rich.console import Console
from rich.table import Table

from ...core.exceptions import InsufficientSharesError
from ...core.models import CashTransactionType, TransactionType
from ...data.repositories.cash_repo import CashRepository
from ...data.repositories.holdings_repo import HoldingsRepository
from ...data.repositories.transactions_repo import TransactionsRepository

app = typer.Typer(help="Record transactions")
console = Console()
cash_repo = CashRepository()
holdings_repo = HoldingsRepository()
tx_repo = TransactionsRepository()


def _record_transaction(
    holding_id: int,
    tx_type: TransactionType,
    quantity: str,
    price: str,
    date: str | None,
    notes: str,
):
    h = holdings_repo.get_by_id(holding_id)
    if not h:
        console.print(f"[red]Holding {holding_id} not found[/red]")
        raise typer.Exit(1)

    try:
        qty = Decimal(quantity)
        prc = Decimal(price)
    except InvalidOperation:
        console.print("[red]Invalid number format for quantity or price[/red]")
        raise typer.Exit(1)

    if qty <= 0 or prc < 0:
        console.print("[red]Quantity must be positive, price must be non-negative[/red]")
        raise typer.Exit(1)

    if tx_type == TransactionType.SELL and qty > h.shares:
        console.print(
            f"[red]Cannot sell {qty} shares — only {h.shares} available[/red]"
        )
        raise typer.Exit(1)

    tx_date = datetime.now()
    if date:
        try:
            tx_date = datetime.fromisoformat(date)
        except ValueError:
            console.print("[red]Invalid date format. Use YYYY-MM-DD[/red]")
            raise typer.Exit(1)

    tx = tx_repo.create(holding_id, tx_type, qty, prc, tx_date, notes)

    # Update holding shares and cost basis
    if tx_type == TransactionType.BUY:
        new_shares = h.shares + qty
        new_cost = h.cost_basis + (qty * prc)
    else:
        new_shares = h.shares - qty
        # Proportional cost basis reduction
        if h.shares > 0:
            cost_per_share = h.cost_basis / h.shares
            new_cost = h.cost_basis - (qty * cost_per_share)
        else:
            new_cost = Decimal("0")

    holdings_repo.update_shares_and_cost(holding_id, new_shares, new_cost)

    # Record cash impact
    if tx_type == TransactionType.BUY:
        cash_repo.create(
            h.portfolio_id, CashTransactionType.BUY, -(qty * prc), tx_date,
            description=f"Buy {h.ticker or h.isin}",
        )
    elif tx_type == TransactionType.SELL:
        cash_repo.create(
            h.portfolio_id, CashTransactionType.SELL, qty * prc, tx_date,
            description=f"Sell {h.ticker or h.isin}",
        )

    action = "Bought" if tx_type == TransactionType.BUY else "Sold"
    cash_balance = cash_repo.get_balance(h.portfolio_id)
    console.print(
        f"[green]{action} {qty} × {h.name or h.isin} @ €{prc:,.4f} = €{tx.total_value:,.2f}[/green]"
    )
    console.print(f"  Cash balance: €{cash_balance:,.2f}")


@app.command("buy")
def buy(
    holding_id: int = typer.Argument(..., help="Holding ID"),
    quantity: str = typer.Argument(..., help="Number of shares/units"),
    price: str = typer.Argument(..., help="Price per share (EUR)"),
    date: str = typer.Option(None, "--date", "-d", help="Transaction date (YYYY-MM-DD)"),
    notes: str = typer.Option("", "--notes", "-n", help="Notes"),
):
    """Record a buy transaction."""
    _record_transaction(holding_id, TransactionType.BUY, quantity, price, date, notes)


@app.command("sell")
def sell(
    holding_id: int = typer.Argument(..., help="Holding ID"),
    quantity: str = typer.Argument(..., help="Number of shares/units"),
    price: str = typer.Argument(..., help="Price per share (EUR)"),
    date: str = typer.Option(None, "--date", "-d", help="Transaction date (YYYY-MM-DD)"),
    notes: str = typer.Option("", "--notes", "-n", help="Notes"),
):
    """Record a sell transaction."""
    _record_transaction(holding_id, TransactionType.SELL, quantity, price, date, notes)


@app.command("list")
def list_transactions(
    holding_id: int = typer.Argument(..., help="Holding ID"),
):
    """List transactions for a holding."""
    h = holdings_repo.get_by_id(holding_id)
    if not h:
        console.print(f"[red]Holding {holding_id} not found[/red]")
        raise typer.Exit(1)

    txs = tx_repo.list_by_holding(holding_id)
    if not txs:
        console.print(f"[yellow]No transactions for {h.name or h.isin}[/yellow]")
        return

    table = Table(title=f"Transactions — {h.name or h.isin} ({h.isin})")
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Type")
    table.add_column("Qty", justify="right")
    table.add_column("Price (€)", justify="right")
    table.add_column("Total (€)", justify="right")
    table.add_column("Date")
    table.add_column("Notes")

    for tx in txs:
        color = "green" if tx.transaction_type == TransactionType.BUY else "red"
        table.add_row(
            str(tx.id),
            f"[{color}]{tx.transaction_type.value.upper()}[/{color}]",
            f"{tx.quantity:,.4f}",
            f"{tx.price:,.4f}",
            f"{tx.total_value:,.2f}",
            tx.transaction_date.strftime("%Y-%m-%d"),
            tx.notes,
        )

    console.print(table)
