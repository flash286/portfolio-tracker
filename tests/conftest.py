"""Shared pytest fixtures for portfolio tracker tests."""

import pytest

import portfolio_tracker.data.database as dbmod
from portfolio_tracker.data.database import get_db, set_db_path


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    """Each test gets a fresh temp DB. Resets the global singleton after."""
    db_path = tmp_path / "test.db"
    set_db_path(str(db_path))
    db = get_db()
    yield db
    db.conn.close()
    dbmod._db = None
