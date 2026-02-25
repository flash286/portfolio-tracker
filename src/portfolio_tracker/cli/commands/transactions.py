"""Transaction commands — buy, sell, list."""

from datetime import datetime
from decimal import Decimal, InvalidOperation

import typer
from rich.console import Console
from rich.table import Table

from ...core.models import CashTransaction, CashTransactionType, TaxLot, Transaction, TransactionType
from ...data.database import get_db
from ...data.repositories.cash_repo import CashRepository
from ...data.repositories.holdings_repo import HoldingsRepository
from ...data.repositories.lots_repo import LotsRepository
from ...data.repositories.transactions_repo import TransactionsRepository

app = typer.Typer(help="Record transactions")
console = Console()
cash_repo = CashRepository()
holdings_repo = HoldingsRepository()
lots_repo = LotsRepository()
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

    # Pre-compute FIFO matching for SELL (read-only, before transaction)
    realized_gain = None
    lots_to_consume = []  # list of (lot_id, consumed_qty)

    if tx_type == TransactionType.SELL:
        open_lots = lots_repo.get_open_lots_fifo(holding_id)
        qty_remaining_temp = qty
        realized_gain = Decimal("0")

        for lot in open_lots:
            if qty_remaining_temp <= 0:
                break
            consumed = min(qty_remaining_temp, lot.quantity_remaining)
            realized_gain += consumed * (prc - lot.cost_per_unit)
            lots_to_consume.append((lot.id, consumed))
            qty_remaining_temp -= consumed

    db = get_db()
    with db.transaction():
        tx = tx_repo.create(Transaction(
            holding_id=holding_id, transaction_type=tx_type,
            quantity=qty, price=prc, transaction_date=tx_date, notes=notes,
            realized_gain=realized_gain,
        ))

        if tx_type == TransactionType.BUY:
            lots_repo.create(TaxLot(
                holding_id=holding_id, acquired_date=tx_date,
                quantity=qty, cost_per_unit=prc, quantity_remaining=qty,
                buy_transaction_id=tx.id,
            ))
            new_shares = h.shares + qty
            new_cost = h.cost_basis + (qty * prc)
        else:  # SELL
            for lot_id, consumed in lots_to_consume:
                lots_repo.reduce_lot(lot_id, consumed)
            new_shares = h.shares - qty
            new_cost = lots_repo.get_fifo_cost_basis(holding_id)

        h.shares = new_shares
        h.cost_basis = new_cost
        holdings_repo.save(h)

        # Record cash impact
        if tx_type == TransactionType.BUY:
            cash_repo.create(CashTransaction(
                portfolio_id=h.portfolio_id, cash_type=CashTransactionType.BUY,
                amount=-(qty * prc), transaction_date=tx_date,
                description=f"Buy {h.ticker or h.isin}",
            ))
        else:
            cash_repo.create(CashTransaction(
                portfolio_id=h.portfolio_id, cash_type=CashTransactionType.SELL,
                amount=qty * prc, transaction_date=tx_date,
                description=f"Sell {h.ticker or h.isin}",
            ))

    action = "Bought" if tx_type == TransactionType.BUY else "Sold"
    cash_balance = cash_repo.get_balance(h.portfolio_id)
    console.print(
        f"[green]{action} {qty} × {h.name or h.isin} @ €{prc:,.4f} = €{tx.total_value:,.2f}[/green]"
    )
    if tx_type == TransactionType.SELL and realized_gain is not None:
        gain_color = "green" if realized_gain >= 0 else "red"
        console.print(f"  Realized gain: [{gain_color}]€{realized_gain:,.2f}[/{gain_color}] (FIFO)")
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
