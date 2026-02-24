#!/usr/bin/env python3
"""
Create a demo portfolio to showcase all dashboard features.

Portfolio: "Portfolio A — Demo"
Strategy:  VWCE/VVSM/HEAL/VAGF (70/15/10/5%)
History:   Jan 2023 lump-sum + quarterly DCA through 2025
Includes:  one VVSM sell in 2024 (shows Realized Gains section)
"""

import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from portfolio_tracker.data.database import get_db
from portfolio_tracker.data.repositories.cash_repo import CashRepository
from portfolio_tracker.data.repositories.holdings_repo import HoldingsRepository
from portfolio_tracker.data.repositories.portfolios_repo import PortfoliosRepository
from portfolio_tracker.data.repositories.prices_repo import PricesRepository
from portfolio_tracker.data.repositories.targets_repo import TargetsRepository
from portfolio_tracker.data.repositories.transactions_repo import TransactionsRepository
from portfolio_tracker.core.models import AssetType, CashTransactionType, TransactionType

get_db()

portfolios_repo = PortfoliosRepository()
holdings_repo   = HoldingsRepository()
tx_repo         = TransactionsRepository()
cash_repo       = CashRepository()
prices_repo     = PricesRepository()
targets_repo    = TargetsRepository()

# ── Guard: don't create twice ────────────────────────────────────────────────
DEMO_NAME = "Portfolio A — Demo"
for p in portfolios_repo.list_all():
    if p.name == DEMO_NAME:
        print(f"Demo portfolio already exists (ID {p.id}). Delete it first if you want to recreate.")
        sys.exit(0)

# ── 1. Portfolio ──────────────────────────────────────────────────────────────
portfolio = portfolios_repo.create(
    DEMO_NAME,
    "Demo portfolio — showcases all dashboard features. Not real data.",
)
pid = portfolio.id
print(f"✓ Created portfolio '{DEMO_NAME}' (ID {pid})")

# ── 2. Holdings ───────────────────────────────────────────────────────────────
HOLDING_META = [
    dict(isin="IE00BK5BQT80", ticker="VWCE", name="Vanguard FTSE All-World UCITS ETF (Acc)",
         asset_type=AssetType.ETF, tfs=Decimal("0.30")),
    dict(isin="IE00BMC38736", ticker="VVSM", name="VanEck Semiconductor UCITS ETF (Acc)",
         asset_type=AssetType.ETF, tfs=Decimal("0.30")),
    dict(isin="IE00BYZK4776", ticker="HEAL", name="iShares Healthcare Innovation UCITS ETF (Acc)",
         asset_type=AssetType.ETF, tfs=Decimal("0.30")),
    dict(isin="IE00BG47KH54", ticker="VAGF", name="Vanguard Global Aggregate Bond EUR Hedged (Acc)",
         asset_type=AssetType.BOND, tfs=Decimal("0.00")),
]

hmap = {}  # ticker → holding_id
for m in HOLDING_META:
    h = holdings_repo.create(pid, m["isin"], m["asset_type"], name=m["name"], ticker=m["ticker"])
    holdings_repo.update_teilfreistellung_rate(h.id, m["tfs"])
    hmap[m["ticker"]] = h.id
    print(f"  ✓ {m['ticker']} ({m['isin']})")

# ── 3. Target allocations ─────────────────────────────────────────────────────
TARGETS = [
    ("IE00BK5BQT80", Decimal("70"), Decimal("5")),
    ("IE00BMC38736", Decimal("15"), Decimal("3")),
    ("IE00BYZK4776", Decimal("10"), Decimal("3")),
    ("IE00BG47KH54", Decimal("5"),  Decimal("3")),
]
for isin, pct, threshold in TARGETS:
    targets_repo.set_target(pid, isin, pct, threshold)
print("✓ Target allocations set (70/15/10/5)")

# ── 4. Transactions ───────────────────────────────────────────────────────────
# Format: (ticker, type, date_str, qty, price, notes, realized_gain)
# Prices are approximate EUR historical NAV values.
BUYS_SELLS = [
    # ── Jan 2023 — lump sum (€13 500) ────────────────────────────────────────
    ("VWCE", "buy",  "2023-01-16", "111.18", "85.00",  "Lump sum", None),
    ("VVSM", "buy",  "2023-01-16", "81.00",  "25.00",  "Lump sum", None),
    ("HEAL", "buy",  "2023-01-16", "135.00", "10.00",  "Lump sum", None),
    ("VAGF", "buy",  "2023-01-16", "30.68",  "22.00",  "Lump sum", None),
    # ── Jul 2023 — Sparplan +€500 ─────────────────────────────────────────────
    ("VWCE", "buy",  "2023-07-03", "3.68",   "95.24",  "Sparplan Q3 2023", None),
    ("VVSM", "buy",  "2023-07-03", "2.34",   "32.05",  "Sparplan Q3 2023", None),
    ("HEAL", "buy",  "2023-07-03", "4.55",   "10.99",  "Sparplan Q3 2023", None),
    ("VAGF", "buy",  "2023-07-03", "1.11",   "22.52",  "Sparplan Q3 2023", None),
    # ── Jan 2024 — Sparplan +€500 ─────────────────────────────────────────────
    ("VWCE", "buy",  "2024-01-02", "3.50",   "100.00", "Sparplan Q1 2024", None),
    ("VVSM", "buy",  "2024-01-02", "1.88",   "39.89",  "Sparplan Q1 2024", None),
    ("HEAL", "buy",  "2024-01-02", "4.76",   "10.50",  "Sparplan Q1 2024", None),
    ("VAGF", "buy",  "2024-01-02", "1.09",   "22.94",  "Sparplan Q1 2024", None),
    # ── Apr 2024 — Sparplan +€500 ─────────────────────────────────────────────
    ("VWCE", "buy",  "2024-04-02", "3.18",   "110.38", "Sparplan Q2 2024", None),
    ("VVSM", "buy",  "2024-04-02", "1.36",   "55.15",  "Sparplan Q2 2024", None),
    ("HEAL", "buy",  "2024-04-02", "4.35",   "11.49",  "Sparplan Q2 2024", None),
    ("VAGF", "buy",  "2024-04-02", "1.06",   "23.58",  "Sparplan Q2 2024", None),
    # ── Oct 2024 — take profits on VVSM (20 shares at €60, cost basis €25 FIFO)
    ("VVSM", "sell", "2024-10-14", "20.00",  "60.00",  "Profit taking", "700.00"),
    # ── Jan 2025 — Sparplan +€500 ─────────────────────────────────────────────
    ("VWCE", "buy",  "2025-01-03", "3.24",   "108.02", "Sparplan Q1 2025", None),
    ("VVSM", "buy",  "2025-01-03", "2.00",   "50.00",  "Sparplan Q1 2025", None),
    ("HEAL", "buy",  "2025-01-03", "4.55",   "11.00",  "Sparplan Q1 2025", None),
    ("VAGF", "buy",  "2025-01-03", "1.09",   "22.94",  "Sparplan Q1 2025", None),
    # ── Jul 2025 — Sparplan +€500 ─────────────────────────────────────────────
    ("VWCE", "buy",  "2025-07-01", "3.05",   "114.75", "Sparplan Q3 2025", None),
    ("VVSM", "buy",  "2025-07-01", "1.64",   "60.98",  "Sparplan Q3 2025", None),
    ("HEAL", "buy",  "2025-07-01", "4.17",   "12.00",  "Sparplan Q3 2025", None),
    ("VAGF", "buy",  "2025-07-01", "1.04",   "24.04",  "Sparplan Q3 2025", None),
]

type_map = {"buy": TransactionType.BUY, "sell": TransactionType.SELL}
for ticker, ttype, date_str, qty, price, notes, rg in BUYS_SELLS:
    tx_repo.create(
        hmap[ticker],
        type_map[ttype],
        Decimal(qty),
        Decimal(price),
        datetime.fromisoformat(date_str),
        notes=notes,
        realized_gain=Decimal(rg) if rg else None,
    )

print(f"✓ {len(BUYS_SELLS)} transactions recorded")

# ── 5. Recalculate shares & cost basis ───────────────────────────────────────
for ticker, hid in hmap.items():
    txs = tx_repo.list_by_holding(hid)
    shares = Decimal("0")
    cost   = Decimal("0")
    for tx in txs:
        if tx.transaction_type == TransactionType.BUY:
            shares += tx.quantity
            cost   += tx.quantity * tx.price
        elif tx.transaction_type == TransactionType.SELL:
            # FIFO cost already captured in realized_gain; reduce shares only
            avg = cost / shares if shares else Decimal("0")
            shares -= tx.quantity
            cost   -= tx.quantity * avg
    holdings_repo.update_shares_and_cost(hid, shares, cost)

# ── 6. Cash transactions ──────────────────────────────────────────────────────
CASH = [
    # Top-ups
    (CashTransactionType.TOP_UP, "2023-01-10", "15000.00", "Initial lump sum"),
    (CashTransactionType.TOP_UP, "2023-07-01", "500.00",   "Sparplan Q3 2023"),
    (CashTransactionType.TOP_UP, "2024-01-01", "500.00",   "Sparplan Q1 2024"),
    (CashTransactionType.TOP_UP, "2024-04-01", "500.00",   "Sparplan Q2 2024"),
    (CashTransactionType.TOP_UP, "2025-01-01", "500.00",   "Sparplan Q1 2025"),
    (CashTransactionType.TOP_UP, "2025-07-01", "500.00",   "Sparplan Q3 2025"),
    # Buys (negative) — Jan 2023
    (CashTransactionType.BUY, "2023-01-16", "-9450.30", "VWCE lump sum"),
    (CashTransactionType.BUY, "2023-01-16", "-2025.00", "VVSM lump sum"),
    (CashTransactionType.BUY, "2023-01-16", "-1350.00", "HEAL lump sum"),
    (CashTransactionType.BUY, "2023-01-16", "-675.00",  "VAGF lump sum"),
    # Buys — Jul 2023
    (CashTransactionType.BUY, "2023-07-03", "-350.48", "Sparplan VWCE"),
    (CashTransactionType.BUY, "2023-07-03", "-75.00",  "Sparplan VVSM"),
    (CashTransactionType.BUY, "2023-07-03", "-50.00",  "Sparplan HEAL"),
    (CashTransactionType.BUY, "2023-07-03", "-25.00",  "Sparplan VAGF"),
    # Buys — Jan 2024
    (CashTransactionType.BUY, "2024-01-02", "-350.00", "Sparplan VWCE"),
    (CashTransactionType.BUY, "2024-01-02", "-75.00",  "Sparplan VVSM"),
    (CashTransactionType.BUY, "2024-01-02", "-50.00",  "Sparplan HEAL"),
    (CashTransactionType.BUY, "2024-01-02", "-25.00",  "Sparplan VAGF"),
    # Buys — Apr 2024
    (CashTransactionType.BUY, "2024-04-02", "-350.81", "Sparplan VWCE"),
    (CashTransactionType.BUY, "2024-04-02", "-75.00",  "Sparplan VVSM"),
    (CashTransactionType.BUY, "2024-04-02", "-50.00",  "Sparplan HEAL"),
    (CashTransactionType.BUY, "2024-04-02", "-25.00",  "Sparplan VAGF"),
    # Sell — Oct 2024
    (CashTransactionType.SELL, "2024-10-14", "1200.00", "VVSM profit taking"),
    # Buys — Jan 2025
    (CashTransactionType.BUY, "2025-01-03", "-350.00", "Sparplan VWCE"),
    (CashTransactionType.BUY, "2025-01-03", "-100.00", "Sparplan VVSM"),
    (CashTransactionType.BUY, "2025-01-03", "-50.00",  "Sparplan HEAL"),
    (CashTransactionType.BUY, "2025-01-03", "-25.00",  "Sparplan VAGF"),
    # Buys — Jul 2025
    (CashTransactionType.BUY, "2025-07-01", "-350.00", "Sparplan VWCE"),
    (CashTransactionType.BUY, "2025-07-01", "-100.00", "Sparplan VVSM"),
    (CashTransactionType.BUY, "2025-07-01", "-50.00",  "Sparplan HEAL"),
    (CashTransactionType.BUY, "2025-07-01", "-25.00",  "Sparplan VAGF"),
]

for cash_type, date_str, amount, desc in CASH:
    cash_repo.create(pid, cash_type, Decimal(amount),
                     datetime.fromisoformat(date_str), desc)

balance = cash_repo.get_balance(pid)
print(f"✓ Cash transactions recorded  |  Balance: €{balance:,.2f}")

# ── 7. Current prices (approximate Feb 2026 NAV) ─────────────────────────────
CURRENT_PRICES = {
    "VWCE": Decimal("122.40"),
    "VVSM": Decimal("61.25"),
    "HEAL": Decimal("11.85"),
    "VAGF": Decimal("23.98"),
}

now = datetime.now()
for ticker, price in CURRENT_PRICES.items():
    prices_repo.store_price(hmap[ticker], price, source="demo")

print("✓ Current prices set (approximate Feb 2026)")

# ── 8. Summary ────────────────────────────────────────────────────────────────
print()
print("=" * 55)
print(f"  Demo portfolio ready! ID: {pid}")
print()
print("  Run:  pt dashboard open", pid)
print("=" * 55)
