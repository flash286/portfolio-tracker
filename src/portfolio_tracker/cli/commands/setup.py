"""Interactive setup wizard — pt setup."""

from decimal import Decimal

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, FloatPrompt, Prompt
from rich.table import Table

from ...core.config import AppConfig, get_config, save_config

app = typer.Typer(help="Interactive setup wizard")
console = Console()


def _say(text: str, style: str = ""):
    """Bot 'speaks'."""
    console.print(f"\n  {text}" if not style else f"\n  [{style}]{text}[/{style}]")


def _ask(prompt: str, choices: list[str] | None = None, default: str = "") -> str:
    """Single-line prompt with optional choices displayed."""
    if choices:
        numbered = "  ".join(f"[bold]{i+1}[/bold]. {c}" for i, c in enumerate(choices))
        console.print(f"    {numbered}")
    return Prompt.ask("  [cyan]>[/cyan]", default=default, console=console)


def _pick(choices: list[str]) -> int:
    """Pick from numbered list. Returns 0-based index."""
    while True:
        raw = Prompt.ask("  [cyan]>[/cyan]", console=console)
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(choices):
                return idx
        except ValueError:
            pass
        console.print("    [red]Enter a number from the list[/red]")


def _yesno(prompt: str, default: bool = True) -> bool:
    console.print(f"\n  {prompt}")
    return Confirm.ask("  [cyan]>[/cyan]", default=default, console=console)


@app.command("run")
def run_setup():
    """Run the interactive setup wizard."""
    existing = get_config()
    has_config = (existing.user_name or existing.country != "DE"
                  or existing.freistellungsauftrag != Decimal("2000"))

    console.print()
    console.print(Panel.fit(
        "[bold]Portfolio Tracker — Setup[/bold]",
        border_style="cyan",
        padding=(0, 4),
    ))

    greeting = "Welcome back!" if has_config else "Welcome!"
    _say(f"{greeting} Answer a few questions to configure your portfolio tracker.")
    if has_config:
        _say("Current settings are shown as defaults. Press Enter to keep them.")

    # ── Name (optional) ───────────────────────────────────────────────────────
    console.print("\n  Your name? (optional, shown in the dashboard greeting)")
    name = Prompt.ask("  [cyan]>[/cyan]", default=existing.user_name or "", console=console)

    # ── Country ───────────────────────────────────────────────────────────────
    _say("In which country do you pay taxes?")
    COUNTRIES = ["Germany (DE)", "Other"]
    for i, c in enumerate(COUNTRIES, 1):
        console.print(f"    [bold]{i}.[/bold] {c}")
    country_idx = _pick(COUNTRIES)
    country = "DE" if country_idx == 0 else "OTHER"

    if country == "DE":
        _say("Germany: Abgeltungssteuer [bold]25%[/bold] + Solidaritätszuschlag [bold]5.5%[/bold].", "green")
        abgeltung = Decimal("0.25")
        soli = Decimal("0.055")
    else:
        _say("Other country — enter your tax rates manually.")
        abgeltung = Decimal(str(FloatPrompt.ask("  Capital gains tax rate (e.g. 0.25)", console=console)))
        soli = Decimal("0")
        country = "OTHER"

    # ── FSA ───────────────────────────────────────────────────────────────────
    if country == "DE":
        _say("Do you file taxes jointly with a spouse (Zusammenveranlagung)?")
        _say("[dim]Joint filing doubles the Freistellungsauftrag from €1,000 to €2,000.[/dim]")
        married = _yesno("Zusammenveranlagung", default=existing.freistellungsauftrag >= Decimal("2000"))
        suggested_fsa = 2000.0 if married else 1000.0
        if married:
            _say("Freistellungsauftrag: €2,000 (joint).", "green")
        else:
            _say("Freistellungsauftrag: €1,000 (single).", "green")

        _say("If you filed a different amount with your bank, enter it here. Otherwise press Enter.")
        fsa_raw = Prompt.ask("  [cyan]>[/cyan] FSA", default=str(int(suggested_fsa)), console=console)
        fsa = Decimal(fsa_raw)
    else:
        _say("Tax-free allowance (Freistellungsauftrag equivalent, if applicable):")
        fsa_raw = Prompt.ask("  [cyan]>[/cyan]", default="0", console=console)
        fsa = Decimal(fsa_raw)

    # ── Kirchensteuer ─────────────────────────────────────────────────────────
    kirche = False
    if country == "DE":
        _say("Do you pay Kirchensteuer (church tax)?")
        _say("[dim]No if you are not a church member or have filed a Kirchenaustritt.[/dim]")
        kirche = _yesno("Kirchensteuer", default=existing.kirchensteuer)
        if kirche:
            _say("Kirchensteuer noted. Rate depends on your federal state (usually 8–9%).", "yellow")
            _say("[dim]Exact Kirchensteuer calculation is not yet implemented — an estimate will be shown.[/dim]")
        else:
            _say("Kirchensteuer: not applicable.", "green")

    # ── Exchange suffix ────────────────────────────────────────────────────────
    _say("Which exchange suffix to use for ETF/stock price lookups via Yahoo Finance?")
    EXCHANGES = [
        (".DE  — Xetra (recommended for DE residents)", ".DE"),
        (".L   — London Stock Exchange", ".L"),
        (".AS  — Euronext Amsterdam", ".AS"),
        (".PA  — Euronext Paris", ".PA"),
        (".MI  — Borsa Italiana", ".MI"),
    ]
    for i, (label, _) in enumerate(EXCHANGES, 1):
        console.print(f"    [bold]{i}.[/bold] {label}")

    console.print(f"    [dim](current: {existing.default_exchange_suffix})[/dim]")
    ex_idx = _pick(EXCHANGES)
    exchange_suffix = EXCHANGES[ex_idx][1]
    _say(f"Exchange: [bold]{exchange_suffix}[/bold]", "green")

    # ── Currency ──────────────────────────────────────────────────────────────
    _say("Portfolio currency:")
    CURRENCIES = ["EUR", "USD", "GBP", "CHF"]
    for i, c in enumerate(CURRENCIES, 1):
        console.print(f"    [bold]{i}.[/bold] {c}")
    console.print(f"    [dim](current: {existing.currency})[/dim]")
    cur_default = next((i for i, c in enumerate(CURRENCIES) if c == existing.currency), 0)
    cur_raw = Prompt.ask("  [cyan]>[/cyan]", default=str(cur_default + 1), console=console)
    try:
        currency = CURRENCIES[int(cur_raw) - 1]
    except (ValueError, IndexError):
        currency = "EUR"

    # ── AI Analysis (optional) ────────────────────────────────────────────────
    _say("AI Analysis in the dashboard (optional):")
    _say("[dim]Adds a 'Generate Analysis' button — AI reviews your portfolio like a financial advisor.[/dim]")
    AI_PROVIDERS = ["Anthropic (Claude)", "OpenAI (o3)", "Google Gemini", "Skip"]
    for i, p in enumerate(AI_PROVIDERS, 1):
        console.print(f"    [bold]{i}.[/bold] {p}")
    console.print(f"    [dim](current: {existing.ai_provider or 'not configured'})[/dim]")
    ai_idx = _pick(AI_PROVIDERS)
    _PROVIDER_MAP = {0: "anthropic", 1: "openai", 2: "gemini", 3: ""}
    ai_provider = _PROVIDER_MAP[ai_idx]
    ai_api_key = existing.ai_api_key
    ai_model = existing.ai_model

    if ai_provider:
        ai_api_key = Prompt.ask(
            "  [cyan]>[/cyan] API key",
            password=True,
            default=existing.ai_api_key or "",
            console=console,
        )
        _DEFAULT_MODELS = {
            "anthropic": "claude-opus-4-6",
            "openai": "o3",
            "gemini": "gemini-2.5-pro",
        }
        ai_model = Prompt.ask(
            f"  [cyan]>[/cyan] Model (Enter = {_DEFAULT_MODELS[ai_provider]})",
            default=existing.ai_model or "",
            console=console,
        )
        _say(f"AI provider: [bold]{ai_provider}[/bold]", "green")
    else:
        _say("AI Analysis: skipped.", "dim")

    # ── Summary & confirm ─────────────────────────────────────────────────────
    console.print()
    table = Table(box=box.ROUNDED, border_style="cyan", show_header=False, padding=(0, 2))
    table.add_column(style="dim")
    table.add_column(style="bold")
    if name:
        table.add_row("Name", name)
    table.add_row("Country", "Germany (DE)" if country == "DE" else country)
    table.add_row("Freistellungsauftrag", f"€{fsa:,.0f}")
    table.add_row("Abgeltungssteuer", f"{abgeltung * 100:.0f}%")
    table.add_row("Solidaritätszuschlag", f"{soli * 100:.1f}%")
    table.add_row("Kirchensteuer", "yes" if kirche else "no")
    table.add_row("Exchange (Yahoo Finance)", exchange_suffix)
    table.add_row("Currency", currency)
    if ai_provider:
        table.add_row("AI Provider", ai_provider)
        table.add_row("AI Model", ai_model or "(default)")
    console.print(table)

    _say("Save these settings?")
    if not _yesno("", default=True):
        _say("Cancelled. Settings unchanged.", "yellow")
        raise typer.Exit()

    cfg = AppConfig(
        country=country,
        freistellungsauftrag=fsa,
        abgeltungssteuer_rate=abgeltung,
        soli_rate=soli,
        kirchensteuer=kirche,
        currency=currency,
        default_exchange_suffix=exchange_suffix,
        user_name=name,
        ai_provider=ai_provider,
        ai_api_key=ai_api_key,
        ai_model=ai_model,
    )
    save_config(cfg)

    console.print()
    console.print(Panel.fit(
        "[bold green]✓ Settings saved to config.json[/bold green]\n\n"
        "[dim]Run [bold]pt setup run[/bold] again to change.[/dim]",
        border_style="green",
        padding=(0, 2),
    ))
    console.print()
