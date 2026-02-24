"""Price fetching commands."""

import typer
from rich.console import Console
from rich.table import Table

from ...core.models import AssetType
from ...data.repositories.holdings_repo import HoldingsRepository
from ...data.repositories.portfolios_repo import PortfoliosRepository
from ...data.repositories.prices_repo import PricesRepository
from ...external.price_fetcher import PriceFetcher
from ...external.crypto_fetcher import CryptoFetcher

app = typer.Typer(help="Fetch and view prices")
console = Console()
holdings_repo = HoldingsRepository()
portfolios_repo = PortfoliosRepository()
prices_repo = PricesRepository()


@app.command("fetch")
def fetch(portfolio_id: int = typer.Argument(..., help="Portfolio ID")):
    """Fetch latest prices for all holdings in a portfolio.

    Uses the 'ticker' field for yfinance lookups. For crypto, uses ISIN or ticker
    to resolve CoinGecko ID.
    """
    p = portfolios_repo.get_by_id(portfolio_id)
    if not p:
        console.print(f"[red]Portfolio {portfolio_id} not found[/red]")
        raise typer.Exit(1)

    holdings = holdings_repo.list_by_portfolio(portfolio_id)
    if not holdings:
        console.print("[yellow]No holdings to fetch prices for[/yellow]")
        return

    # Separate by type
    stock_holdings = [h for h in holdings if h.asset_type in (AssetType.STOCK, AssetType.ETF, AssetType.BOND)]
    crypto_holdings = [h for h in holdings if h.asset_type == AssetType.CRYPTO]

    console.print(f"Fetching prices for {len(holdings)} holdings...")

    # Map: holding_id -> price
    prices_by_id: dict[int, object] = {}

    # Fetch stock/ETF/bond prices via yfinance (needs ticker)
    if stock_holdings:
        fetcher = PriceFetcher()
        for h in stock_holdings:
            lookup = h.ticker or h.isin  # Prefer ticker, fallback to ISIN
            if not lookup:
                continue
            price = fetcher.fetch_price(lookup)
            if price is not None:
                prices_by_id[h.id] = price

    # Fetch crypto prices via CoinGecko (needs ticker like BTC, ETH)
    if crypto_holdings:
        crypto = CryptoFetcher()
        tickers = [h.ticker or h.isin for h in crypto_holdings]
        batch = crypto.fetch_batch(tickers)
        for h in crypto_holdings:
            key = h.ticker or h.isin
            if key.upper() in batch and batch[key.upper()] is not None:
                prices_by_id[h.id] = batch[key.upper()]

    # Store and display
    table = Table(title="Fetched Prices")
    table.add_column("ISIN", style="bold")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Price (€)", justify="right")
    table.add_column("Status")

    for h in holdings:
        price = prices_by_id.get(h.id)
        if price is not None:
            source = "coingecko" if h.asset_type == AssetType.CRYPTO else "yfinance"
            prices_repo.store_price(h.id, price, source=source)
            table.add_row(h.isin, h.name or h.ticker or "—", h.asset_type.value, f"{price:,.4f}", "[green]OK[/green]")
        else:
            table.add_row(h.isin, h.name or h.ticker or "—", h.asset_type.value, "—", "[red]FAILED[/red]")

    console.print(table)


@app.command("history")
def history(
    holding_id: int = typer.Argument(..., help="Holding ID"),
    days: int = typer.Option(30, "--days", "-d", help="Number of days"),
):
    """Show price history for a holding."""
    h = holdings_repo.get_by_id(holding_id)
    if not h:
        console.print(f"[red]Holding {holding_id} not found[/red]")
        raise typer.Exit(1)

    points = prices_repo.get_history(h.id, limit=days)
    if not points:
        console.print(f"[yellow]No price history for {h.name or h.isin}. Run: pt prices fetch <portfolio_id>[/yellow]")
        return

    table = Table(title=f"Price History — {h.name or h.isin}")
    table.add_column("Date")
    table.add_column("Price (€)", justify="right")
    table.add_column("Source")

    for pt in points:
        table.add_row(
            pt.fetch_date.strftime("%Y-%m-%d %H:%M"),
            f"{pt.price:,.4f}",
            pt.source,
        )

    console.print(table)
