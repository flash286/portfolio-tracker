"""Portfolio Tracker CLI — main entry point."""

import typer

from ..data.database import get_db
from .commands import cash, dashboard, holdings, portfolio, prices, rebalance, stats, transactions

app = typer.Typer(
    name="pt",
    help="Investment portfolio tracker with rebalancing (Trade Republic / Germany)",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

app.add_typer(cash.app, name="cash", help="Cash balance management")
app.add_typer(portfolio.app, name="portfolio", help="Manage portfolios")
app.add_typer(holdings.app, name="holdings", help="Manage holdings")
app.add_typer(transactions.app, name="tx", help="Record buy/sell transactions")
app.add_typer(prices.app, name="prices", help="Fetch & view prices")
app.add_typer(stats.app, name="stats", help="Portfolio statistics & tax")
app.add_typer(rebalance.app, name="rebalance", help="Target allocation & rebalancing")
app.add_typer(dashboard.app, name="dashboard", help="Web dashboard")


@app.callback()
def startup():
    """Initialize database on first run."""
    get_db()


if __name__ == "__main__":
    app()
