# Portfolio Tracker

[![CI](https://github.com/flash286/portfolio-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/flash286/portfolio-tracker/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

CLI tool for tracking ETF portfolios with full **German tax support** — Abgeltungssteuer, Teilfreistellung, Vorabpauschale, and FIFO cost basis. Designed for European ETF investors with German tax residency.

---

![Dashboard overview](docs/screen%20-2.png)

![Holdings and tax summary](docs/screen%20-1.png)

---

## Features

- **Full transaction history** — buys, sells, dividends with FIFO lot tracking
- **German tax engine** — Abgeltungssteuer (25%) + Soli (5.5%), Freistellungsauftrag, Teilfreistellung per ETF type
- **Vorabpauschale** — annual prepayment tax for accumulating ETFs (§ 18 InvStG)
- **Realized gains** — per-sell gain with FIFO lot matching and TFS applied
- **Rebalancing** — set target allocations by ISIN or asset type, get trade suggestions
- **Price history** — automatic fetching via yfinance for European ETFs (`.DE`, `.L`, `.AS` …)
- **Web dashboard** — offline single-page app with donut charts, tax summary, Markdown export
- **Cash tracking** — full cash flow ledger (top-ups, buys, sells, dividends, fees)
- **Revolut CSV import** — one-command idempotent import of full transaction history

---

## Table of Contents

- [Setup](#setup)
- [Quick start](#quick-start)
- [Revolut import](#revolut-import)
- [Manual portfolio setup](#manual-portfolio-setup)
- [Prices](#prices)
- [Statistics](#statistics)
- [Tax commands](#tax-commands)
- [Rebalancing](#rebalancing)
- [Web dashboard](#web-dashboard)
- [Cash management](#cash-management)
- [CLI reference](#cli-reference)
- [Stack](#stack)

---

## Setup

**Requirements:** Python 3.10+

```bash
git clone https://github.com/flash286/portfolio-tracker.git
cd portfolio-tracker

python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

pip install -e .
pt --help
```

### First-run configuration

```bash
pt setup run
```

The wizard asks for your tax profile (FSA amount, Zusammenveranlagung, church tax, preferred exchange suffix). Settings are saved to `config.json`.

---

## Quick start

```bash
pt portfolio create "My Portfolio"        # → ID 1
pt holdings add 1 IE00BK5BQT80 etf \
    --name "Vanguard FTSE All-World" \
    --ticker VWCE --tfs-rate 0.3
pt tx buy 1 10 115.42 --date 2025-01-15
pt prices fetch 1
pt stats summary 1
```

```
Portfolio: My Portfolio

  Total Cost Basis      €1,154.20
  Holdings Value        €1,282.78
  Cash Balance              €0.00
  Portfolio Value       €1,282.78
  Unrealized P&L     +€128.58 (+11.1%)
```

---

## Revolut import

### Export from Revolut

1. **Revolut app** → Investments → portfolio → **···** → **Export transactions**
2. Download:
   - **Transactions CSV** — buys, dividends, cash flows
   - **P&L CSV** — realized gains with ISIN details (recommended)

### Run the import

```bash
pt import revolut data/revolut_transactions.csv --pnl data/revolut_pnl.csv
```

```
╭──────────── Import result ─────────────╮
│  Portfolio             Revolut (ID 1)  │
│  Holdings created                   8  │
│  Buys imported                     56  │
│  Dividends imported                42  │
│  Cash rows imported               146  │
╰────────────────────────────────────────╯
Done. Run pt holdings list to verify.
```

The import is **idempotent** — re-running on the same file skips all duplicates (SHA-256 deduplication). Use `--dry-run` to validate without writing.

### Options

| Flag | Description |
|------|-------------|
| `--pnl <file>` | P&L CSV for ISIN enrichment (recommended) |
| `--portfolio-name / -n` | Portfolio name to create or reuse |
| `--portfolio-id / -p` | Use an existing portfolio by ID |
| `--dry-run / -d` | Validate without writing to DB |
| `--no-interactive` | Skip prompts for unknown tickers (CI/script mode) |

---

## Manual portfolio setup

```bash
pt portfolio create "Trade Republic"

pt holdings add 1 IE00BK5BQT80 etf --name "VWCE" --ticker VWCE --tfs-rate 0.3
pt holdings add 1 IE00BMC38736 etf --name "VVSM" --ticker VVSM --tfs-rate 0.3

pt tx buy 1 100 115.42 --date 2025-01-15
pt cash add 1 1000 --type top_up --desc "January deposit"
```

---

## Prices

```bash
pt prices fetch 1              # fetch current prices for all holdings
pt prices history <holding_id>
```

yfinance is used for lookups. European ETFs require exchange suffixes — the tracker handles this automatically (tries `.DE` → `.L` → `.AS` → `.PA` → `.MI`).

Add overrides in `src/portfolio_tracker/external/price_fetcher.py`:
```python
TICKER_OVERRIDES = {
    "VWCE": "VWCE.DE",
    ...
}
```

---

## Statistics

```bash
pt stats summary 1         # P&L, allocation, estimated tax
pt stats allocation 1      # breakdown by asset type
```

The tax estimate in `summary` applies Teilfreistellung → Freistellungsauftrag → Abgeltungssteuer + Soli. This is a hypothetical estimate (as if you sold everything today).

---

## Tax commands

### Realized gains

```bash
pt tax realized 1 --year 2025
```

Shows all sells with FIFO-matched cost basis, Teilfreistellung, FSA deduction, and estimated Abgeltungssteuer + Soli.

### FIFO tax lots

```bash
pt tax lots <holding_id>
```

Shows individual cost lots — acquired date, quantity, cost/unit, remaining.

### Vorabpauschale

```bash
pt tax vorabpauschale 1 --year 2024
```

Calculates the annual prepayment tax for accumulating ETFs (§ 18 InvStG):

```
Basisertrag/share = Kurs(Jan 1) × Basiszins × 0.7
Vorabpauschale    = min(Basisertrag, Fondszuwachs) × Anteile
```

**Basiszins** (BMF-published):

| Year | Basiszins |
|------|-----------|
| 2023 | 2.55% |
| 2024 | 2.29% |
| 2025 | 2.53% |

Run once in January after the previous year's prices are final. Results are cached and shown in the dashboard.

---

## Rebalancing

```bash
pt rebalance target 1        # set target allocations interactively
pt rebalance check 1         # show current deviation from targets
pt rebalance suggest 1       # suggest trades with cash impact
pt rebalance execute 1       # execute trades and record transactions
```

---

## Web dashboard

```bash
pt dashboard open 1
pt dashboard open 1 --output /tmp/portfolio.html   # save to file
```

Offline single-page app — no CDN, no network required after opening. Features:
- Portfolio value / P&L / cash cards
- Allocation donut charts (by holding and by type)
- Holdings table with TFS rates and rebalancing deviation badges
- **Tax Summary** — Vorabpauschale FSA usage, TFS exemption, Abgeltungssteuer estimate
- Target vs. Actual allocation bars
- **Copy as Markdown** — exports a full portfolio snapshot for AI review

---

## Cash management

```bash
pt cash balance 1           # current balance
pt cash history 1           # full ledger
pt cash add 1 500 --type top_up
```

Types: `top_up`, `withdrawal`, `buy`, `sell`, `dividend`, `fee`. Buy/sell transactions automatically create matching cash entries.

---

## CLI reference

```
pt portfolio  create | list | show | delete
pt holdings   add | list | remove
pt tx         buy | sell | list
pt prices     fetch | history
pt stats      summary | allocation
pt rebalance  target | check | suggest | execute
pt cash       balance | history | add
pt tax        realized | lots | vorabpauschale
pt import     revolut | tr
pt dashboard  open
pt setup      run
```

---

## Stack

| | |
|---|---|
| Language | Python 3.10+ |
| CLI | [Typer](https://typer.tiangolo.com) + [Rich](https://github.com/Textualize/rich) |
| Database | SQLite (`portfolio.db`) |
| Prices | [yfinance](https://github.com/ranaroussi/yfinance) |
| Dashboard | Vanilla HTML/JS/SVG — no CDN, no build step |

---

## License

[MIT](LICENSE)
