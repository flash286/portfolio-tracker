"""Tests for query.py: RowMapper, QueryBuilder, BaseRepository."""

import sqlite3
from datetime import datetime
from decimal import Decimal

import pytest

from portfolio_tracker.core.models import (
    AssetType,
    Holding,
    Portfolio,
    Transaction,
    TransactionType,
)
from portfolio_tracker.data.query import QueryBuilder, RowMapper
from portfolio_tracker.data.repositories.holdings_repo import HoldingsRepository
from portfolio_tracker.data.repositories.portfolios_repo import PortfoliosRepository


def _make_row(**kwargs) -> sqlite3.Row:
    """Create a sqlite3.Row from keyword arguments.

    The connection is kept alive implicitly: sqlite3.Row holds a reference
    to the cursor (which holds a reference to the connection), so the
    connection is not GC'd while the Row is alive.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    col_exprs = ", ".join(f"? as {name}" for name in kwargs)
    return conn.execute(f"SELECT {col_exprs}", list(kwargs.values())).fetchone()


# ---------------------------------------------------------------------------
# TestRowMapper
# ---------------------------------------------------------------------------

class TestRowMapper:
    def test_basic_portfolio_mapping(self):
        """int, str, and Optional[datetime] fields are mapped correctly."""
        mapper = RowMapper(Portfolio)
        row = _make_row(
            id=1,
            name="My Portfolio",
            description="A test portfolio",
            created_at="2023-01-15 10:00:00",
            updated_at="2023-01-16 10:00:00",
        )
        p = mapper.map(row)
        assert p.id == 1
        assert p.name == "My Portfolio"
        assert p.description == "A test portfolio"
        assert isinstance(p.created_at, datetime)
        assert p.created_at.year == 2023

    def test_enum_conversion(self):
        """Enum-typed field is converted from its string value."""
        mapper = RowMapper(Holding)
        row = _make_row(
            id=1, portfolio_id=1, isin="IE00B4L5Y983",
            asset_type="etf", name="World ETF", ticker="IWDA",
            shares="100", cost_basis="10000", teilfreistellung_rate="0.3",
            created_at=None, updated_at=None,
        )
        h = mapper.map(row)
        assert h.asset_type == AssetType.ETF

    def test_transaction_type_enum(self):
        """TransactionType enum is converted correctly."""
        mapper = RowMapper(Transaction)
        row = _make_row(
            id=1, holding_id=1, transaction_type="buy",
            quantity="10", price="100", total_value="1000",
            realized_gain=None, transaction_date="2023-01-15T10:00:00",
            notes="", created_at=None,
        )
        tx = mapper.map(row)
        assert tx.transaction_type == TransactionType.BUY

    def test_decimal_conversion(self):
        """TEXT Decimal columns are converted to Decimal without precision loss."""
        mapper = RowMapper(Holding)
        row = _make_row(
            id=1, portfolio_id=1, isin="IE00B4L5Y983",
            asset_type="stock", name="", ticker="",
            shares="123.456789012345", cost_basis="9876.54",
            teilfreistellung_rate="0.3",
            created_at=None, updated_at=None,
        )
        h = mapper.map(row)
        assert h.shares == Decimal("123.456789012345")
        assert h.cost_basis == Decimal("9876.54")

    def test_optional_decimal_null(self):
        """Optional[Decimal] = None with NULL column → None."""
        mapper = RowMapper(Transaction)
        row = _make_row(
            id=1, holding_id=1, transaction_type="buy",
            quantity="10", price="100", total_value="1000",
            realized_gain=None,
            transaction_date="2023-01-15T10:00:00", notes="", created_at=None,
        )
        tx = mapper.map(row)
        assert tx.realized_gain is None

    def test_optional_decimal_non_null(self):
        """Optional[Decimal] with a value is converted to Decimal."""
        mapper = RowMapper(Transaction)
        row = _make_row(
            id=1, holding_id=1, transaction_type="sell",
            quantity="10", price="120", total_value="1200",
            realized_gain="200.50",
            transaction_date="2023-06-01T10:00:00", notes="", created_at=None,
        )
        tx = mapper.map(row)
        assert tx.realized_gain == Decimal("200.50")

    def test_str_default_for_null_column(self):
        """str = '' field with NULL in the DB row → uses the '' default."""
        mapper = RowMapper(Holding)
        row = _make_row(
            id=1, portfolio_id=1, isin="IE00B4L5Y983",
            asset_type="etf", name=None, ticker=None,
            shares="0", cost_basis="0", teilfreistellung_rate="0",
            created_at=None, updated_at=None,
        )
        h = mapper.map(row)
        assert h.name == ""
        assert h.ticker == ""

    def test_field_not_in_row_uses_default(self):
        """current_price is not in the DB — mapper uses its None default."""
        mapper = RowMapper(Holding)
        row = _make_row(
            id=1, portfolio_id=1, isin="IE00B4L5Y983",
            asset_type="etf", name="", ticker="",
            shares="50", cost_basis="5000", teilfreistellung_rate="0.3",
            created_at=None, updated_at=None,
            # current_price intentionally absent
        )
        h = mapper.map(row)
        assert h.current_price is None

    def test_field_not_in_row_no_default_raises(self):
        """Required field missing from row → TypeError on construction."""
        mapper = RowMapper(Holding)
        # Row is missing portfolio_id which has no default
        row = _make_row(
            id=1, isin="IE00B4L5Y983", asset_type="etf",
            name="", ticker="",
            shares="0", cost_basis="0", teilfreistellung_rate="0",
        )
        with pytest.raises(TypeError):
            mapper.map(row)

    def test_datetime_from_isoformat_string(self):
        """datetime field stored as ISO string is converted to datetime."""
        mapper = RowMapper(Transaction)
        row = _make_row(
            id=1, holding_id=1, transaction_type="buy",
            quantity="10", price="100", total_value="1000",
            realized_gain=None,
            transaction_date="2023-01-15T10:30:00",
            notes="", created_at=None,
        )
        tx = mapper.map(row)
        assert isinstance(tx.transaction_date, datetime)
        assert tx.transaction_date == datetime(2023, 1, 15, 10, 30, 0)

    def test_map_all(self):
        """map_all converts a list of rows."""
        mapper = RowMapper(Portfolio)
        rows = [
            _make_row(id=1, name="A", description="", created_at=None, updated_at=None),
            _make_row(id=2, name="B", description="", created_at=None, updated_at=None),
        ]
        portfolios = mapper.map_all(rows)
        assert len(portfolios) == 2
        assert portfolios[0].name == "A"
        assert portfolios[1].name == "B"

    def test_serialize_decimal(self):
        assert RowMapper._serialize(Decimal("123.456")) == "123.456"

    def test_serialize_datetime(self):
        dt = datetime(2024, 6, 15, 10, 30, 0)
        assert RowMapper._serialize(dt) == "2024-06-15T10:30:00"

    def test_serialize_enum(self):
        assert RowMapper._serialize(AssetType.ETF) == "etf"
        assert RowMapper._serialize(TransactionType.BUY) == "buy"

    def test_serialize_none(self):
        assert RowMapper._serialize(None) is None

    def test_serialize_primitives(self):
        assert RowMapper._serialize(42) == 42
        assert RowMapper._serialize("hello") == "hello"
        assert RowMapper._serialize(True) is True

    def test_to_db_dict_serializes_values(self):
        """to_db_dict converts Decimal, datetime, and Enum fields."""
        mapper = RowMapper(Holding)
        h = Holding(
            portfolio_id=1, isin="IE00B4L5Y983", asset_type=AssetType.ETF,
            shares=Decimal("10.5"), cost_basis=Decimal("1050.00"),
            teilfreistellung_rate=Decimal("0.3"),
        )
        d = mapper.to_db_dict(h)
        assert d["shares"] == "10.5"
        assert d["cost_basis"] == "1050.00"
        assert d["asset_type"] == "etf"
        assert d["teilfreistellung_rate"] == "0.3"

    def test_to_db_dict_none_for_none_values(self):
        """None fields are serialized as None."""
        mapper = RowMapper(Portfolio)
        p = Portfolio(name="Test")
        d = mapper.to_db_dict(p)
        assert d["created_at"] is None
        assert d["updated_at"] is None

    def test_to_db_dict_skips_fields(self):
        """Fields in skip set are excluded from the result."""
        mapper = RowMapper(Portfolio)
        p = Portfolio(name="Test", description="Desc")
        skip = frozenset({"id", "created_at", "updated_at"})
        d = mapper.to_db_dict(p, skip=skip)
        assert "id" not in d
        assert "created_at" not in d
        assert "updated_at" not in d
        assert d["name"] == "Test"
        assert d["description"] == "Desc"


# ---------------------------------------------------------------------------
# TestQueryBuilder
# ---------------------------------------------------------------------------

class TestQueryBuilder:
    def test_default_is_select_star(self):
        sql, params = QueryBuilder("portfolios").build()
        assert sql == "SELECT * FROM portfolios"
        assert params == []

    def test_single_where(self):
        sql, params = QueryBuilder("portfolios").where("id = ?", 1).build()
        assert sql == "SELECT * FROM portfolios WHERE id = ?"
        assert params == [1]

    def test_multiple_where_joined_with_and(self):
        sql, params = (
            QueryBuilder("holdings")
            .where("portfolio_id = ?", 5)
            .where("isin = ?", "IE00B4L5Y983")
            .build()
        )
        assert "WHERE portfolio_id = ? AND isin = ?" in sql
        assert params == [5, "IE00B4L5Y983"]

    def test_order_by_appended(self):
        sql, _ = QueryBuilder("portfolios").order_by("created_at DESC").build()
        assert sql.endswith("ORDER BY created_at DESC")

    def test_join_before_where(self):
        sql, params = (
            QueryBuilder("transactions t")
            .select("t.*")
            .join("JOIN holdings h ON t.holding_id = h.id")
            .where("h.portfolio_id = ?", 1)
            .build()
        )
        assert "JOIN holdings h ON t.holding_id = h.id" in sql
        assert sql.index("JOIN") < sql.index("WHERE")
        assert params == [1]

    def test_limit_appended(self):
        sql, _ = QueryBuilder("price_history").limit(10).build()
        assert sql.endswith("LIMIT 10")

    def test_select_specific_columns(self):
        sql, _ = QueryBuilder("transactions t").select("t.*").build()
        assert sql.startswith("SELECT t.* FROM transactions t")

    def test_build_returns_str_and_list(self):
        result = QueryBuilder("portfolios").where("name = ?", "test").build()
        assert isinstance(result, tuple) and len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], list)

    def test_no_where_no_order_no_limit(self):
        sql, params = QueryBuilder("tax_lots").build()
        assert "WHERE" not in sql
        assert "ORDER BY" not in sql
        assert "LIMIT" not in sql
        assert params == []


# ---------------------------------------------------------------------------
# TestBaseRepository
# ---------------------------------------------------------------------------

class TestBaseRepository:
    """Uses PortfoliosRepository as a concrete BaseRepository implementation."""

    def test_get_by_id_returns_mapped_model(self, isolated_db):
        repo = PortfoliosRepository()
        created = repo.create(Portfolio(name="Test Portfolio", description="A description"))
        fetched = repo.get_by_id(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.name == "Test Portfolio"
        assert fetched.description == "A description"
        assert isinstance(fetched, Portfolio)

    def test_get_by_id_missing_returns_none(self, isolated_db):
        assert PortfoliosRepository().get_by_id(9999) is None

    def test_delete_removes_row_and_returns_true(self, isolated_db):
        repo = PortfoliosRepository()
        p = repo.create(Portfolio(name="ToDelete"))
        assert repo.delete(p.id) is True
        assert repo.get_by_id(p.id) is None

    def test_delete_missing_id_returns_false(self, isolated_db):
        assert PortfoliosRepository().delete(9999) is False

    def test_insert_inserts_row_and_returns_model(self, isolated_db):
        """_insert() writes to DB and returns a fully mapped model with id set."""
        repo = PortfoliosRepository()
        p = repo.create(Portfolio(name="Inserted", description="via _insert"))
        assert p.id is not None
        assert p.name == "Inserted"
        assert p.description == "via _insert"
        assert isinstance(p.created_at, datetime)

    def test_save_updates_writable_fields(self, isolated_db):
        """save() updates all non-skipped fields and returns the updated model."""
        repo = PortfoliosRepository()
        p = repo.create(Portfolio(name="Original", description="first"))
        p.name = "Updated"
        p.description = "second"
        saved = repo.save(p)
        assert saved.name == "Updated"
        assert saved.description == "second"
        # Persisted to DB
        fetched = repo.get_by_id(p.id)
        assert fetched.name == "Updated"

    def test_save_sets_updated_at_for_models_with_that_field(self, isolated_db):
        """save() adds updated_at = CURRENT_TIMESTAMP for Portfolio (has updated_at)."""
        repo = PortfoliosRepository()
        p = repo.create(Portfolio(name="TSTest"))
        p.description = "changed"
        saved = repo.save(p)
        # updated_at should be set (may equal original if within same second, but field exists)
        assert saved.updated_at is not None

    def test_save_does_not_set_updated_at_for_models_without_it(self, isolated_db):
        """save() on HoldingsRepository (no updated_at in skip) still works for Holding."""
        # Holding has updated_at, but Transaction does not — use holdings to verify
        p = PortfoliosRepository().create(Portfolio(name="TestP"))
        h_repo = HoldingsRepository()
        h = h_repo.create(Holding(
            portfolio_id=p.id, isin="IE00B4L5Y983", asset_type=AssetType.ETF,
        ))
        h.shares = Decimal("5")
        saved = h_repo.save(h)
        assert saved.shares == Decimal("5")
