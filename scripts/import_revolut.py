#!/usr/bin/env python3
"""Import Revolut portfolio data from the Feb 2026 statement."""

import sys
sys.path.insert(0, "src")

from datetime import datetime
from decimal import Decimal

from portfolio_tracker.data.database import get_db
from portfolio_tracker.data.repositories.portfolios_repo import PortfoliosRepository
from portfolio_tracker.data.repositories.holdings_repo import HoldingsRepository
from portfolio_tracker.data.repositories.transactions_repo import TransactionsRepository
from portfolio_tracker.core.models import AssetType, TransactionType

# Initialize DB
get_db()

portfolios = PortfoliosRepository()
holdings_repo = HoldingsRepository()
tx_repo = TransactionsRepository()

# Create portfolio
p = portfolios.create("Revolut", "Revolut investment portfolio — migrating to Trade Republic")
print(f"Created portfolio: {p.name} (ID: {p.id})")

# ============================================================
# Holdings from Revolut PDF statement (Feb 2026)
# ============================================================

HOLDINGS = [
    # (ISIN, asset_type, name, ticker, quantity, avg_price_eur, cost_basis_eur)
    # Equity ETFs
    ("IE00BP3QZ601", "etf", "iShares MSCI World Quality Factor", "IS3Q", "45.7292", "67.04", "3065.78"),
    ("DE0006289382", "etf", "iShares DJ Global Titans 50", "EXI2", "49.6293", "51.71", "2566.21"),
    ("IE00BM67HT60", "etf", "Xtrackers MSCI World IT", "XDWT", "15.3741", "103.51", "1591.08"),
    ("LU0274209740", "etf", "Xtrackers MSCI Japan", "DBXJ", "36.9478", "20.57", "760.10"),
    # Bond ETFs
    ("IE00B66F4759", "bond", "iShares € High Yield Corp Bond", "IS3K", "27.3018", "96.07", "2622.85"),
    ("IE00B2NPKV68", "bond", "iShares JPM USD EM Bond", "IS3C", "7.1853", "88.26", "634.21"),
    ("IE00B3F81R35", "bond", "iShares € Corp Bond Large Cap", "IBCL", "7.6163", "109.22", "831.63"),
    ("IE00BDBRDM35", "bond", "iShares € Corp Bond 0-3yr ESG", "IBCN", "5.5303", "30.71", "169.86"),
]

# ============================================================
# Transaction history from the Revolut PDF
# Each entry: (isin, type, date, qty, price_eur)
# ============================================================

TRANSACTIONS = [
    # === IS3Q — iShares MSCI World Quality Factor ===
    ("IE00BP3QZ601", "buy", "2022-08-08", "1.8197", "54.95"),
    ("IE00BP3QZ601", "buy", "2022-09-05", "1.8989", "52.66"),
    ("IE00BP3QZ601", "buy", "2022-10-06", "3.6003", "55.55"),
    ("IE00BP3QZ601", "buy", "2022-11-07", "3.4236", "58.43"),
    ("IE00BP3QZ601", "buy", "2022-12-05", "3.2779", "61.01"),
    ("IE00BP3QZ601", "buy", "2023-01-09", "3.4602", "57.80"),
    ("IE00BP3QZ601", "buy", "2023-02-06", "3.2032", "62.43"),
    ("IE00BP3QZ601", "buy", "2023-03-06", "3.1108", "64.30"),
    ("IE00BP3QZ601", "buy", "2023-04-06", "3.0581", "65.40"),
    ("IE00BP3QZ601", "buy", "2023-05-08", "2.9834", "67.03"),
    ("IE00BP3QZ601", "buy", "2023-06-05", "2.8131", "71.08"),
    ("IE00BP3QZ601", "buy", "2023-07-06", "2.8160", "71.02"),
    ("IE00BP3QZ601", "buy", "2023-08-07", "2.6963", "74.18"),
    ("IE00BP3QZ601", "buy", "2023-09-06", "2.7413", "72.96"),
    ("IE00BP3QZ601", "buy", "2023-10-05", "2.8490", "70.20"),
    ("IE00BP3QZ601", "buy", "2023-11-06", "2.7448", "72.87"),

    # === EXI2 — iShares DJ Global Titans 50 ===
    ("DE0006289382", "buy", "2022-08-08", "2.5000", "40.00"),
    ("DE0006289382", "buy", "2022-09-05", "2.6350", "37.96"),
    ("DE0006289382", "buy", "2022-10-06", "5.0839", "39.34"),
    ("DE0006289382", "buy", "2022-11-07", "4.6728", "42.80"),
    ("DE0006289382", "buy", "2022-12-05", "4.5066", "44.38"),
    ("DE0006289382", "buy", "2023-01-09", "4.6555", "42.96"),
    ("DE0006289382", "buy", "2023-02-06", "4.1929", "47.70"),
    ("DE0006289382", "buy", "2023-03-06", "4.0387", "49.52"),
    ("DE0006289382", "buy", "2023-04-06", "3.7657", "53.11"),
    ("DE0006289382", "buy", "2023-05-08", "3.6219", "55.22"),
    ("DE0006289382", "buy", "2023-06-05", "3.2974", "60.65"),
    ("DE0006289382", "buy", "2023-07-06", "3.2287", "61.94"),
    ("DE0006289382", "buy", "2023-08-07", "3.2051", "62.40"),
    ("DE0006289382", "buy", "2023-09-06", "3.2979", "60.65"),
    ("DE0006289382", "buy", "2023-10-05", "3.4810", "57.46"),
    ("DE0006289382", "buy", "2023-11-06", "3.4462", "58.04"),

    # === XDWT — Xtrackers MSCI World IT ===
    ("IE00BM67HT60", "buy", "2022-08-08", "0.9560", "104.60"),
    ("IE00BM67HT60", "buy", "2022-09-05", "1.1136", "89.80"),
    ("IE00BM67HT60", "buy", "2022-10-06", "2.1277", "93.99"),
    ("IE00BM67HT60", "buy", "2022-11-07", "1.9646", "101.80"),
    ("IE00BM67HT60", "buy", "2022-12-05", "2.0040", "99.80"),
    ("IE00BM67HT60", "buy", "2023-01-09", "2.1097", "94.80"),
    ("IE00BM67HT60", "buy", "2023-02-06", "1.8587", "107.60"),
    ("IE00BM67HT60", "buy", "2023-03-06", "1.7637", "113.42"),
    ("IE00BM67HT60", "buy", "2023-04-06", "1.7699", "113.02"),
    ("IE00BM67HT60", "buy", "2023-05-08", "1.7086", "117.05"),

    # === IS3K — iShares € High Yield Corp Bond ===
    ("IE00B66F4759", "buy", "2022-08-08", "1.0660", "93.81"),
    ("IE00B66F4759", "buy", "2022-09-05", "1.0947", "91.35"),
    ("IE00B66F4759", "buy", "2022-10-06", "2.2177", "90.18"),
    ("IE00B66F4759", "buy", "2022-11-07", "2.1200", "94.34"),
    ("IE00B66F4759", "buy", "2022-12-05", "2.1095", "94.81"),
    ("IE00B66F4759", "buy", "2023-01-09", "2.0743", "96.42"),
    ("IE00B66F4759", "buy", "2023-02-06", "2.0327", "98.39"),
    ("IE00B66F4759", "buy", "2023-03-06", "2.0632", "96.94"),
    ("IE00B66F4759", "buy", "2023-04-06", "2.0408", "98.00"),
    ("IE00B66F4759", "buy", "2023-05-08", "2.0489", "97.61"),
    ("IE00B66F4759", "buy", "2023-06-05", "2.0534", "97.40"),
    ("IE00B66F4759", "buy", "2023-07-06", "2.0636", "96.92"),
    ("IE00B66F4759", "buy", "2023-08-07", "2.0571", "97.22"),
    ("IE00B66F4759", "buy", "2023-09-06", "2.0709", "96.57"),
    ("IE00B66F4759", "buy", "2023-10-05", "2.0884", "95.77"),
    ("IE00B66F4759", "buy", "2023-11-06", "1.2011", "96.57"),

    # === IS3C — iShares JPM USD EM Bond ===
    ("IE00B2NPKV68", "buy", "2022-10-06", "1.1820", "84.60"),
    ("IE00B2NPKV68", "buy", "2022-11-07", "1.0882", "91.90"),
    ("IE00B2NPKV68", "buy", "2022-12-05", "1.1236", "89.00"),
    ("IE00B2NPKV68", "buy", "2023-01-09", "1.0965", "91.20"),
    ("IE00B2NPKV68", "buy", "2023-02-06", "1.1574", "86.40"),
    ("IE00B2NPKV68", "buy", "2023-03-06", "1.5376", "86.50"),

    # === DBXJ — Xtrackers MSCI Japan ===
    ("LU0274209740", "buy", "2022-10-06", "5.0125", "19.95"),
    ("LU0274209740", "buy", "2022-11-07", "4.8544", "20.60"),
    ("LU0274209740", "buy", "2022-12-05", "5.1546", "19.40"),
    ("LU0274209740", "buy", "2023-01-09", "4.9261", "20.30"),
    ("LU0274209740", "buy", "2023-02-06", "4.7962", "20.85"),
    ("LU0274209740", "buy", "2023-03-06", "4.6404", "21.55"),
    ("LU0274209740", "buy", "2023-04-06", "4.5249", "22.10"),
    ("LU0274209740", "buy", "2023-05-08", "3.0387", "21.72"),

    # === IBCL — iShares € Corp Bond Large Cap ===
    ("IE00B3F81R35", "buy", "2022-08-08", "0.8880", "112.61"),
    ("IE00B3F81R35", "buy", "2022-09-05", "0.9560", "104.60"),
    ("IE00B3F81R35", "buy", "2022-10-06", "1.9512", "102.50"),
    ("IE00B3F81R35", "buy", "2022-11-07", "1.8519", "108.00"),
    ("IE00B3F81R35", "buy", "2022-12-05", "1.9693", "113.75"),

    # === IBCN — iShares € Corp Bond 0-3yr ESG ===
    ("IE00BDBRDM35", "buy", "2022-12-05", "1.9504", "30.76"),
    ("IE00BDBRDM35", "buy", "2023-01-09", "3.2479", "30.79"),
    ("IE00BDBRDM35", "buy", "2023-02-06", "0.3320", "30.12"),
]


def main():
    pid = p.id

    # Create all holdings
    holding_map = {}  # ISIN -> holding_id
    for isin, atype, name, ticker, qty, avg_price, cost in HOLDINGS:
        h = holdings_repo.create(pid, isin, AssetType(atype), name=name, ticker=ticker)
        holding_map[isin] = h.id
        print(f"  Added: {name} ({isin}) — {ticker}")

    print(f"\nCreated {len(HOLDINGS)} holdings. Importing transactions...\n")

    # Import all transactions
    tx_count = 0
    for isin, tx_type, date_str, qty, price in TRANSACTIONS:
        hid = holding_map[isin]
        tx_date = datetime.fromisoformat(date_str)
        tt = TransactionType.BUY if tx_type == "buy" else TransactionType.SELL
        qty_d = Decimal(qty)
        price_d = Decimal(price)

        tx_repo.create(hid, tt, qty_d, price_d, tx_date)
        tx_count += 1

    print(f"Imported {tx_count} transactions.")

    # Now update holding shares and cost_basis from transactions
    print("\nRecalculating shares and cost basis...")
    for isin, hid in holding_map.items():
        txs = tx_repo.list_by_holding(hid)
        total_shares = Decimal("0")
        total_cost = Decimal("0")
        for tx in txs:
            if tx.transaction_type == TransactionType.BUY:
                total_shares += tx.quantity
                total_cost += tx.quantity * tx.price
            else:
                avg_cost = total_cost / total_shares if total_shares > 0 else Decimal("0")
                total_shares -= tx.quantity
                total_cost -= tx.quantity * avg_cost

        holdings_repo.update_shares_and_cost(hid, total_shares, total_cost)
        h = holdings_repo.get_by_id(hid)
        print(f"  {h.name}: {h.shares:.4f} units, cost €{h.cost_basis:,.2f}")

    print("\nDone! Run 'pt holdings list 1' to see your portfolio.")
    print(f"Expected total cost from PDF: €14,267.49")
    actual_cost = sum(Decimal(h[6]) for h in HOLDINGS)
    print(f"Sum of cost basis from PDF:   €{actual_cost:,.2f}")


if __name__ == "__main__":
    main()
