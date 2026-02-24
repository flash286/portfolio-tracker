"""Interactive setup wizard — pt setup."""

from decimal import Decimal

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, FloatPrompt, Prompt
from rich.table import Table
from rich import box

from ...core.config import AppConfig, get_config, save_config

app = typer.Typer(help="Interactive setup wizard")
console = Console()


def _say(text: str, style: str = ""):
    """Bot 'speaks'."""
    console.print(f"\n  {text}" if not style else f"\n  [{style}]{text}[/{style}]")


def _ask(prompt: str, choices: list[str] | None = None, default: str = "") -> str:
    """Single-line prompt with optional choices displayed."""
    choice_str = ""
    if choices:
        numbered = "  ".join(f"[bold]{i+1}[/bold]. {c}" for i, c in enumerate(choices))
        console.print(f"    {numbered}")
    return Prompt.ask(f"  [cyan]>[/cyan]", default=default, console=console)


def _pick(choices: list[str]) -> int:
    """Pick from numbered list. Returns 0-based index."""
    while True:
        raw = Prompt.ask(f"  [cyan]>[/cyan]", console=console)
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(choices):
                return idx
        except ValueError:
            pass
        console.print("    [red]Введи номер из списка[/red]")


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

    greeting = "Снова привет!" if has_config else "Привет!"
    _say(f"{greeting} Отвечай на вопросы — настрою трекер под тебя.")
    if has_config:
        _say("Текущие настройки показаны в скобках. Enter = оставить.")

    # ── Name (optional) ───────────────────────────────────────────────────────
    console.print("\n  Как тебя зовут? (необязательно, только для приветствия в дашборде)")
    name = Prompt.ask("  [cyan]>[/cyan]", default=existing.user_name or "", console=console)

    # ── Country ───────────────────────────────────────────────────────────────
    _say("В какой стране платишь налоги?")
    COUNTRIES = ["Германия (DE)", "Другая"]
    for i, c in enumerate(COUNTRIES, 1):
        console.print(f"    [bold]{i}.[/bold] {c}")
    country_idx = _pick(COUNTRIES)
    country = "DE" if country_idx == 0 else "OTHER"

    if country == "DE":
        _say("Германия: Abgeltungssteuer [bold]25%[/bold] + Solidaritätszuschlag [bold]5.5%[/bold].", "green")
        abgeltung = Decimal("0.25")
        soli = Decimal("0.055")
    else:
        _say("Другая страна — введи ставки налога вручную.")
        abgeltung = Decimal(str(FloatPrompt.ask("  Ставка налога на прирост капитала (напр. 0.25)", console=console)))
        soli = Decimal("0")
        country = "OTHER"

    # ── FSA ───────────────────────────────────────────────────────────────────
    if country == "DE":
        _say("Подаёшь налоговую декларацию совместно с супругом?")
        _say("[dim]Zusammenveranlagung даёт Freistellungsauftrag €2 000 вместо €1 000.[/dim]")
        married = _yesno("Zusammenveranlagung", default=existing.freistellungsauftrag >= Decimal("2000"))
        suggested_fsa = 2000.0 if married else 1000.0
        if married:
            _say("Freistellungsauftrag: €2 000 (совместный).", "green")
        else:
            _say("Freistellungsauftrag: €1 000 (одиночный).", "green")

        _say(f"Если в банке подал заявление на другую сумму — введи её. Иначе Enter.")
        fsa_raw = Prompt.ask(f"  [cyan]>[/cyan] FSA", default=str(int(suggested_fsa)), console=console)
        fsa = Decimal(fsa_raw)
    else:
        _say("Freistellungsauftrag (налоговый вычет, если применимо):")
        fsa_raw = Prompt.ask("  [cyan]>[/cyan]", default="0", console=console)
        fsa = Decimal(fsa_raw)

    # ── Kirchensteuer ─────────────────────────────────────────────────────────
    kirche = False
    if country == "DE":
        _say("Платишь Kirchensteuer (церковный налог)?")
        _say("[dim]Если не состоишь в церкви или подал Austritt — нет.[/dim]")
        kirche = _yesno("Kirchensteuer", default=existing.kirchensteuer)
        if kirche:
            _say("Kirchensteuer учтена. Ставка зависит от земли (обычно 8–9%).", "yellow")
            _say("[dim]Точный расчёт Kirchensteuer пока не реализован — будет показана оценка.[/dim]")
        else:
            _say("Kirchensteuer: не применяется.", "green")

    # ── Exchange suffix ────────────────────────────────────────────────────────
    _say("Какую биржу использовать для поиска цен ETF/акций через Yahoo Finance?")
    EXCHANGES = [
        (".DE  — Xetra (немецкие ETF, рекомендуется для DE резидентов)", ".DE"),
        (".L   — London Stock Exchange", ".L"),
        (".AS  — Euronext Amsterdam", ".AS"),
        (".PA  — Euronext Paris", ".PA"),
        (".MI  — Borsa Italiana", ".MI"),
    ]
    for i, (label, _) in enumerate(EXCHANGES, 1):
        console.print(f"    [bold]{i}.[/bold] {label}")

    default_ex_idx = next(
        (i for i, (_, suffix) in enumerate(EXCHANGES) if suffix == existing.default_exchange_suffix),
        0,
    )
    console.print(f"    [dim](текущая: {existing.default_exchange_suffix})[/dim]")
    ex_idx = _pick(EXCHANGES)
    exchange_suffix = EXCHANGES[ex_idx][1]
    _say(f"Биржа: [bold]{exchange_suffix}[/bold]", "green")

    # ── Currency ──────────────────────────────────────────────────────────────
    _say("Валюта портфеля:")
    CURRENCIES = ["EUR", "USD", "GBP", "CHF"]
    for i, c in enumerate(CURRENCIES, 1):
        console.print(f"    [bold]{i}.[/bold] {c}")
    console.print(f"    [dim](текущая: {existing.currency})[/dim]")
    cur_default = next((i for i, c in enumerate(CURRENCIES) if c == existing.currency), 0)
    cur_raw = Prompt.ask(f"  [cyan]>[/cyan]", default=str(cur_default + 1), console=console)
    try:
        currency = CURRENCIES[int(cur_raw) - 1]
    except (ValueError, IndexError):
        currency = "EUR"

    # ── Summary & confirm ─────────────────────────────────────────────────────
    console.print()
    table = Table(box=box.ROUNDED, border_style="cyan", show_header=False, padding=(0, 2))
    table.add_column(style="dim")
    table.add_column(style="bold")
    if name:
        table.add_row("Имя", name)
    table.add_row("Страна", "Германия (DE)" if country == "DE" else country)
    table.add_row("Freistellungsauftrag", f"€{fsa:,.0f}")
    table.add_row("Abgeltungssteuer", f"{abgeltung * 100:.0f}%")
    table.add_row("Solidaritätszuschlag", f"{soli * 100:.1f}%")
    table.add_row("Kirchensteuer", "да" if kirche else "нет")
    table.add_row("Биржа (Yahoo Finance)", exchange_suffix)
    table.add_row("Валюта", currency)
    console.print(table)

    _say("Сохранить эти настройки?")
    if not _yesno("", default=True):
        _say("Отменено. Настройки не изменены.", "yellow")
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
    )
    save_config(cfg)

    console.print()
    console.print(Panel.fit(
        f"[bold green]✓ Настройки сохранены в config.json[/bold green]\n\n"
        f"[dim]Запусти [bold]pt setup run[/bold] снова чтобы изменить.[/dim]",
        border_style="green",
        padding=(0, 2),
    ))
    console.print()
