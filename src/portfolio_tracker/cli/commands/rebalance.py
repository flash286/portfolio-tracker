"""Rebalancing commands."""

from datetime import datetime
from decimal import Decimal, InvalidOperation

import typer
from rich.console import Console
from rich.table import Table

from ...core.models import AssetType, CashTransactionType, TransactionType
from ...core.rebalancer import Rebalancer
from ...data.repositories.cash_repo import CashRepository
from ...data.repositories.holdings_repo import HoldingsRepository
from ...data.repositories.portfolios_repo import PortfoliosRepository
from ...data.repositories.prices_repo import PricesRepository
from ...data.repositories.targets_repo import TargetsRepository
from ...data.repositories.transactions_repo import TransactionsRepository

app = typer.Typer(help="Rebalancing")
console = Console()
cash_repo = CashRepository()
holdings_repo = HoldingsRepository()
portfolios_repo = PortfoliosRepository()
prices_repo = PricesRepository()
targets_repo = TargetsRepository()
tx_repo = TransactionsRepository()


def _load_holdings_with_prices(portfolio_id: int):
    holdings = holdings_repo.list_by_portfolio(portfolio_id)
    for h in holdings:
        latest = prices_repo.get_latest(h.id)
        if latest:
            h.current_price = latest.price
    return holdings


@app.command("target")
def set_targets(portfolio_id: int = typer.Argument(..., help="Portfolio ID")):
    """Set target allocations interactively."""
    p = portfolios_repo.get_by_id(portfolio_id)
    if not p:
        console.print(f"[red]Portfolio {portfolio_id} not found[/red]")
        raise typer.Exit(1)

    # Determine which asset types are in the portfolio
    holdings = holdings_repo.list_by_portfolio(portfolio_id)
    asset_types = sorted(set(h.asset_type.value for h in holdings))

    if not asset_types:
        console.print("[yellow]No holdings yet. Add holdings first.[/yellow]")
        return

    # Show current targets
    current_targets = targets_repo.list_by_portfolio(portfolio_id)
    if current_targets:
        console.print("\n[bold]Current targets:[/bold]")
        for t in current_targets:
            console.print(f"  {t.asset_type}: {t.target_percentage}% (threshold: {t.rebalance_threshold}%)")
        console.print()

    console.print(f"[bold]Set target allocation for portfolio '{p.name}'[/bold]")
    console.print(f"Asset types in portfolio: {', '.join(asset_types)}\n")

    total = Decimal("0")
    new_targets = []

    for atype in asset_types:
        existing = next((t for t in current_targets if t.asset_type == atype), None)
        default = str(existing.target_percentage) if existing else ""
        prompt = f"  Target % for {atype}"
        if default:
            prompt += f" [{default}]"

        while True:
            raw = typer.prompt(prompt, default=default)
            try:
                pct = Decimal(raw)
                if pct < 0 or pct > 100:
                    console.print("  [red]Must be between 0 and 100[/red]")
                    continue
                break
            except InvalidOperation:
                console.print("  [red]Invalid number[/red]")

        threshold_default = str(existing.rebalance_threshold) if existing else "5"
        raw_thresh = typer.prompt(f"  Rebalance threshold % for {atype}", default=threshold_default)
        try:
            threshold = Decimal(raw_thresh)
        except InvalidOperation:
            threshold = Decimal("5")

        new_targets.append((atype, pct, threshold))
        total += pct

    if total != 100:
        console.print(f"\n[yellow]Warning: targets sum to {total}%, not 100%[/yellow]")
        if not typer.confirm("Save anyway?"):
            console.print("Cancelled.")
            return

    for atype, pct, threshold in new_targets:
        targets_repo.set_target(portfolio_id, atype, pct, threshold)

    console.print(f"\n[green]Target allocations saved for '{p.name}'[/green]")


@app.command("check")
def check(portfolio_id: int = typer.Argument(..., help="Portfolio ID")):
    """Check current deviation from target allocations."""
    p = portfolios_repo.get_by_id(portfolio_id)
    if not p:
        console.print(f"[red]Portfolio {portfolio_id} not found[/red]")
        raise typer.Exit(1)

    holdings = _load_holdings_with_prices(portfolio_id)
    targets = targets_repo.list_by_portfolio(portfolio_id)

    if not targets:
        console.print("[yellow]No target allocations set. Run: pt rebalance target <portfolio_id>[/yellow]")
        return

    rebalancer = Rebalancer(holdings, targets)
    deviations = rebalancer.check_deviation()

    table = Table(title=f"Allocation Check — {p.name}")
    table.add_column("Asset Type", style="bold")
    table.add_column("Current %", justify="right")
    table.add_column("Target %", justify="right")
    table.add_column("Deviation", justify="right")
    table.add_column("Threshold", justify="right")
    table.add_column("Status")

    for atype, info in sorted(deviations.items()):
        dev = info["deviation"]
        color = "green" if not info["needs_rebalance"] else "red"
        status = f"[{color}]{'REBALANCE' if info['needs_rebalance'] else 'OK'}[/{color}]"
        dev_str = f"[{color}]{dev:+.2f}%[/{color}]"

        table.add_row(
            atype,
            f"{info['current']:.2f}%",
            f"{info['target']:.2f}%",
            dev_str,
            f"{info['threshold']:.2f}%",
            status,
        )

    console.print(table)


@app.command("suggest")
def suggest(portfolio_id: int = typer.Argument(..., help="Portfolio ID")):
    """Suggest trades to rebalance portfolio."""
    p = portfolios_repo.get_by_id(portfolio_id)
    if not p:
        console.print(f"[red]Portfolio {portfolio_id} not found[/red]")
        raise typer.Exit(1)

    holdings = _load_holdings_with_prices(portfolio_id)
    targets = targets_repo.list_by_portfolio(portfolio_id)

    if not targets:
        console.print("[yellow]No targets set. Run: pt rebalance target <portfolio_id>[/yellow]")
        return

    rebalancer = Rebalancer(holdings, targets)
    trades = rebalancer.suggest_trades()

    if not trades:
        console.print("[green]Portfolio is within target allocations. No rebalancing needed.[/green]")
        return

    table = Table(title=f"Suggested Rebalancing Trades — {p.name}")
    table.add_column("Action", style="bold")
    table.add_column("ISIN")
    table.add_column("Shares", justify="right")
    table.add_column("Price (€)", justify="right")
    table.add_column("Value (€)", justify="right")
    table.add_column("Reason")

    for t in trades:
        color = "green" if t.action == TransactionType.BUY else "red"
        table.add_row(
            f"[{color}]{t.action.value.upper()}[/{color}]",
            t.isin,
            f"{t.shares:,.4f}",
            f"{t.current_price:,.4f}",
            f"{t.trade_value:,.2f}",
            t.reason,
        )

    console.print(table)

    # Show cash impact
    cash_balance = cash_repo.get_balance(portfolio_id)
    buy_total = sum(t.trade_value for t in trades if t.action == TransactionType.BUY)
    sell_total = sum(t.trade_value for t in trades if t.action == TransactionType.SELL)
    net_cash_impact = sell_total - buy_total
    remaining = cash_balance + net_cash_impact

    console.print(f"\n  Available cash: €{cash_balance:,.2f}")
    console.print(f"  Net cash impact: €{net_cash_impact:+,.2f}")
    color = "green" if remaining >= 0 else "red"
    console.print(f"  Remaining cash: [{color}]€{remaining:,.2f}[/{color}]")
    if remaining < 0:
        console.print(f"  [red]⚠ Not enough cash — need €{-remaining:,.2f} more[/red]")
    console.print("\n[dim]Run 'pt rebalance execute <portfolio_id>' to execute these trades[/dim]")


@app.command("execute")
def execute(
    portfolio_id: int = typer.Argument(..., help="Portfolio ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Execute suggested rebalancing trades."""
    p = portfolios_repo.get_by_id(portfolio_id)
    if not p:
        console.print(f"[red]Portfolio {portfolio_id} not found[/red]")
        raise typer.Exit(1)

    holdings = _load_holdings_with_prices(portfolio_id)
    targets = targets_repo.list_by_portfolio(portfolio_id)

    if not targets:
        console.print("[yellow]No targets set.[/yellow]")
        return

    rebalancer = Rebalancer(holdings, targets)
    trades = rebalancer.suggest_trades()

    if not trades:
        console.print("[green]No rebalancing needed.[/green]")
        return

    # Show trades
    for t in trades:
        action = "BUY" if t.action == TransactionType.BUY else "SELL"
        console.print(f"  {action} {t.shares:,.4f} {t.isin} @ €{t.current_price:,.4f} = €{t.trade_value:,.2f}")

    if not force:
        confirm = typer.confirm("\nExecute these trades?")
        if not confirm:
            console.print("Cancelled.")
            return

    # Record transactions
    now = datetime.now()
    for t in trades:
        h = next((h for h in holdings if h.isin == t.isin), None)
        if not h:
            continue

        tx_repo.create(h.id, t.action, t.shares, t.current_price, now, f"Rebalance: {t.reason}")

        if t.action == TransactionType.BUY:
            new_shares = h.shares + t.shares
            new_cost = h.cost_basis + t.trade_value
            # Cash outflow
            cash_repo.create(
                portfolio_id, CashTransactionType.BUY, -t.trade_value, now,
                description=f"Rebalance: Buy {t.ticker or t.isin}",
            )
        else:
            new_shares = h.shares - t.shares
            cost_per_share = h.cost_basis / h.shares if h.shares > 0 else Decimal("0")
            new_cost = h.cost_basis - (t.shares * cost_per_share)
            # Cash inflow
            cash_repo.create(
                portfolio_id, CashTransactionType.SELL, t.trade_value, now,
                description=f"Rebalance: Sell {t.ticker or t.isin}",
            )

        holdings_repo.update_shares_and_cost(h.id, new_shares, new_cost)

    new_balance = cash_repo.get_balance(portfolio_id)
    console.print(f"\n[green]Executed {len(trades)} rebalancing trades.[/green]")
    console.print(f"  Cash balance: €{new_balance:,.2f}")
