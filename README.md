# Portfolio Tracker

[![CI](https://github.com/flash286/portfolio-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/flash286/portfolio-tracker/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-flash286-FFDD00?style=flat&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/flash286)

Track your ETF portfolio with full **German tax compliance** — Abgeltungssteuer,
Teilfreistellung, Vorabpauschale, FIFO lots — all from the command line.
Built for European ETF investors living in Germany.

> **Designed for:** DE tax residents · EUR-denominated ETF portfolios · buy-and-hold investors
>
> **Not designed for:** US investors, multi-currency portfolios, real-time trading

---

<p align="center">
  <img src="docs/screen%20-2.png" alt="Web dashboard — allocation charts and tax summary" width="900">
  <br><em>Web dashboard — allocation, holdings, tax summary</em>
</p>
<p align="center">
  <img src="docs/screen%20-1.png" alt="CLI — holdings list and stats" width="900">
  <br><em>CLI — pt holdings list and pt stats summary</em>
</p>

---

## Features

- **Portfolio & holdings** — multiple portfolios, buys/sells/dividends, FIFO lots
- **German tax engine** — Abgeltungssteuer (25%) + Soli (5.5%), Teilfreistellung, Freistellungsauftrag
- **Vorabpauschale** — annual prepayment tax for accumulating ETFs (§18 InvStG)
- **Rebalancing** — target allocations by ISIN/type, deviation check, trade suggestions
- **Price fetching** — automatic yfinance lookups for European ETFs (`.DE` `.L` `.AS` …)
- **Cash tracking** — full ledger: top-ups, buys, sells, dividends, fees
- **Performance history** — Time-Weighted Return over 1m/3m/6m/1y/2y/all, auto-fetches historical prices
- **Revolut import** — idempotent one-command CSV import
- **Web dashboard** — tabbed SPA: allocation charts, sortable holdings table, P&L bars, FSA progress, tax summary, rebalancing, AI Analysis
- **AI Analysis** — one-click portfolio review by Claude / GPT / Gemini in the dashboard
- **AI import** — Claude Code skill imports any broker CSV without writing code

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

The wizard configures your tax profile (country, FSA amount, Zusammenveranlagung,
church tax, exchange suffix) and optionally sets up an AI provider for dashboard
analysis. Settings are saved to `config.json` (gitignored).

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
pt stats summary 1               # P&L, allocation, estimated tax
pt stats allocation 1            # breakdown by asset type
pt stats performance 1           # value history + Time-Weighted Return
pt stats performance 1 --period 2y   # longer range: 1m|3m|6m|1y|2y|all
```

The tax estimate in `summary` applies Teilfreistellung → Freistellungsauftrag → Abgeltungssteuer + Soli. This is a hypothetical estimate (as if you sold everything today).

`pt stats performance` automatically backfills missing history from yfinance the first time you run it for a given period — no manual setup needed.

---

## Performance snapshots

```bash
pt snapshot take 1               # record today's portfolio value
pt snapshot backfill 1           # fill history from yfinance (all time)
pt snapshot backfill 1 --since 2024-01-01 --interval 1d   # daily, from a date
```

Snapshots power the performance chart in `pt stats performance` and the dashboard. `pt dashboard open` records a snapshot automatically on every open.

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

Opens a local HTTP server at `http://127.0.0.1:<port>` and launches the browser. Press **Ctrl+C** in the terminal to stop. No CDN, no external requests (except the optional AI Analysis call).

The dashboard is organised into **5 tabs**:

| Tab | Content |
|-----|---------|
| **Overview** | KPI cards · allocation donut charts · P&L bar chart per holding |
| **Holdings** | Sortable, filterable table (click any column header to sort) |
| **Tax** | Freistellungsauftrag progress bar · tax summary · realized gains |
| **Rebalancing** | Target vs. actual deviation bars |
| **AI Analysis** | One-click deep analysis by your configured AI provider |

Other features:
- **Copy as Markdown** — exports a full portfolio snapshot for AI review
- Auto-records a snapshot on every open (used by the performance chart)

---

## AI Analysis

The dashboard includes a built-in **AI Analysis** panel powered by your choice of LLM. Click **Generate Analysis** to get a structured financial advisor review of your portfolio.

![AI Analysis](docs/screen%20-3.png)

### What the AI produces

| Section | Content |
|---------|---------|
| **Overall** | Rating (strong / good / fair / weak) + 2–3 sentence summary |
| **Performance Highlights** | Top winners and underperformers with commentary |
| **Risk & Diversification** | Concentration risk, geographic exposure, ETF overlap warnings |
| **Tax Optimization** | Freistellungsauftrag usage, Vorabpauschale notes, actions needed |
| **Recommendations** | Numbered, prioritised action items |

### Supported providers

| Provider | Default model |
|----------|--------------|
| **Anthropic** | `claude-sonnet-4-6` |
| **OpenAI** | `o3` |
| **Google Gemini** | `gemini-2.5-pro` |

### Setup

```bash
pt setup run
# → answer the "AI Analysis" step at the end
# → choose provider, paste API key, optionally override model
```

Or edit `config.json` directly:

```json
{
  "ai_provider": "anthropic",
  "ai_api_key": "sk-ant-...",
  "ai_model": ""
}
```

Then reopen the dashboard:

```bash
pt dashboard open 1
```

> The API key is stored only in `config.json` (gitignored) and embedded in the locally-generated
> temp HTML file. It is never sent anywhere except the chosen provider's API endpoint.

---

## Cash management

```bash
pt cash balance 1           # current balance
pt cash history 1           # full ledger
pt cash add 1 500 --type top_up
```

Types: `top_up`, `withdrawal`, `buy`, `sell`, `dividend`, `fee`. Buy/sell transactions automatically create matching cash entries.

---

## AI import (Claude Code skill)

This project includes [Claude Code Skills](https://docs.anthropic.com/en/docs/claude-code/skills) — reusable AI workflows that drive the CLI. No separate server or API key needed beyond your existing Claude Code session.

### Skills

| Command | Description |
|---------|-------------|
| `/portfolio import <file>` | Import from any broker CSV |
| `/portfolio summary` | Full portfolio overview + tax snapshot |
| `/portfolio` | Show menu |

The skill lives in `.claude/skills/portfolio/SKILL.md` and is committed to the repo —
available to anyone who clones it.

### Universal broker import

```
/portfolio import data/trading212_export.csv
```

Claude reads the columns, maps them to `pt` commands, and imports:
1. Shows a dry-run summary (counts by type, date range, tickers)
2. Asks for confirmation before writing anything
3. Creates missing holdings and records all transactions chronologically

> Unlike `pt import revolut`, the AI import is **not idempotent**. Running it twice creates
> duplicates — the skill always shows a preview and asks before proceeding.

### Portfolio overview

```
/portfolio summary
```

Runs `pt stats`, `pt holdings list`, `pt rebalance check`, and optional tax commands,
then gives 1–3 actionable recommendations based on the data.

---

## CLI reference

```
pt portfolio  create | list | show | delete
pt holdings   add | list | remove
pt tx         buy | sell | list
pt prices     fetch | history
pt stats      summary | allocation | performance
pt snapshot   take | backfill
pt rebalance  target | check | suggest | execute
pt cash       balance | history | add
pt tax        realized | lots | vorabpauschale
pt import     revolut
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
| AI Providers | Anthropic Claude, OpenAI, Google Gemini (optional) |

---

## Privacy

All data stays **local**:
- `portfolio.db` — SQLite on your machine
- `config.json` — local config, gitignored
- No accounts, no cloud sync, no telemetry
- AI Analysis calls your configured provider's API directly with your own key

---

## Disclaimer

This tool provides estimates for informational purposes only.
It is **not financial advice** and **not a substitute for professional tax counsel**.
Always verify Vorabpauschale and Abgeltungssteuer calculations with a Steuerberater
or your Finanzamt before filing.

---

## License

[MIT](LICENSE)
