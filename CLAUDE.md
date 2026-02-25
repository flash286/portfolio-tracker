# Portfolio Tracker — Claude Instructions

## Project Overview

Investment portfolio tracker CLI for managing holdings, transactions, cash balance, statistics, and rebalancing. Built for European ETF investors with German tax residency.

## Tech Stack

- **Python 3.10+** with **Typer** CLI framework
- **SQLite** database (stored at project root: `portfolio.db`)
- **yfinance** for stock/ETF/bond prices (European ETFs need `.DE` suffix)
- **Rich** for terminal output formatting
- No external frontend dependencies — dashboard is vanilla HTML/JS/SVG

## Project Structure

```
src/portfolio_tracker/
├── cli/
│   ├── main.py                  # Typer app + command group registration
│   └── commands/
│       ├── cash.py              # pt cash balance|history|add
│       ├── dashboard.py         # pt dashboard open (web UI)
│       ├── holdings.py          # pt holdings add|list|remove
│       ├── import_cmd.py        # pt import revolut|tr
│       ├── portfolio.py         # pt portfolio create|list|show|delete
│       ├── prices.py            # pt prices fetch|history
│       ├── rebalance.py         # pt rebalance target|check|suggest|execute
│       ├── setup.py             # pt setup run (interactive config wizard)
│       ├── stats.py             # pt stats summary|allocation
│       ├── tax.py               # pt tax realized|lots|vorabpauschale
│       └── transactions.py      # pt tx buy|sell|list
├── core/
│   ├── models.py                # Dataclasses: Portfolio, Holding, Transaction, CashTransaction, etc.
│   ├── calculator.py            # PortfolioCalculator — thin delegation wrapper (see Tax & Finance Engine)
│   ├── rebalancer.py            # Rebalancer (deviation check, trade suggestions)
│   ├── config.py                # AppConfig — reads config.json
│   ├── exceptions.py
│   ├── tax/                     # Pure tax functions (no DB/IO)
│   │   ├── __init__.py          # calculate_german_tax() orchestrator + re-exports
│   │   ├── abgeltungssteuer.py  # ABGELTUNGSSTEUER_RATE, SOLI_RATE, calculate_*()
│   │   ├── teilfreistellung.py  # TFS_RATES, apply_teilfreistellung(), weighted_portfolio_tfs()
│   │   ├── freistellungsauftrag.py  # DEFAULT_FSA_*, apply_freistellungsauftrag()
│   │   └── vorabpauschale.py    # BASISZINS, VorabpauschaleResult, calculate_vorabpauschale()
│   └── finance/                 # Pure portfolio math (no DB/IO)
│       ├── __init__.py          # re-exports
│       └── returns.py           # total_value(), total_cost_basis(), total_unrealized_pnl(), allocation_by_*()
├── data/
│   ├── database.py              # SQLite schema + connection (get_db, _find_project_root)
│   └── repositories/
│       ├── portfolios_repo.py
│       ├── holdings_repo.py
│       ├── transactions_repo.py
│       ├── prices_repo.py
│       ├── targets_repo.py
│       └── cash_repo.py         # Cash balance tracking
├── importers/
│   ├── base.py                  # ImportResult dataclass + BaseImporter ABC
│   ├── registry.py              # ETF_REGISTRY (ticker → ISIN/TFS, 30 entries)
│   └── revolut.py               # RevolutImporter
└── external/
    └── price_fetcher.py         # yfinance with TICKER_OVERRIDES + exchange suffix fallback

scripts/
└── simulate_portfolios.py       # Portfolio simulation / backtesting

data/                            # CSV exports (gitignored — personal data)
portfolio.db                     # SQLite database (gitignored — personal data)
config.json                      # User config (gitignored — personal data)
```

## Database

SQLite at project root (`portfolio.db`). **Not tracked in git**
(contains real financial data — gitignored).

### Tables
- `portfolios` — name, description
- `holdings` — per-portfolio, keyed by ISIN, with ticker for yfinance
- `transactions` — buy/sell/dividend per holding
- `lots` — FIFO cost lots per holding
- `cash_transactions` — portfolio-level cash flows (top_up, withdrawal, fee, dividend, buy, sell)
- `price_history` — historical prices per holding
- `target_allocations` — per-portfolio target % by asset type or ISIN
- `vorabpauschale_cache` — cached annual prepayment tax results

### DB Path Resolution
`_find_project_root()` walks up from `database.py` looking for `pyproject.toml`. The DB lives next to it. This makes it work correctly from venv, scripts, or any subdirectory.

## Key Design Decisions

- **Repository pattern**: Each table has its own repo class in `data/repositories/`
- **Decimal everywhere**: Financial calculations use `Decimal`, not `float`
- **EUR-centric**: All prices and values in EUR
- **German tax model**: Abgeltungssteuer (25%) + Soli (5.5%), Freistellungsauftrag configured via `config.json`
- **Asset types**: stock, etf, crypto, bond (enum `AssetType`)
- **Cash is first-class**: Every buy/sell/dividend/fee creates a `cash_transactions` record. Cash balance = SUM(amount) from cash_transactions for the portfolio.
- **ISINs as primary identifiers**: Tickers are secondary, used only for yfinance lookups.
- **Dashboard**: Single-file vanilla HTML/JS with SVG donut charts. No React/CDN — everything inline. Generated by `dashboard.py` and opened in browser via `tempfile`.

## European ETF Price Fetching

yfinance requires exchange suffixes for European ETFs. The `price_fetcher.py` handles this:

1. **TICKER_OVERRIDES** dict maps known tickers to Yahoo symbols (e.g., `VWCE` → `VWCE.DE`)
2. If not in overrides, tries ticker as-is
3. Falls back to trying `.DE`, `.L`, `.AS`, `.PA`, `.MI` suffixes
4. Full error handling — never crashes on bad tickers

## Cash Balance System

Cash transactions are stored in `cash_transactions` table with types:
- `top_up` — money deposited (positive)
- `withdrawal` — money withdrawn (negative)
- `buy` — cash spent on purchases (negative)
- `sell` — cash received from sales (positive)
- `dividend` — cash received from dividends (positive)
- `fee` — management fees (negative)

Balance = `SUM(amount)` — positive means cash available, negative means overdrawn.

Cash is displayed in: `pt portfolio show`, `pt stats summary`, `pt holdings list` (footer), `pt rebalance suggest` (available/remaining), `pt tx buy/sell` (after-trade balance), and the web dashboard.

When adding a buy/sell transaction via `pt tx buy|sell`, the corresponding cash_transaction is created automatically. Same for `pt rebalance execute`.

## CLI Command Reference

```bash
pt portfolio create|list|show|delete    # Portfolio CRUD (show includes cash + total value)
pt holdings add|list|remove             # Holdings management (list shows totals + cash footer)
pt tx buy|sell|list                     # Record transactions (auto-updates cash, shows balance after)
pt prices fetch|history                 # Fetch prices via yfinance
pt stats summary|allocation             # Portfolio stats + German tax calc (summary includes cash)
pt rebalance target|check|suggest|execute  # Rebalancing (suggest shows cash impact, execute records cash)
pt cash balance|history|add             # Cash balance management
pt tax realized|lots|vorabpauschale     # Tax calculations (FIFO lots, Vorabpauschale)
pt import revolut|tr                    # Import broker CSV exports
pt dashboard open [--output FILE]       # Open web dashboard in browser
pt setup run                            # Interactive configuration wizard
```

## Running

```bash
pip install -e .
pt setup run    # configure tax profile on first run
pt --help
```

## Tax & Finance Engine

All math lives in pure, DB-free modules under
`core/tax/` and `core/finance/`. Import them
directly for new code — do NOT go through
`PortfolioCalculator`.

```python
# Preferred — direct import
from portfolio_tracker.core.tax import calculate_german_tax
from portfolio_tracker.core.tax.vorabpauschale import (
    BASISZINS, calculate_vorabpauschale,
)
from portfolio_tracker.core.finance.returns import (
    total_value, allocation_by_type,
)
```

`PortfolioCalculator` in `calculator.py` is a
**thin backward-compatible delegation wrapper**
kept only for legacy callers. All its methods
just call the pure functions above. New code
should import the pure functions directly.

### German tax pipeline (in order)

1. **Teilfreistellung** (§20 InvStG) — partial
   exemption for investment funds. Equity ETF:
   30%, mixed fund: 15%, bond/stock/crypto: 0%.
2. **Freistellungsauftrag** (§20 Abs.9 EStG) —
   annual allowance (€1 000 single / €2 000
   joint), read from `config.json`.
3. **Abgeltungssteuer** (§32d EStG) — 25% flat
   tax on remaining gain.
4. **Solidaritätszuschlag** (§4 SolZG) — 5.5%
   surcharge on Abgeltungssteuer.

### Vorabpauschale (§18 InvStG)

Annual prepayment tax on accumulating ETFs.

```
Basisertrag/share = price_Jan1 × Basiszins × 0.7
VP/share          = min(Basisertrag, Fondszuwachs)
Vorabpauschale    = VP/share × shares
Taxable VP        = Vorabpauschale × (1 − TFS_rate)
```

`BASISZINS` dict in `vorabpauschale.py` holds
annual BMF-published rates. Years 2020–2022 are
`0` (no VP owed). 2023 = 2.55%, 2024 = 2.29%,
2025 = 2.53%.

## AI Compatibility

Claude Code Skills in `.claude/skills/` provide AI-powered workflows built on top of the CLI.
Invoke with `/skill-name` in Claude Code.

### Available Skills

| Command | Description |
|---------|-------------|
| `/portfolio import <file>` | Import transactions from any broker CSV |
| `/portfolio summary` | Portfolio overview, allocation, tax snapshot |
| `/portfolio` | Show menu (import or summary) |

Skill file: `.claude/skills/portfolio/SKILL.md`

### AI as Universal Importer

`/portfolio import` lets an AI handle any broker export without writing a custom importer:

```
1. AI reads the CSV, infers column meaning
2. For each deposit/withdrawal → pt cash add <pid> <amount> --type top_up|withdrawal
3. For each buy/sell:
   a. pt holdings list <pid>  — check if holding exists
   b. pt holdings add <pid> <isin> <type> ...  — create if missing
   c. pt tx buy|sell <holding_id> <qty> <price> --date YYYY-MM-DD
4. For dividends → pt cash add <pid> <amount> --type dividend
```

Works for any broker that exports buy/sell history (Trading 212, Interactive Brokers, etc.)
No Python code per broker — prompt-driven column mapping.

**Note:** Unlike `pt import revolut`, the AI import is NOT idempotent. Running twice creates
duplicate transactions. The skill includes a dry-run summary step before recording anything.

## Importer Architecture

`importers/BaseImporter` ABC wraps `_run_import()` atomically:
- Dry-run: writes then rolls back, returns result with counts
- Idempotency: `source_id = sha256(raw_row)[:16]` prefixed with broker name, stored in `transactions.source_id` and `cash_transactions.source_id` with `INSERT OR IGNORE` + unique partial index

Ticker resolution priority (Revolut importer):
1. `ETF_REGISTRY` (30 pre-verified tickers)
2. P&L CSV (for distributing ETFs — contains ISIN)
3. `user_registry.json` (saved from previous interactive sessions)
4. Interactive Rich prompt (saves answer to `user_registry.json`)

## Testing

### Layout

```
tests/
├── unit/
│   ├── test_calculator.py       # legacy PortfolioCalculator tests
│   ├── test_finance/
│   │   └── test_returns.py      # pure finance functions
│   └── test_tax/
│       ├── test_abgeltungssteuer.py
│       ├── test_freistellungsauftrag.py
│       ├── test_teilfreistellung.py
│       └── test_vorabpauschale.py
└── integration/
    └── test_end_to_end.py       # full import → prices → calc → tax
```

Run all tests:

```bash
pytest                           # all 226
pytest tests/unit/test_tax/      # tax only
pytest tests/integration/        # e2e only
```

### Critical gotcha: prices are NOT auto-joined

`HoldingsRepository.list_by_portfolio()` returns
`Holding` objects with `current_price = None`.

**Always use the helper method** — never write
a manual price-loading loop:

```python
# CORRECT
holdings = holdings_repo.list_by_portfolio_with_prices(pid)

# WRONG — duplicates internal logic
holdings = holdings_repo.list_by_portfolio(pid)
for h in holdings:
    latest = prices_repo.get_latest(h.id)
    if latest:
        h.current_price = latest.price
```

Forgetting prices causes `total_value()`,
`allocation_by_type()`, and `weighted_portfolio_tfs()`
to silently return `0` / `{}`.

Commands that display values/P&L/allocation
must use `list_by_portfolio_with_prices()`:
`stats.py`, `rebalance.py`, `portfolio.py`,
`holdings.py`, `dashboard.py`

## Linting

**Tool:** `ruff` (line length: 120)

```bash
# Check — scope is src/ and tests/ only
python -m ruff check src/ tests/

# Auto-fix safe issues
python -m ruff check --fix src/ tests/
```

- `scripts/simulate_portfolios.py` has known
  legacy lint issues — do NOT fix unless asked
- For unavoidable long lines: `# noqa: E501`

## Repository Quick Reference

```python
# Generic INSERT (skips id, created_at,
# updated_at — defined in _insert_skip)
repo._insert(obj)

# Idempotent INSERT OR IGNORE with source_id
repo._insert_with_source_id(
    obj, source_id,
    extra_fields={"computed_col": value}
)

# UPDATE by obj.id (same skip set)
repo.save(obj)
```

`_insert_skip` per repo:
- Default: `{"id", "created_at", "updated_at"}`
- `HoldingsRepository`: also skips
  `"current_price"` (model-only field)

`Transaction.total_value` is a `@property`
(not a dataclass field) but required as DB
column — pass via
`extra_fields={"total_value": ...}`.

## Code Review Quality Gate

For quality-critical changes, spawn three
independent parallel agents with **zero context**:

1. **Fintech calculations** — Decimal usage,
   tax math, FIFO logic correctness
2. **Security** — input validation, injection,
   sensitive data (local-only app)
3. **Code quality** — duplication, type hints,
   error handling, consistency

Repeat until all three report no new issues.
Typical: 2–3 rounds.

Common issues to watch for:
- `float` in financial math (must be `Decimal`)
- Manual price-loading loops (use helper above)
- Silent failures without user-visible warnings
- Imprecise type hints (`object` vs
  `Optional[Decimal]`)

## Conventions

- Code and comments in English
- Commit messages in English
- All CLI output uses Rich formatting
- Prices displayed to 4 decimal places, values to 2
- Holdings sorted by value descending in most views
- German tax terms in dashboard have English translations in parentheses

## Security & Privacy

### Gitignored files (never commit)
- `portfolio.db` — real transaction history
- `*.bak` — database backups
- `config.json` — user name + tax settings
- `user_registry.json` — custom ticker→ISIN mappings
- `data/*.csv` — raw broker exports

### How to purge a file from git history
```bash
pip install git-filter-repo
git filter-repo --path <file> --invert-paths --force
git remote add origin <url>   # filter-repo removes remote
git push --force origin master
```

### Configuration
User-specific settings (FSA amount, tax rates, name)
live in `config.json` at project root.
Read via `get_config()` in `core/config.py`.
Set interactively with `pt setup run`.

Dashboard reads `freistellungsauftrag` from config
(not hardcoded) — passed as `D.freistellungsauftrag`
in the JSON data blob.

## Future Plans

See `PLANS.md` for detailed roadmap.
