#!/usr/bin/env python3
"""
DEPRECATED: use `pt import revolut <file>` instead. Kept for reference.

Import Revolut portfolio from CSV exports.

Reads:
  - Transaction CSV (buys, dividends, cash top-ups, fees)
  - P&L CSV (dividend details with ISINs)

Creates one portfolio with all holdings, buy transactions, and dividends.
"""

import csv
import sys
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, "src")

from portfolio_tracker.data.database import get_db
from portfolio_tracker.data.repositories.portfolios_repo import PortfoliosRepository
from portfolio_tracker.data.repositories.holdings_repo import HoldingsRepository
from portfolio_tracker.data.repositories.lots_repo import LotsRepository
from portfolio_tracker.data.repositories.transactions_repo import TransactionsRepository
from portfolio_tracker.data.repositories.cash_repo import CashRepository
from portfolio_tracker.core.models import AssetType, TransactionType, CashTransactionType

# ============================================================
# Ticker → ISIN + metadata mapping
# ISINs from P&L CSV (distributing) + known ISINs (accumulating)
# ============================================================
TICKER_META = {
    # Equity ETFs (accumulating — no dividends, ISINs from original statements)
    # Teilfreistellung 30% applies (§ 20 InvStG, equity fund)
    "IS3Q": {
        "isin": "IE00BP3QZ601",
        "name": "iShares MSCI World Quality Factor UCITS ETF",
        "type": "etf",
        "teilfreistellung_rate": "0.3",
    },
    "XDWT": {
        "isin": "IE00BM67HT60",
        "name": "Xtrackers MSCI World IT UCITS ETF",
        "type": "etf",
        "teilfreistellung_rate": "0.3",
    },
    "DBXJ": {
        "isin": "LU0274209740",
        "name": "Xtrackers MSCI Japan UCITS ETF",
        "type": "etf",
        "teilfreistellung_rate": "0.3",
    },
    "EXI2": {
        "isin": "DE0006289382",
        "name": "iShares Dow Jones Global Titans 50 ETF (Dist)",
        "type": "etf",
        "teilfreistellung_rate": "0.3",
    },
    # Bond ETFs (distributing — ISINs from P&L CSV)
    # No Teilfreistellung for bond ETFs
    "IS3C": {
        "isin": "IE00B9M6RS56",
        "name": "iShares J.P. Morgan USD EM Bond (Dist.) ETF",
        "type": "bond",
        "teilfreistellung_rate": "0",
    },
    "IS3K": {
        "isin": "IE00BCRY6003",
        "name": "iShares High Yield Corporate Bond Dist ETF",
        "type": "bond",
        "teilfreistellung_rate": "0",
    },
    "QDVY": {
        "isin": "IE00BZ048462",
        "name": "iShares Floating Rate Bond Dist ETF",
        "type": "bond",
        "teilfreistellung_rate": "0",
    },
    "IBCD": {
        "isin": "IE0032895942",
        "name": "iShares Corporate Bond Dist ETF",
        "type": "bond",
        "teilfreistellung_rate": "0",
    },
}


def parse_eur(s: str) -> Decimal:
    """Parse 'EUR 123.45' or 'EUR -5.05' to Decimal."""
    s = s.strip()
    s = s.replace("EUR ", "").replace("€", "").replace(",", "")
    return Decimal(s)


def main():
    tx_csv = Path(__file__).parent.parent / "data" / "revolut_transactions.csv"
    pnl_csv = Path(__file__).parent.parent / "data" / "revolut_pnl.csv"

    if not tx_csv.exists():
        print(f"ERROR: {tx_csv} not found. Copy the CSV there first.")
        sys.exit(1)

    db = get_db()

    portfolios = PortfoliosRepository()
    holdings_repo = HoldingsRepository()
    lots_repo = LotsRepository()
    tx_repo = TransactionsRepository()
    cash_repo = CashRepository()

    with db.transaction():
        # Create portfolio
        p = portfolios.create("Revolut", "Revolut Robo-Advisor — migrating to Trade Republic")
        print(f"Created portfolio: {p.name} (ID: {p.id})\n")

        # Create all holdings
        holding_map = {}  # ticker -> holding_id
        for ticker, meta in TICKER_META.items():
            from decimal import Decimal as _Decimal
            tfs_rate = _Decimal(meta.get("teilfreistellung_rate", "0"))
            h = holdings_repo.create(
                p.id,
                meta["isin"],
                AssetType(meta["type"]),
                name=meta["name"],
                ticker=ticker,
                teilfreistellung_rate=tfs_rate,
            )
            holding_map[ticker] = h.id
            tfs_info = f"  TFS={tfs_rate * 100:.0f}%" if tfs_rate > 0 else ""
            print(f"  Created: {meta['name']} ({ticker} / {meta['isin']}){tfs_info}")

        print(f"\nCreated {len(holding_map)} holdings.\n")

        # Parse transaction CSV
        buy_count = 0
        div_count = 0
        cash_count = 0
        total_invested = Decimal("0")
        total_dividends = Decimal("0")
        total_fees = Decimal("0")
        total_topups = Decimal("0")

        with open(tx_csv) as f:
            reader = csv.DictReader(f)
            for row in reader:
                tx_type = row["Type"].strip()
                ticker = row["Ticker"].strip()
                date_str = row["Date"].strip()

                # Parse date (ISO format with optional fractional seconds)
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))

                if tx_type == "BUY - MARKET" and ticker in holding_map:
                    qty = Decimal(row["Quantity"])
                    price = parse_eur(row["Price per share"])
                    total = parse_eur(row["Total Amount"])

                    tx = tx_repo.create(
                        holding_map[ticker],
                        TransactionType.BUY,
                        qty,
                        price,
                        dt,
                        notes="Revolut CSV import",
                    )
                    # Create FIFO tax lot for this buy
                    lots_repo.create(
                        holding_map[ticker], dt, qty, price,
                        buy_transaction_id=tx.id,
                    )
                    # Record cash outflow for the buy
                    cash_repo.create(
                        p.id, CashTransactionType.BUY, -total, dt,
                        description=f"Buy {ticker} ({qty} × €{price})",
                    )
                    buy_count += 1
                    cash_count += 1
                    total_invested += total

                elif tx_type == "DIVIDEND" and ticker in holding_map:
                    amount = parse_eur(row["Total Amount"])
                    tx_repo.create(
                        holding_map[ticker],
                        TransactionType.DIVIDEND,
                        Decimal("0"),  # no shares change
                        amount,  # dividend amount as "price"
                        dt,
                        notes="Revolut dividend",
                    )
                    # Record cash inflow from dividend
                    cash_repo.create(
                        p.id, CashTransactionType.DIVIDEND, amount, dt,
                        description=f"Dividend from {ticker}",
                    )
                    div_count += 1
                    cash_count += 1
                    total_dividends += amount

                elif tx_type == "CASH TOP-UP":
                    amount = parse_eur(row["Total Amount"])
                    cash_repo.create(
                        p.id, CashTransactionType.TOP_UP, amount, dt,
                        description="Revolut top-up",
                    )
                    cash_count += 1
                    total_topups += amount

                elif tx_type == "ROBO MANAGEMENT FEE":
                    fee = parse_eur(row["Total Amount"])
                    cash_repo.create(
                        p.id, CashTransactionType.FEE, fee, dt,
                        description="Robo management fee",
                    )
                    cash_count += 1
                    total_fees += fee  # negative values

        # Recalculate shares and cost basis from buy transactions
        print("Recalculating holdings from transactions...\n")
        for ticker, hid in holding_map.items():
            txs = tx_repo.list_by_holding(hid)
            total_shares = Decimal("0")
            total_cost = Decimal("0")

            for tx in txs:
                if tx.transaction_type == TransactionType.BUY:
                    total_shares += tx.quantity
                    total_cost += tx.quantity * tx.price

            holdings_repo.update_shares_and_cost(hid, total_shares, total_cost)
            meta = TICKER_META[ticker]
            print(f"  {meta['name']:50s}  {total_shares:>12.8f} units  cost €{total_cost:>10,.2f}")

    # Summary (outside transaction — just printing)
    cash_balance = cash_repo.get_balance(p.id)
    print(f"\n{'='*75}")
    print(f"  Buy transactions:    {buy_count}")
    print(f"  Dividend payments:   {div_count}")
    print(f"  Cash transactions:   {cash_count}")
    print(f"  Total top-ups:       €{total_topups:,.2f}")
    print(f"  Total invested:      €{total_invested:,.2f}")
    print(f"  Total dividends:     €{total_dividends:,.2f}")
    print(f"  Total fees:          €{total_fees:,.2f}")
    print(f"  Cash balance (DB):   €{cash_balance:,.2f}")
    print(f"{'='*75}")
    print(f"\nDone! Run 'pt holdings list 1' to see your portfolio.")


if __name__ == "__main__":
    main()
