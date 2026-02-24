#!/usr/bin/env python3
"""
Import Revolut portfolio from the Feb 2026 PDF statement.
Uses the summary holdings data (exact quantities + cost basis from PDF page 2).
"""

import sys
sys.path.insert(0, "src")

from datetime import datetime
from decimal import Decimal

from portfolio_tracker.data.database import get_db
from portfolio_tracker.data.repositories.portfolios_repo import PortfoliosRepository
from portfolio_tracker.data.repositories.holdings_repo import HoldingsRepository
from portfolio_tracker.data.repositories.transactions_repo import TransactionsRepository
from portfolio_tracker.core.models import AssetType, TransactionType

get_db()

portfolios = PortfoliosRepository()
holdings_repo = HoldingsRepository()
tx_repo = TransactionsRepository()

p = portfolios.create("Revolut", "Revolut investment portfolio — migrating to Trade Republic")
print(f"Created portfolio: {p.name} (ID: {p.id})")

# Holdings from PDF page 2 (summary section)
# (ISIN, type, name, ticker, quantity, avg_price_eur, cost_basis_eur)
HOLDINGS = [
    ("IE00BP3QZ601", "etf",  "iShares MSCI World Quality Factor", "IS3Q",  "45.7292", "67.04",  "3065.78"),
    ("DE0006289382", "etf",  "iShares DJ Global Titans 50",       "EXI2",  "49.6293", "51.71",  "2566.21"),
    ("IE00BM67HT60", "etf",  "Xtrackers MSCI World IT",           "XDWT",  "15.3741", "103.51", "1591.08"),
    ("LU0274209740", "etf",  "Xtrackers MSCI Japan",              "DBXJ",  "36.9478", "20.57",  "760.10"),
    ("IE00B66F4759", "bond", "iShares € High Yield Corp Bond",    "IS3K",  "27.3018", "96.07",  "2622.85"),
    ("IE00B2NPKV68", "bond", "iShares JPM USD EM Bond",           "IS3C",  "7.1853",  "88.26",  "634.21"),
    ("IE00B3F81R35", "bond", "iShares € Corp Bond Large Cap",     "IBCL",  "7.6163",  "109.22", "831.63"),
    ("IE00BDBRDM35", "bond", "iShares € Corp Bond 0-3yr ESG",    "IBCN",  "5.5303",  "30.71",  "169.86"),
]

total_cost = Decimal("0")

for isin, atype, name, ticker, qty_str, avg_str, cost_str in HOLDINGS:
    qty = Decimal(qty_str)
    avg_price = Decimal(avg_str)
    cost = Decimal(cost_str)

    h = holdings_repo.create(p.id, isin, AssetType(atype), name=name, ticker=ticker)

    # Record one consolidated "buy" at avg price
    tx_repo.create(
        h.id,
        TransactionType.BUY,
        qty,
        avg_price,
        datetime(2024, 1, 1),  # placeholder date (DCA over 2022-2023)
        notes="Revolut import — consolidated avg price",
    )

    # Set exact shares and cost basis from PDF
    holdings_repo.update_shares_and_cost(h.id, qty, cost)
    total_cost += cost

    print(f"  {name:42s}  {str(qty):>10s} units  cost EUR {cost_str:>9s}  ({ticker})")

print(f"\n{'='*70}")
print(f"  Total cost basis:  €{total_cost:,.2f}")
print(f"  Expected (PDF):    €14,267.49")
print(f"  Delta:             €{total_cost - Decimal('14267.49'):,.2f}")
print(f"{'='*70}")
print(f"\n  8 holdings imported. Run 'pt holdings list 1' to verify.")
