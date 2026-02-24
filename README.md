# Portfolio Tracker

CLI tool for tracking ETF portfolios, built for a German tax resident using Trade Republic.

## What it does

- Track holdings by ISIN with full transaction history (buys, dividends)
- Store and compare prices over time
- Calculate P&L, tax estimates (Abgeltungssteuer), and portfolio allocation
- Rebalance toward target allocations (supports per-ISIN targets)
- German tax awareness: Freistellungsauftrag, Teilfreistellung, Solidaritätszuschlag

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

The CLI entry point is `pt`. All commands are grouped by domain:

```
pt portfolio create "My Portfolio"     # create a portfolio
pt portfolio list                      # list portfolios

pt holdings add 1 IE00BK5BQT80 equity --name "Vanguard FTSE All-World" --ticker VWCE
pt holdings list 1                     # show holdings with current prices

pt tx buy <holding_id> --qty 10 --price 100.50 --date 2025-01-15
pt tx list <holding_id>                # transaction history

pt prices fetch 1                      # fetch latest prices (yfinance)
pt prices history <holding_id>         # price history for a holding

pt stats summary 1                     # portfolio summary with P&L
pt stats tax 1                         # German tax estimate

pt rebalance targets 1                 # view target allocations
pt rebalance check 1                   # compare current vs target
pt rebalance suggest 1 --amount 500    # suggest trades to rebalance
```

## Project structure

```
src/portfolio_tracker/
├── cli/commands/       # Typer CLI commands (holdings, portfolio, prices, rebalance, stats, tx)
├── core/               # Business logic (calculator, rebalancer, models)
├── data/               # SQLite database and repositories
└── external/           # Price fetchers (yfinance, crypto)

scripts/                # Import scripts (Revolut CSV)
tests/                  # Unit and integration tests
portfolio.db            # SQLite database (tracked in git as backup)
```

## Stack

Python 3.10+, Typer, Rich, SQLite, yfinance

## License

Private — personal use only.
