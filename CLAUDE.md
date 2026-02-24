# Portfolio Tracker — Claude Instructions

## Project Overview

Investment portfolio tracker CLI for managing holdings, transactions, statistics, and rebalancing. Designed for a user trading on **Trade Republic** with **German tax residency**.

## Tech Stack

- **Python 3.10+** with **Typer** CLI framework
- **SQLite** database (stored at `~/.portfolio-tracker/portfolio.db`)
- **yfinance** for stock/ETF/bond prices
- **CoinGecko API** for crypto prices (free, no key)
- **Rich** for terminal output formatting

## Project Structure

```
src/portfolio_tracker/
├── cli/commands/    # CLI command groups (portfolio, holdings, tx, prices, stats, rebalance)
├── core/            # Business logic (calculator, rebalancer, models, exceptions)
├── data/            # Database + repositories (portfolios, holdings, transactions, prices, targets)
└── external/        # Price fetching (yfinance, CoinGecko)
```

## Key Design Decisions

- **Repository pattern**: Data access isolated from business logic
- **Decimal everywhere**: Financial calculations use `Decimal`, not `float`
- **EUR-centric**: All prices and values in EUR (Trade Republic base currency)
- **German tax model**: Abgeltungssteuer (25%) + Soli (5.5%), Freistellungsauftrag €2,000 (married)
- **Asset types**: stock, etf, crypto, bond

## CLI Command Reference

```bash
pt portfolio create|list|show|delete
pt holdings add|list|remove
pt tx buy|sell|list
pt prices fetch|history
pt stats summary|allocation
pt rebalance target|check|suggest|execute
```

## Running

```bash
pip install -e .
pt --help
```

## Testing

```bash
python -m pytest tests/ -v
```

## Future Plans

- REST API (FastAPI) for React frontend
- Trade Republic CSV import
- Historical performance charts
- Vorabpauschale calculation for accumulating funds
- Kirchensteuer support (configurable by Bundesland)
