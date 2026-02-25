# Portfolio Tracker

A CLI tool for tracking ETF portfolios with full German tax support — Abgeltungssteuer, Teilfreistellung, Vorabpauschale, and FIFO cost basis. Built for Trade Republic users with German tax residency.

```
pt stats summary 1
```
```
╭─────────────────── Portfolio A — Trade Republic ───────────────────╮
│  Holdings value   €24,831.40     Cash balance       €2,648.41      │
│  Total value      €27,479.81     Cost basis        €21,200.00      │
│  Unrealized P&L   +€3,631.40     Return                +17.1%      │
╰────────────────────────────────────────────────────────────────────╯
```

---

## Features

- **Full transaction history** — buys, sells, dividends with FIFO lot tracking
- **German tax engine** — Abgeltungssteuer (25%) + Solidaritätszuschlag (5.5%), Freistellungsauftrag, Teilfreistellung per ETF type
- **Vorabpauschale calculator** — annual prepayment tax for accumulating ETFs (§ 18 InvStG)
- **Realized gains** — per-sell gain with FIFO lot matching and TFS applied
- **Rebalancing** — set target allocations by ISIN or asset type, get trade suggestions
- **Price history** — automatic fetching via yfinance for European ETFs (`.DE`, `.L`, `.AS`…)
- **Web dashboard** — offline single-page app with donut charts, tax summary, and Markdown export
- **Cash tracking** — full cash flow ledger (top-ups, buys, sells, dividends, fees)
- **Revolut CSV import** — one-command import of full transaction history

---

## Setup

**Requirements:** Python 3.10+

```bash
git clone https://github.com/flash286/portfolio-tracker.git
cd portfolio-tracker

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -e .
```

Verify:
```bash
pt --help
```

### First-run configuration

Run the interactive setup wizard to configure your tax profile:

```bash
pt setup run
```

It will ask:
- Your name (optional, shown in dashboard)
- Tax country (Germany or other)
- Zusammenveranlagung (joint filing → €2,000 FSA vs. €1,000 single)
- Kirchensteuer (church tax — usually no)
- Preferred exchange suffix for Yahoo Finance (`.DE` for Xetra, `.L` for LSE, etc.)
- Portfolio currency (EUR, USD, GBP, CHF)

Settings are saved to `config.json` at the project root and read by all commands. Re-run at any time to update.

---

## Importing from Revolut

Revolut Invest / Robo-Advisor lets you export your full transaction history as CSV.

### Step 1 — Export from Revolut

1. Open **Revolut app** → Investments → your portfolio
2. Tap the **···** menu → **Export transactions**
3. Download two files:
   - **Transactions CSV** — all buys, dividends, cash top-ups, and fees
   - **P&L CSV** — realized gains with ISIN details (recommended for ISIN enrichment)

### Step 2 — Run the import

```bash
pt import revolut data/revolut_transactions.csv --pnl data/revolut_pnl.csv
```

Output:
```
Importing revolut_transactions.csv…

╭─────────────────────────────── Import result ────────────────────────────────╮
│                                                                              │
│   Portfolio                 Revolut (ID 1)                                   │
│                                                                              │
│   Holdings created                       8                                   │
│   Holdings reused                        0                                   │
│                                                                              │
│   Buys imported                         56                                   │
│   Buys skipped (dup)                     0                                   │
│   Dividends imported                    42                                   │
│   Dividends skipped (dup)                0                                   │
│   Cash rows imported                   146                                   │
│   Cash rows skipped (dup)                0                                   │
│                                                                              │
╰──────────────────────────────────────────────────────────────────────────────╯

Done. Run pt holdings list to verify.
```

The import is **idempotent** — re-running on the same file skips duplicates:

```bash
pt import revolut data/revolut_transactions.csv   # all rows skipped, 0 new inserts
```

Use `--dry-run` to validate without writing to the database:

```bash
pt import revolut data/revolut_transactions.csv --dry-run
```

### Options

```
pt import revolut <tx_csv>
  --pnl <file>              P&L CSV for ISIN enrichment (recommended)
  --portfolio-name / -n     Portfolio name to create or reuse (default: Revolut)
  --portfolio-id / -p       Use an existing portfolio by ID
  --dry-run / -d            Validate without writing to DB
```

### Ticker registry

All 8 standard Revolut Robo-Advisor ETFs are pre-configured in `src/portfolio_tracker/importers/registry.py`. If your export contains unknown tickers the importer will warn you and suggest the manual add command:

```bash
pt holdings add <portfolio_id> <ISIN> etf --ticker MYTICKER --tfs-rate 0.3
```

Or add the ticker to `ETF_REGISTRY` in `importers/registry.py`.

**Teilfreistellung rates** (§ 20 InvStG):
| Fund type | TFS rate | Condition |
|-----------|----------|-----------|
| Equity ETF (Aktienfonds) | 30% | >51% equities |
| Mixed fund (Mischfonds) | 15% | 25–51% equities |
| Bond ETF (Rentenfonds) | 0% | <25% equities |

---

## Manual Portfolio Setup

If you prefer to enter data manually (e.g., for Trade Republic):

```bash
# Create a portfolio
pt portfolio create "Portfolio A"

# Add holdings (ISIN is the primary identifier)
pt holdings add 1 IE00BK5BQT80 etf \
    --name "Vanguard FTSE All-World" \
    --ticker VWCE \
    --tfs-rate 0.3

# Record a buy transaction
pt tx buy 1 --qty 10 --price 115.42 --date 2025-01-15

# Deposit cash
pt cash add 1 top_up 1000 --date 2025-01-15 --note "January top-up"

# Set target allocation
pt rebalance target 1 --isin IE00BK5BQT80 --pct 70
pt rebalance target 1 --isin IE00BMC38736 --pct 15
```

---

## Fetching Prices

```bash
# Fetch current prices for all holdings in portfolio 1
pt prices fetch 1

# View price history for a specific holding
pt prices history <holding_id>
```

yfinance is used for price lookups. European ETFs require exchange suffixes — the tracker handles this automatically:
1. Checks `TICKER_OVERRIDES` dict in `price_fetcher.py` (known overrides)
2. Tries the ticker as-is
3. Falls back through `.DE` → `.L` → `.AS` → `.PA` → `.MI`

If a ticker doesn't resolve, add it to `TICKER_OVERRIDES` in `src/portfolio_tracker/external/price_fetcher.py`:
```python
TICKER_OVERRIDES = {
    "VWCE": "VWCE.DE",
    "VVSM": "VVSM.DE",
    # ...
}
```

---

## Portfolio Statistics

```bash
pt stats summary 1         # P&L, allocation, tax estimate
pt stats allocation 1      # breakdown by asset type
```

The tax estimate in `summary` applies:
1. Weighted Teilfreistellung across holdings
2. Freistellungsauftrag from `config.json`
3. Abgeltungssteuer 25% + Soli 5.5%

This is a **hypothetical** estimate (as if you sold everything today). Actual tax is calculated per transaction.

---

## Tax Commands

### Realized gains

```bash
pt tax realized 1 --year 2025
```

Shows all sell transactions for the year with:
- FIFO-matched cost basis per lot
- Teilfreistellung applied per holding
- Freistellungsauftrag deducted
- Estimated Abgeltungssteuer + Soli

### FIFO tax lots

```bash
pt tax lots <holding_id>
```

Shows individual cost lots (acquired date, quantity, cost/unit, remaining) and how they're consumed FIFO when you sell.

### Vorabpauschale

Accumulating ETFs owe an annual prepayment tax even without a sale (§ 18 InvStG). Calculate it after year-end prices are available:

```bash
pt tax vorabpauschale 1 --year 2025
```

This:
1. Reconstructs shares held on Jan 1 from transaction history
2. Fetches Jan 1 and Dec 31 prices via yfinance
3. Calculates: `Basisertrag = Kurs_01.01 × Basiszins × 0.7`
4. `Vorabpauschale = min(Basisertrag, Fondszuwachs) × Anteile`
5. Applies Teilfreistellung and Freistellungsauftrag
6. Caches the result so the dashboard shows FSA usage

**Basiszins** (published by BMF each January):
| Year | Basiszins |
|------|-----------|
| 2023 | 2.55% |
| 2024 | 2.29% |
| 2025 | 2.53% |

Run this command once in January after the previous year's prices are final. The result is cached in `vorabpauschale_cache` and shown in the dashboard Tax Summary.

---

## Rebalancing

```bash
# View targets vs current allocation
pt rebalance check 1

# Suggest trades to rebalance with €1,000 new investment
pt rebalance suggest 1 --amount 1000

# Execute the suggested trades (records transactions + cash flows)
pt rebalance execute 1 --amount 1000
```

Set targets by ISIN (recommended) or asset type:
```bash
pt rebalance target 1 --isin IE00BK5BQT80 --pct 70   # VWCE 70%
pt rebalance target 1 --isin IE00BMC38736 --pct 15   # VVSM 15%
pt rebalance target 1 --isin IE00BYZK4776 --pct 10   # HEAL 10%
pt rebalance target 1 --isin IE00BG47KH54 --pct 5    # VAGF  5%
```

---

## Web Dashboard

```bash
pt dashboard open 1
```

Opens an offline HTML dashboard in your browser with:
- Portfolio value, P&L, and allocation donut chart
- Holdings table with Teilfreistellung rates and deviation badges
- Tax Summary card (Vorabpauschale FSA usage, TFS exemption, Abgeltungssteuer estimate)
- Realized Gains section (current year sells, conditional)
- Target vs. Actual allocation bars
- **Copy as Markdown** button — exports a full portfolio snapshot for AI review

To save as a file instead of opening:
```bash
pt dashboard open 1 --output /tmp/portfolio.html
```

---

## Cash Management

```bash
pt cash balance 1          # current cash balance
pt cash history 1          # full cash flow ledger
pt cash add 1 top_up 500   # manually add a top-up
```

Cash transaction types: `top_up`, `withdrawal`, `buy`, `sell`, `dividend`, `fee`.

Buy/sell transactions automatically create corresponding cash entries. Balance = SUM of all cash flows.

---

## Full CLI Reference

```
pt portfolio  create|list|show|delete
pt holdings   add|list|remove
pt tx         buy|sell|list
pt prices     fetch|history
pt stats      summary|allocation
pt rebalance  target|check|suggest|execute
pt cash       balance|history|add
pt tax        realized|lots|vorabpauschale
pt import     revolut|tr
pt dashboard  open
pt setup      run
```

---

## Project Structure

```
src/portfolio_tracker/
├── cli/commands/       # Typer CLI commands
├── core/               # Business logic
│   ├── calculator.py   # P&L, Abgeltungssteuer, Vorabpauschale
│   ├── rebalancer.py   # Deviation check, trade suggestions
│   ├── models.py       # Dataclasses
│   └── config.py       # AppConfig (config.json)
├── data/               # SQLite + repositories (one per table)
├── importers/          # Broker CSV importers
│   ├── base.py         # ImportResult + BaseImporter ABC
│   ├── registry.py     # ETF_REGISTRY (ticker → ISIN/TFS)
│   └── revolut.py      # RevolutImporter
└── external/
    └── price_fetcher.py  # yfinance with European ETF suffix handling

scripts/
└── simulate_portfolios.py  # Portfolio simulation / backtesting

data/                   # CSV exports (gitignored — personal data)
portfolio.db            # SQLite database (gitignored — personal data)
config.json             # User config (gitignored — personal data)
```

---

## Stack

Python 3.10+, [Typer](https://typer.tiangolo.com), [Rich](https://github.com/Textualize/rich), SQLite, [yfinance](https://github.com/ranaroussi/yfinance)

---

## License

MIT — see [LICENSE](LICENSE).
