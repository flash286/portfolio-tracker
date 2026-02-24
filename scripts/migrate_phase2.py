#!/usr/bin/env python3
"""
Phase 2 migration: REAL → TEXT for financial columns, add tax_lots table.

Run ONCE on an existing portfolio.db. Creates a backup first.

Changes:
  - holdings.shares, cost_basis: REAL → TEXT
  - holdings: add teilfreistellung_rate TEXT DEFAULT '0'
  - transactions.quantity, price, total_value: REAL → TEXT
  - transactions: add realized_gain TEXT DEFAULT NULL
  - price_history.price: REAL → TEXT
  - cash_transactions.amount: REAL → TEXT
  - target_allocations.target_percentage, rebalance_threshold: REAL → TEXT
  - New table: tax_lots (FIFO cost basis tracking)
  - Seed tax_lots from existing buy transactions (FIFO-adjusted for sells)
"""

import shutil
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path


def find_project_root() -> Path:
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    return Path.cwd()


def migrate(db_path: Path):
    print(f"Migrating: {db_path}")

    # Safety backup
    backup_path = db_path.with_suffix(f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    shutil.copy2(db_path, backup_path)
    print(f"Backup created: {backup_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("PRAGMA journal_mode = WAL")

    try:
        with conn:
            _migrate_holdings(conn)
            _migrate_transactions(conn)
            _migrate_price_history(conn)
            _migrate_cash_transactions(conn)
            _migrate_target_allocations(conn)
            _create_tax_lots(conn)
            _seed_tax_lots(conn)
            _rebuild_indexes(conn)

        print("\nMigration complete.")
        _verify(conn)

    except Exception as e:
        print(f"\nERROR: {e}")
        print("Database may be corrupted — restore from backup!")
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.close()


def _migrate_holdings(conn):
    print("\n[1/5] Migrating holdings (REAL→TEXT, add teilfreistellung_rate)...")
    conn.execute("ALTER TABLE holdings RENAME TO holdings_old")
    conn.execute("""
        CREATE TABLE holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_id INTEGER NOT NULL,
            isin TEXT NOT NULL,
            asset_type TEXT NOT NULL,
            name TEXT DEFAULT '',
            ticker TEXT DEFAULT '',
            shares TEXT NOT NULL DEFAULT '0',
            cost_basis TEXT NOT NULL DEFAULT '0',
            teilfreistellung_rate TEXT NOT NULL DEFAULT '0',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
            UNIQUE(portfolio_id, isin)
        )
    """)
    conn.execute("""
        INSERT INTO holdings
            (id, portfolio_id, isin, asset_type, name, ticker,
             shares, cost_basis, teilfreistellung_rate, created_at, updated_at)
        SELECT id, portfolio_id, isin, asset_type, name, ticker,
               CAST(shares AS TEXT), CAST(cost_basis AS TEXT), '0',
               created_at, updated_at
        FROM holdings_old
    """)
    count = conn.execute("SELECT COUNT(*) FROM holdings").fetchone()[0]
    conn.execute("DROP TABLE holdings_old")
    print(f"   Migrated {count} holdings.")


def _migrate_transactions(conn):
    print("[2/5] Migrating transactions (REAL→TEXT, add realized_gain)...")
    conn.execute("ALTER TABLE transactions RENAME TO transactions_old")
    conn.execute("""
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            holding_id INTEGER NOT NULL,
            transaction_type TEXT NOT NULL,
            quantity TEXT NOT NULL,
            price TEXT NOT NULL,
            total_value TEXT NOT NULL,
            realized_gain TEXT DEFAULT NULL,
            transaction_date TIMESTAMP NOT NULL,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (holding_id) REFERENCES holdings(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        INSERT INTO transactions
            (id, holding_id, transaction_type, quantity, price, total_value,
             realized_gain, transaction_date, notes, created_at)
        SELECT id, holding_id, transaction_type,
               CAST(quantity AS TEXT), CAST(price AS TEXT), CAST(total_value AS TEXT),
               NULL, transaction_date, notes, created_at
        FROM transactions_old
    """)
    count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    conn.execute("DROP TABLE transactions_old")
    print(f"   Migrated {count} transactions.")


def _migrate_price_history(conn):
    print("[3/5] Migrating price_history (REAL→TEXT)...")
    conn.execute("ALTER TABLE price_history RENAME TO price_history_old")
    conn.execute("""
        CREATE TABLE price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            holding_id INTEGER NOT NULL,
            price TEXT NOT NULL,
            fetch_date TIMESTAMP NOT NULL,
            source TEXT DEFAULT '',
            FOREIGN KEY (holding_id) REFERENCES holdings(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        INSERT INTO price_history (id, holding_id, price, fetch_date, source)
        SELECT id, holding_id, CAST(price AS TEXT), fetch_date, source
        FROM price_history_old
    """)
    count = conn.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
    conn.execute("DROP TABLE price_history_old")
    print(f"   Migrated {count} price records.")


def _migrate_cash_transactions(conn):
    print("[4/5] Migrating cash_transactions (REAL→TEXT)...")
    conn.execute("ALTER TABLE cash_transactions RENAME TO cash_transactions_old")
    conn.execute("""
        CREATE TABLE cash_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_id INTEGER NOT NULL,
            cash_type TEXT NOT NULL,
            amount TEXT NOT NULL,
            transaction_date TIMESTAMP NOT NULL,
            description TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        INSERT INTO cash_transactions
            (id, portfolio_id, cash_type, amount, transaction_date, description, created_at)
        SELECT id, portfolio_id, cash_type, CAST(amount AS TEXT),
               transaction_date, description, created_at
        FROM cash_transactions_old
    """)
    count = conn.execute("SELECT COUNT(*) FROM cash_transactions").fetchone()[0]
    conn.execute("DROP TABLE cash_transactions_old")
    print(f"   Migrated {count} cash transactions.")


def _migrate_target_allocations(conn):
    print("[5/5] Migrating target_allocations (REAL→TEXT)...")
    conn.execute("ALTER TABLE target_allocations RENAME TO target_allocations_old")
    conn.execute("""
        CREATE TABLE target_allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_id INTEGER NOT NULL,
            asset_type TEXT NOT NULL,
            target_percentage TEXT NOT NULL,
            rebalance_threshold TEXT DEFAULT '5.0',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
            UNIQUE(portfolio_id, asset_type)
        )
    """)
    conn.execute("""
        INSERT INTO target_allocations
            (id, portfolio_id, asset_type, target_percentage, rebalance_threshold,
             created_at, updated_at)
        SELECT id, portfolio_id, asset_type,
               CAST(target_percentage AS TEXT), CAST(rebalance_threshold AS TEXT),
               created_at, updated_at
        FROM target_allocations_old
    """)
    count = conn.execute("SELECT COUNT(*) FROM target_allocations").fetchone()[0]
    conn.execute("DROP TABLE target_allocations_old")
    print(f"   Migrated {count} target allocations.")


def _create_tax_lots(conn):
    print("\nCreating tax_lots table...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tax_lots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            holding_id INTEGER NOT NULL,
            buy_transaction_id INTEGER,
            acquired_date TIMESTAMP NOT NULL,
            quantity TEXT NOT NULL,
            cost_per_unit TEXT NOT NULL,
            quantity_remaining TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (holding_id) REFERENCES holdings(id) ON DELETE CASCADE
        )
    """)


def _seed_tax_lots(conn):
    """
    Seed tax_lots from existing buy transactions.
    FIFO-adjusts quantity_remaining to match the actual remaining shares per holding.
    """
    print("Seeding tax_lots from existing buy transactions...")

    # Fetch all buy transactions grouped by holding
    buy_rows = conn.execute("""
        SELECT id, holding_id, quantity, price, transaction_date
        FROM transactions
        WHERE transaction_type = 'buy'
        ORDER BY holding_id, transaction_date ASC, id ASC
    """).fetchall()

    # Group by holding_id
    by_holding = defaultdict(list)
    for row in buy_rows:
        by_holding[row["holding_id"]].append(dict(row))

    lot_count = 0
    for holding_id, buys in by_holding.items():
        # Get current remaining shares
        h_row = conn.execute(
            "SELECT shares FROM holdings WHERE id = ?", (holding_id,)
        ).fetchone()
        if h_row is None:
            continue

        remaining_shares = Decimal(str(h_row["shares"]))
        total_bought = sum(Decimal(str(b["quantity"])) for b in buys)

        # How many shares have been consumed by historical sells?
        to_consume = total_bought - remaining_shares

        for buy in buys:
            qty = Decimal(str(buy["quantity"]))
            this_consumed = min(to_consume, qty)
            qty_remaining = qty - this_consumed
            to_consume = max(to_consume - this_consumed, Decimal("0"))

            conn.execute("""
                INSERT INTO tax_lots
                    (holding_id, buy_transaction_id, acquired_date,
                     quantity, cost_per_unit, quantity_remaining)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                holding_id,
                buy["id"],
                buy["transaction_date"],
                str(qty),
                str(Decimal(str(buy["price"]))),
                str(qty_remaining),
            ))
            lot_count += 1

    print(f"   Created {lot_count} tax lots.")


def _rebuild_indexes(conn):
    print("Rebuilding indexes...")
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_holdings_portfolio ON holdings(portfolio_id);
        CREATE INDEX IF NOT EXISTS idx_transactions_holding ON transactions(holding_id);
        CREATE INDEX IF NOT EXISTS idx_price_history_holding ON price_history(holding_id);
        CREATE INDEX IF NOT EXISTS idx_target_allocations_portfolio ON target_allocations(portfolio_id);
        CREATE INDEX IF NOT EXISTS idx_cash_transactions_portfolio ON cash_transactions(portfolio_id);
        CREATE INDEX IF NOT EXISTS idx_tax_lots_holding ON tax_lots(holding_id, acquired_date);
    """)


def _verify(conn):
    print("\nVerification:")
    # Check column types
    row = conn.execute("SELECT shares, cost_basis FROM holdings LIMIT 1").fetchone()
    if row:
        shares_val = row[0]
        print(f"  holdings.shares type: {type(shares_val).__name__!r}  value: {shares_val!r}")
        assert isinstance(shares_val, str), "Expected TEXT (str), got something else!"

    tx_row = conn.execute("SELECT quantity, price FROM transactions LIMIT 1").fetchone()
    if tx_row:
        qty_val = tx_row[0]
        print(f"  transactions.quantity type: {type(qty_val).__name__!r}  value: {qty_val!r}")
        assert isinstance(qty_val, str), "Expected TEXT (str)!"

    lot_count = conn.execute("SELECT COUNT(*) FROM tax_lots").fetchone()[0]
    print(f"  tax_lots rows: {lot_count}")
    print("\nAll checks passed.")


if __name__ == "__main__":
    root = find_project_root()
    db_path = root / "portfolio.db"

    if not db_path.exists():
        print(f"ERROR: {db_path} not found.")
        sys.exit(1)

    migrate(db_path)
