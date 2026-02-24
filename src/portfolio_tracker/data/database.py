"""SQLite database connection and schema management."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS portfolios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS holdings (
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
);

CREATE TABLE IF NOT EXISTS transactions (
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
);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    holding_id INTEGER NOT NULL,
    price TEXT NOT NULL,
    fetch_date TIMESTAMP NOT NULL,
    source TEXT DEFAULT '',
    FOREIGN KEY (holding_id) REFERENCES holdings(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS target_allocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL,
    asset_type TEXT NOT NULL,
    target_percentage TEXT NOT NULL,
    rebalance_threshold TEXT DEFAULT '5.0',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
    UNIQUE(portfolio_id, asset_type)
);

CREATE TABLE IF NOT EXISTS cash_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL,
    cash_type TEXT NOT NULL,
    amount TEXT NOT NULL,
    transaction_date TIMESTAMP NOT NULL,
    description TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE
);

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
);

CREATE INDEX IF NOT EXISTS idx_holdings_portfolio ON holdings(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_transactions_holding ON transactions(holding_id);
CREATE INDEX IF NOT EXISTS idx_price_history_holding ON price_history(holding_id);
CREATE INDEX IF NOT EXISTS idx_target_allocations_portfolio ON target_allocations(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_cash_transactions_portfolio ON cash_transactions(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_tax_lots_holding ON tax_lots(holding_id, acquired_date);

CREATE TABLE IF NOT EXISTS vorabpauschale_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    total_vp TEXT NOT NULL,
    tfs_exempt TEXT NOT NULL,
    taxable_vp TEXT NOT NULL,
    fsa_used TEXT NOT NULL,
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(portfolio_id, year),
    FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE
);
"""


# Incremental column additions for existing databases.
# Each entry is (table, column, DDL fragment). Safe to run multiple times —
# the ALTER TABLE is silently skipped if the column already exists.
_COLUMN_MIGRATIONS = [
    ("holdings", "teilfreistellung_rate",
     "ALTER TABLE holdings ADD COLUMN teilfreistellung_rate TEXT NOT NULL DEFAULT '0'"),
    ("transactions", "realized_gain",
     "ALTER TABLE transactions ADD COLUMN realized_gain TEXT DEFAULT NULL"),
]


def _apply_column_migrations(conn: sqlite3.Connection):
    """Add new columns to existing tables without touching data."""
    for _table, _col, sql in _COLUMN_MIGRATIONS:
        try:
            conn.execute(sql)
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists — safe to ignore


class Database:
    def __init__(self, db_path: str = "portfolio.db"):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._in_transaction: bool = False

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def initialize(self):
        """Create tables if they don't exist, then apply incremental column migrations."""
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        _apply_column_migrations(self.conn)

    @contextmanager
    def transaction(self):
        """Wrap multiple operations in a single atomic commit."""
        self._in_transaction = True
        try:
            yield
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        finally:
            self._in_transaction = False

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None


# Global database instance — configured at app startup
_db: Database | None = None


def _find_project_root() -> Path:
    """Walk up from this file to find the project root (where pyproject.toml lives)."""
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    # Fallback: current working directory
    return Path.cwd()


def get_db() -> Database:
    global _db
    if _db is None:
        # Prefer project-local DB (next to pyproject.toml)
        project_root = _find_project_root()
        default_path = project_root / "portfolio.db"
        default_path.parent.mkdir(parents=True, exist_ok=True)
        _db = Database(str(default_path))
        _db.initialize()
    return _db


def set_db_path(path: str):
    global _db
    if _db:
        _db.close()
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    _db = Database(str(p))
    _db.initialize()
