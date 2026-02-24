"""SQLite database connection and schema management."""

import sqlite3
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
    shares REAL NOT NULL DEFAULT 0,
    cost_basis REAL NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
    UNIQUE(portfolio_id, isin)
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    holding_id INTEGER NOT NULL,
    transaction_type TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    total_value REAL NOT NULL,
    transaction_date TIMESTAMP NOT NULL,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (holding_id) REFERENCES holdings(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    holding_id INTEGER NOT NULL,
    price REAL NOT NULL,
    fetch_date TIMESTAMP NOT NULL,
    source TEXT DEFAULT '',
    FOREIGN KEY (holding_id) REFERENCES holdings(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS target_allocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL,
    asset_type TEXT NOT NULL,
    target_percentage REAL NOT NULL,
    rebalance_threshold REAL DEFAULT 5.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
    UNIQUE(portfolio_id, asset_type)
);

CREATE INDEX IF NOT EXISTS idx_holdings_portfolio ON holdings(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_transactions_holding ON transactions(holding_id);
CREATE INDEX IF NOT EXISTS idx_price_history_holding ON price_history(holding_id);
CREATE INDEX IF NOT EXISTS idx_target_allocations_portfolio ON target_allocations(portfolio_id);
"""


class Database:
    def __init__(self, db_path: str = "portfolio.db"):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def initialize(self):
        """Create tables if they don't exist."""
        self.conn.executescript(SCHEMA)
        self.conn.commit()

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
