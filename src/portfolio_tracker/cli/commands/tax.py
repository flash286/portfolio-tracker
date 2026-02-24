"""Tax reporting commands — FIFO lots and realized gains."""

from datetime import datetime
from decimal import Decimal

import typer
from rich.console import Console
from rich.table import Table

from ...core.calculator import PortfolioCalculator
from ...data.repositories.holdings_repo import HoldingsRepository
from ...data.repositories.lots_repo import LotsRepository
from ...data.repositories.portfolios_repo import PortfoliosRepository
from ...data.repositories.transactions_repo import TransactionsRepository

app = typer.Typer(help="Tax reporting")
console = Console()
holdings_repo = HoldingsRepository()
lots_repo = LotsRepository()
portfolios_repo = PortfoliosRepository()
tx_repo = TransactionsRepository()


@app.command("realized")
def realized(
    portfolio_id: int = typer.Argument(..., help="Portfolio ID"),
    year: int = typer.Option(datetime.now().year, "--year", "-y", help="Tax year"),
):
    """Show realized gains for a year with Teilfreistellung and tax estimate."""
    p = portfolios_repo.get_by_id(portfolio_id)
    if not p:
        console.print(f"[red]Portfolio {portfolio_id} not found[/red]")
        raise typer.Exit(1)

    sells = tx_repo.list_sells_by_portfolio_year(portfolio_id, year)
    if not sells:
        console.print(f"[yellow]No sell transactions for {year} in '{p.name}'[/yellow]")
        return

    holdings = holdings_repo.list_by_portfolio(portfolio_id)
    holding_map = {h.id: h for h in holdings}

    table = Table(title=f"Realized Gains — {p.name} ({year})")
    table.add_column("Date")
    table.add_column("ISIN", style="bold")
    table.add_column("Name")
    table.add_column("Qty", justify="right")
    table.add_column("Realized (€)", justify="right")
    table.add_column("TFS%", justify="right")
    table.add_column("Taxable (€)", justify="right")

    total_realized = Decimal("0")
    total_taxable = Decimal("0")

    for tx in sells:
        h = holding_map.get(tx.holding_id)
        gain = tx.realized_gain if tx.realized_gain is not None else Decimal("0")
        tfs_rate = h.teilfreistellung_rate if h else Decimal("0")
        exempt = (gain * tfs_rate).quantize(Decimal("0.01"))
        taxable = gain - exempt

        total_realized += gain
        total_taxable += taxable

        gain_color = "green" if gain >= 0 else "red"
        tfs_str = f"{tfs_rate * 100:.0f}%" if tfs_rate > 0 else "—"

        table.add_row(
            tx.transaction_date.strftime("%Y-%m-%d"),
            h.isin if h else "?",
            (h.name if h else "?")[:32],
            f"{tx.quantity:,.4f}",
            f"[{gain_color}]€{gain:+,.2f}[/{gain_color}]",
            tfs_str,
            f"€{taxable:,.2f}",
        )

    table.add_row(
        "", "", "", "",
        f"[bold]€{total_realized:+,.2f}[/bold]",
        "",
        f"[bold]€{total_taxable:,.2f}[/bold]",
    )
    console.print(table)

    # Tax estimate on total taxable (TFS already applied per-row)
    tax_info = PortfolioCalculator.calculate_german_tax(max(total_taxable, Decimal("0")))
    tfs_exempt_total = total_realized - total_taxable

    console.print(f"\n  Total realized gain:        €{total_realized:+,.2f}")
    if tfs_exempt_total > 0:
        console.print(f"  Teilfreistellung-exempt:    −€{tfs_exempt_total:,.2f}")
    console.print(f"  Taxable (after TFS):        €{total_taxable:,.2f}")
    console.print(f"  Freistellungsauftrag used:  €{tax_info.freistellungsauftrag_used:,.2f}")
    console.print(f"  Steuerpflichtiger Gewinn:   €{tax_info.taxable_gain:,.2f}")
    tax_color = "red" if tax_info.total_tax > 0 else "green"
    console.print(f"  Est. Steuer:                [{tax_color}]€{tax_info.total_tax:,.2f}[/{tax_color}]")
    console.print()


@app.command("lots")
def lots(
    holding_id: int = typer.Argument(..., help="Holding ID"),
):
    """Show FIFO tax lots for a holding."""
    h = holdings_repo.get_by_id(holding_id)
    if not h:
        console.print(f"[red]Holding {holding_id} not found[/red]")
        raise typer.Exit(1)

    all_lots = lots_repo.list_by_holding(holding_id)
    if not all_lots:
        console.print(f"[yellow]No tax lots for {h.name or h.isin}[/yellow]")
        console.print("[dim]Lots are created automatically on buy transactions.[/dim]")
        return

    table = Table(title=f"Tax Lots — {h.name or h.isin} ({h.isin})")
    table.add_column("ID", justify="right", style="dim")
    table.add_column("Acquired")
    table.add_column("Qty", justify="right")
    table.add_column("Cost/Unit (€)", justify="right")
    table.add_column("Remaining", justify="right")
    table.add_column("Basis (€)", justify="right")
    table.add_column("Status")

    total_basis = Decimal("0")
    for lot in all_lots:
        basis = lot.quantity_remaining * lot.cost_per_unit
        total_basis += basis
        is_open = lot.quantity_remaining > 0
        status = "[green]Open[/green]" if is_open else "[dim]Consumed[/dim]"

        table.add_row(
            str(lot.id),
            lot.acquired_date.strftime("%Y-%m-%d"),
            f"{lot.quantity:,.4f}",
            f"{lot.cost_per_unit:,.4f}",
            f"{lot.quantity_remaining:,.4f}",
            f"€{basis:,.2f}",
            status,
        )

    console.print(table)
    tfs_str = f"{h.teilfreistellung_rate * 100:.0f}%" if h.teilfreistellung_rate > 0 else "0%"
    console.print(f"  FIFO cost basis: [bold]€{total_basis:,.2f}[/bold]  |  TFS rate: {tfs_str}\n")
