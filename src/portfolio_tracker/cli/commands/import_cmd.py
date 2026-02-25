"""CLI commands for importing broker CSV exports."""

from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ...core.models import AssetType, PricePoint
from ...data.repositories.holdings_repo import HoldingsRepository
from ...data.repositories.prices_repo import PricesRepository
from ...external.price_fetcher import PriceFetcher

app = typer.Typer(help="Import transactions from broker CSV exports")
console = Console()


@app.command("revolut")
def import_revolut(
    tx_csv: Path = typer.Argument(..., help="Path to revolut_transactions.csv"),
    pnl_csv: Optional[Path] = typer.Option(None, "--pnl", help="revolut_pnl.csv for ISIN enrichment"),
    portfolio_name: str = typer.Option("Revolut", "--portfolio-name", "-n", help="Portfolio name to create or reuse"),
    portfolio_id: Optional[int] = typer.Option(None, "--portfolio-id", "-p", help="Use existing portfolio by ID"),
    dry_run: bool = typer.Option(False, "--dry-run", "-d", help="Validate without writing to DB"),
    no_interactive: bool = typer.Option(False, "--no-interactive", help="Skip prompts for unknown tickers (CI/script mode)"),  # noqa: E501
    fetch_prices: bool = typer.Option(True, "--fetch-prices/--no-fetch-prices", help="Fetch current prices after importing new holdings"),  # noqa: E501
):
    """Import Revolut CSV export. Re-running on the same file is safe — duplicates are skipped."""
    if not tx_csv.exists():
        console.print(f"[red]Error:[/red] File not found: {tx_csv}")
        raise typer.Exit(1)

    if pnl_csv is not None and not pnl_csv.exists():
        console.print(f"[red]Error:[/red] P&L file not found: {pnl_csv}")
        raise typer.Exit(1)

    from ...importers.revolut import RevolutImporter

    importer = RevolutImporter(
        portfolio_name=portfolio_name,
        portfolio_id=portfolio_id,
        dry_run=dry_run,
        interactive=not no_interactive,
    )

    mode = "[yellow]DRY RUN[/yellow] — " if dry_run else ""
    console.print(f"\n{mode}Importing [bold]{tx_csv.name}[/bold]…\n")

    try:
        result = importer.run(tx_csv, pnl_csv)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    _print_result(result)

    if fetch_prices and not result.dry_run and result.holdings_created > 0:
        _fetch_prices_for_portfolio(result.portfolio_id)


@app.command("tr")
def import_tr(
    tx_csv: Path = typer.Argument(..., help="Path to Trade Republic export CSV"),
):
    """Import Trade Republic CSV export. (Not yet implemented)"""
    console.print("[red]Trade Republic import not yet implemented.[/red]")
    raise typer.Exit(1)


def _print_result(result) -> None:
    dry_label = " [yellow](dry run — no changes written)[/yellow]" if result.dry_run else ""

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column("", style="dim")
    table.add_column("", justify="right")

    table.add_row("Portfolio", f"[bold]{result.portfolio_name}[/bold] (ID {result.portfolio_id})")
    table.add_section()
    table.add_row("Holdings created", str(result.holdings_created))
    table.add_row("Holdings reused", str(result.holdings_skipped))
    table.add_section()
    table.add_row("Buys imported", str(result.buys_imported))
    table.add_row("Buys skipped (dup)", str(result.buys_skipped))
    table.add_row("Dividends imported", str(result.dividends_imported))
    table.add_row("Dividends skipped (dup)", str(result.dividends_skipped))
    table.add_row("Cash rows imported", str(result.cash_imported))
    table.add_row("Cash rows skipped (dup)", str(result.cash_skipped))

    title = f"Import result{dry_label}"
    console.print(Panel(table, title=title, border_style="green" if not result.dry_run else "yellow"))

    if result.unknown_tickers:
        console.print(f"\n[yellow]Unknown tickers skipped:[/yellow] {', '.join(result.unknown_tickers)}")
        console.print("  Re-run without [bold]--no-interactive[/bold] to enter ISINs at the prompt.")
        console.print("  Answers are saved to [bold]user_registry.json[/bold] — you'll never be asked again.")

    if result.warnings:
        console.print("\n[yellow]Warnings:[/yellow]")
        for w in result.warnings:
            console.print(f"  • {w}")

    if not result.dry_run:
        console.print("\n[green]Done.[/green] Run [bold]pt holdings list[/bold] to verify.")


def _fetch_prices_for_portfolio(portfolio_id: int) -> None:
    """Fetch current prices for all holdings in a portfolio."""
    holdings_repo = HoldingsRepository()
    prices_repo = PricesRepository()
    fetcher = PriceFetcher()

    holdings = [
        h for h in holdings_repo.list_by_portfolio(portfolio_id)
        if h.asset_type in (AssetType.STOCK, AssetType.ETF, AssetType.BOND)
    ]
    if not holdings:
        return

    console.print(f"\nFetching prices for {len(holdings)} holdings…")
    ok = 0
    for h in holdings:
        lookup = h.ticker or h.isin
        try:
            price = fetcher.fetch_price(lookup)
            if price is not None:
                prices_repo.store_price(PricePoint(
                    holding_id=h.id, price=price, fetch_date=datetime.now(), source="yfinance",
                ))
                console.print(f"  [green]✓[/green] {lookup}: €{price:,.4f}")
                ok += 1
            else:
                console.print(f"  [yellow]✗[/yellow] {lookup}: not found")
        except Exception as e:
            console.print(f"  [red]✗[/red] {lookup}: {e}")

    console.print(f"Prices fetched: {ok}/{len(holdings)}")
