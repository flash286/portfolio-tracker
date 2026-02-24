"""Tax reporting commands — FIFO lots and realized gains."""

from datetime import datetime
from decimal import Decimal

import typer
from rich.console import Console
from rich.table import Table

from ...core.calculator import BASISZINS, PortfolioCalculator
from ...data.repositories.holdings_repo import HoldingsRepository
from ...data.repositories.lots_repo import LotsRepository
from ...data.repositories.portfolios_repo import PortfoliosRepository
from ...data.repositories.transactions_repo import TransactionsRepository
from ...external.price_fetcher import PriceFetcher

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


@app.command("vorabpauschale")
def vorabpauschale(
    portfolio_id: int = typer.Argument(..., help="Portfolio ID"),
    year: int = typer.Option(datetime.now().year - 1, "--year", "-y", help="Tax year"),
):
    """Calculate Vorabpauschale for accumulating ETFs (§ 18 InvStG)."""
    p = portfolios_repo.get_by_id(portfolio_id)
    if not p:
        console.print(f"[red]Portfolio {portfolio_id} not found[/red]")
        raise typer.Exit(1)

    basiszins = BASISZINS.get(year, Decimal("0"))
    if basiszins == Decimal("0"):
        console.print(f"[yellow]Basiszins für {year} = 0% — keine Vorabpauschale fällig.[/yellow]")
        return

    console.print(f"\n[bold]Vorabpauschale {year}[/bold] — {p.name}")
    console.print(f"  Basiszins {year}: [cyan]{basiszins * 100:.2f}%[/cyan]  |  Basisertragsfaktor: {basiszins * Decimal('0.7') * 100:.4f}%\n")
    console.print("[dim]Fetching historical prices (Jan 1 and Dec 31)...[/dim]")

    holdings = holdings_repo.list_by_portfolio(portfolio_id)

    results = []
    for h in holdings:
        if not h.ticker:
            continue

        # Shares held on Jan 1 of the year (sum of buys - sells before Jan 1)
        jan1 = datetime(year, 1, 1)
        txs = tx_repo.list_by_holding(h.id)
        shares_jan1 = Decimal("0")
        for tx in txs:
            tx_date = tx.transaction_date.replace(tzinfo=None) if tx.transaction_date.tzinfo else tx.transaction_date
            if tx_date >= jan1:
                continue
            if tx.transaction_type.value == "buy":
                shares_jan1 += tx.quantity
            elif tx.transaction_type.value == "sell":
                shares_jan1 -= tx.quantity

        if shares_jan1 <= 0:
            continue  # didn't hold this at start of year

        # Fetch prices
        price_jan1 = PriceFetcher.fetch_historical_price(
            h.ticker, f"{year}-01-01", f"{year}-01-10"
        )
        price_dec31 = PriceFetcher.fetch_historical_price(
            h.ticker, f"{year}-12-20", f"{year + 1}-01-05", last=True
        )

        if price_jan1 is None or price_dec31 is None:
            console.print(f"  [yellow]⚠ {h.ticker}: could not fetch historical prices — skipping[/yellow]")
            continue

        # Determine if distributing (had dividends this year)
        is_distributing = any(
            tx.transaction_type.value == "dividend"
            and datetime(year, 1, 1) <= (tx.transaction_date.replace(tzinfo=None) if tx.transaction_date.tzinfo else tx.transaction_date) < datetime(year + 1, 1, 1)
            for tx in txs
        )

        result = PortfolioCalculator.calculate_vorabpauschale(
            ticker=h.ticker,
            isin=h.isin,
            year=year,
            shares_jan1=shares_jan1,
            price_jan1=price_jan1,
            price_dec31=price_dec31,
            teilfreistellung_rate=h.teilfreistellung_rate,
            is_distributing=is_distributing,
        )
        results.append(result)

    if not results:
        console.print("[yellow]Keine Positionen am 01.01. gehalten — keine Vorabpauschale.[/yellow]")
        return

    # Table
    table = Table(title=f"Vorabpauschale {year} — {p.name}")
    table.add_column("Ticker", style="bold")
    table.add_column("Anteile 01.01", justify="right")
    table.add_column("Kurs 01.01 €", justify="right")
    table.add_column("Kurs 31.12 €", justify="right")
    table.add_column("Zuwachs/Anteil €", justify="right")
    table.add_column("Basisertrag/Anteil €", justify="right")
    table.add_column("Vorabpauschale €", justify="right")
    table.add_column("TFS%", justify="right")
    table.add_column("Steuerpflichtig €", justify="right")
    table.add_column("Typ", justify="center")

    total_vp = Decimal("0")
    total_taxable = Decimal("0")

    for r in results:
        zuwachs_color = "green" if r.fondszuwachs_per_share > 0 else "red"
        typ = "[dim]Dist.[/dim]" if r.is_distributing else "Acc."
        tfs_str = f"{r.tfs_rate * 100:.0f}%" if r.tfs_rate > 0 else "—"
        table.add_row(
            r.ticker,
            f"{r.shares_jan1:,.4f}",
            f"{r.price_jan1:,.4f}",
            f"{r.price_dec31:,.4f}",
            f"[{zuwachs_color}]{r.fondszuwachs_per_share:+,.4f}[/{zuwachs_color}]",
            f"{r.basisertrag_per_share:,.4f}",
            f"[bold]€{r.vorabpauschale:,.2f}[/bold]",
            tfs_str,
            f"€{r.taxable_vp:,.2f}",
            typ,
        )
        total_vp += r.vorabpauschale
        total_taxable += r.taxable_vp

    console.print(table)

    # Tax estimate on total taxable VP
    tax_info = PortfolioCalculator.calculate_german_tax(max(total_taxable, Decimal("0")))

    console.print(f"\n  Vorabpauschale gesamt:        [bold]€{total_vp:,.2f}[/bold]")
    if total_vp > total_taxable:
        console.print(f"  Teilfreistellung-exempt:      −€{total_vp - total_taxable:,.2f}")
    console.print(f"  Steuerpflichtig (nach TFS):   €{total_taxable:,.2f}")
    console.print(f"  Freistellungsauftrag genutzt: €{tax_info.freistellungsauftrag_used:,.2f}")
    console.print(f"  Steuerpflichtiger Betrag:     €{tax_info.taxable_gain:,.2f}")
    tax_color = "red" if tax_info.total_tax > 0 else "green"
    console.print(f"  Est. Steuer (Abgeltung+Soli): [{tax_color}]€{tax_info.total_tax:,.2f}[/{tax_color}]")
    console.print(f"  Fälligkeit:                   [dim]Januar {year + 1} (bereits abgerechnet)[/dim]")

    if any(r.is_distributing for r in results):
        console.print("\n  [yellow]⚠ Distributing funds (Dist.) — Ausschüttungen reduzieren die VP.[/yellow]")
        console.print("  [dim]Tatsächliche VP = max(0, Basisertrag − Ausschüttungen/Anteil). Wert oben ist Obergrenze.[/dim]")
    console.print()

    # Save to cache so the dashboard can read it without fetching prices
    from ...data.database import get_db
    db = get_db()
    db.conn.execute(
        """INSERT INTO vorabpauschale_cache
               (portfolio_id, year, total_vp, tfs_exempt, taxable_vp, fsa_used, computed_at)
           VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(portfolio_id, year) DO UPDATE SET
               total_vp=excluded.total_vp, tfs_exempt=excluded.tfs_exempt,
               taxable_vp=excluded.taxable_vp, fsa_used=excluded.fsa_used,
               computed_at=excluded.computed_at""",
        (portfolio_id, year, str(total_vp), str(total_vp - total_taxable),
         str(total_taxable), str(tax_info.freistellungsauftrag_used)),
    )
    db.conn.commit()
    console.print(f"  [dim]✓ Cached — dashboard will show VP {year} FSA usage[/dim]\n")
