"""Statistics commands."""

from decimal import Decimal

import typer
from rich.console import Console
from rich.table import Table

from ...core.calculator import PortfolioCalculator
from ...data.repositories.cash_repo import CashRepository
from ...data.repositories.holdings_repo import HoldingsRepository
from ...data.repositories.portfolios_repo import PortfoliosRepository
from ...data.repositories.prices_repo import PricesRepository

app = typer.Typer(help="Portfolio statistics")
console = Console()
cash_repo = CashRepository()
holdings_repo = HoldingsRepository()
portfolios_repo = PortfoliosRepository()
prices_repo = PricesRepository()


def _load_holdings_with_prices(portfolio_id: int):
    """Load holdings and attach latest prices."""
    holdings = holdings_repo.list_by_portfolio(portfolio_id)
    for h in holdings:
        latest = prices_repo.get_latest(h.id)
        if latest:
            h.current_price = latest.price
    return holdings


@app.command("summary")
def summary(portfolio_id: int = typer.Argument(..., help="Portfolio ID")):
    """Show portfolio summary: value, P&L, allocation."""
    p = portfolios_repo.get_by_id(portfolio_id)
    if not p:
        console.print(f"[red]Portfolio {portfolio_id} not found[/red]")
        raise typer.Exit(1)

    holdings = _load_holdings_with_prices(portfolio_id)
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

    holdings = _load_holdings_with_prices(portfolio_id)
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
