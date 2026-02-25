"""Lightweight query builder and base repository for SQLite repositories."""

import dataclasses
import sqlite3
import typing
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Generic, Optional, TypeVar

from .database import Database, get_db

T = TypeVar("T")


class RowMapper(Generic[T]):
    """Maps sqlite3.Row objects to dataclass instances using type hints."""

    def __init__(self, model_class: type[T]):
        self._model_class = model_class
        self._fields = dataclasses.fields(model_class)  # type: ignore[arg-type]
        self._hints = typing.get_type_hints(model_class)
        self._converters = {
            f.name: self._get_converter(self._hints.get(f.name))
            for f in self._fields
        }

    def _get_converter(self, hint):
        if hint is None:
            return None

        origin = typing.get_origin(hint)
        args = typing.get_args(hint)

        # Optional[X] = Union[X, None]
        if origin is typing.Union:
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                inner_conv = self._get_converter(non_none[0])
                if inner_conv is None:
                    return None
                return lambda v, c=inner_conv: c(v) if v is not None else None
            return None

        if hint is Decimal:
            return lambda v: Decimal(str(v))
        if hint is datetime:
            return lambda v: datetime.fromisoformat(v) if isinstance(v, str) else v
        if hint is int:
            return int
        if hint is str:
            return str
        if isinstance(hint, type) and issubclass(hint, Enum):
            return lambda v, cls=hint: cls(v)

        return None

    def map(self, row: sqlite3.Row) -> T:
        kwargs: dict = {}
        row_keys = row.keys()
        for f in self._fields:
            if f.name not in row_keys:
                # Field not in DB row — use default if available
                if f.default is not dataclasses.MISSING:
                    kwargs[f.name] = f.default
                elif f.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
                    kwargs[f.name] = f.default_factory()  # type: ignore[misc]
                # else: leave missing — ModelClass(**kwargs) will raise TypeError
                continue

            raw = row[f.name]
            if raw is None:
                if f.default is not dataclasses.MISSING:
                    kwargs[f.name] = f.default
                elif f.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
                    kwargs[f.name] = f.default_factory()  # type: ignore[misc]
                else:
                    kwargs[f.name] = None
            else:
                conv = self._converters.get(f.name)
                kwargs[f.name] = conv(raw) if conv else raw

        return self._model_class(**kwargs)

    def map_all(self, rows) -> list[T]:
        return [self.map(r) for r in rows]

    @staticmethod
    def _serialize(val):
        """Convert Python value → SQLite-compatible value."""
        if val is None:
            return None
        if isinstance(val, Decimal):
            return str(val)
        if isinstance(val, datetime):
            return val.isoformat()
        if isinstance(val, Enum):
            return val.value
        return val  # int, str, bool as-is

    def to_db_dict(self, obj: T, skip: frozenset = frozenset()) -> dict:
        """Return {field_name: serialized_value} for all non-skipped fields."""
        return {
            f.name: self._serialize(getattr(obj, f.name))
            for f in self._fields
            if f.name not in skip
        }


class QueryBuilder:
    """Fluent SELECT query builder for SQLite."""

    def __init__(self, table: str):
        self._table = table
        self._columns: list[str] = ["*"]
        self._joins: list[str] = []
        self._conditions: list[str] = []
        self._params: list = []
        self._order: Optional[str] = None
        self._limit_val: Optional[int] = None

    def select(self, *columns: str) -> "QueryBuilder":
        self._columns = list(columns)
        return self

    def join(self, clause: str) -> "QueryBuilder":
        self._joins.append(clause)
        return self

    def where(self, condition: str, *params) -> "QueryBuilder":
        self._conditions.append(condition)
        self._params.extend(params)
        return self

    def order_by(self, clause: str) -> "QueryBuilder":
        self._order = clause
        return self

    def limit(self, n: int) -> "QueryBuilder":
        self._limit_val = n
        return self

    def build(self) -> tuple[str, list]:
        sql = f"SELECT {', '.join(self._columns)} FROM {self._table}"
        for join in self._joins:
            sql += f" {join}"
        if self._conditions:
            sql += " WHERE " + " AND ".join(self._conditions)
        if self._order:
            sql += f" ORDER BY {self._order}"
        if self._limit_val is not None:
            sql += f" LIMIT {self._limit_val}"
        return sql, list(self._params)

    def fetch_one(self, conn: sqlite3.Connection) -> Optional[sqlite3.Row]:
        sql, params = self.build()
        return conn.execute(sql, params).fetchone()

    def fetch_all(self, conn: sqlite3.Connection) -> list[sqlite3.Row]:
        sql, params = self.build()
        return conn.execute(sql, params).fetchall()


class BaseRepository(Generic[T]):
    """Abstract base providing get_by_id, delete, _query, and _commit helpers."""

    _table: str
    _mapper: RowMapper  # type: ignore[type-arg]
    _insert_skip: frozenset = frozenset({"id", "created_at", "updated_at"})

    def _db(self) -> Database:
        return get_db()

    def _commit(self, db: Database) -> None:
        if not db._in_transaction:
            db.conn.commit()

    def _query(self) -> QueryBuilder:
        return QueryBuilder(self._table)

    def get_by_id(self, id: int) -> Optional[T]:
        row = self._query().where("id = ?", id).fetch_one(self._db().conn)
        return self._mapper.map(row) if row else None

    def delete(self, id: int) -> bool:
        db = self._db()
        cursor = db.conn.execute(
            f"DELETE FROM {self._table} WHERE id = ?", (id,)
        )
        self._commit(db)
        return cursor.rowcount > 0

    def _insert(self, obj: T) -> T:
        """Generic INSERT: serializes all non-skipped fields and returns the new row."""
        db = self._db()
        row_dict = self._mapper.to_db_dict(obj, skip=self._insert_skip)
        cols = ", ".join(row_dict)
        placeholders = ", ".join("?" * len(row_dict))
        cursor = db.conn.execute(
            f"INSERT INTO {self._table} ({cols}) VALUES ({placeholders})",
            list(row_dict.values()),
        )
        self._commit(db)
        return self.get_by_id(cursor.lastrowid)

    def _insert_with_source_id(
        self, obj: T, source_id: str, extra_fields: Optional[dict] = None
    ) -> Optional[T]:
        """INSERT OR IGNORE with a source_id column for idempotent imports.

        Returns None if the row already exists (duplicate source_id).
        Pass extra_fields for computed columns not present in the dataclass.
        """
        db = self._db()
        row_dict = self._mapper.to_db_dict(obj, skip=self._insert_skip)
        if extra_fields:
            row_dict.update(extra_fields)
        row_dict["source_id"] = source_id
        cols = ", ".join(row_dict)
        placeholders = ", ".join("?" * len(row_dict))
        cursor = db.conn.execute(
            f"INSERT OR IGNORE INTO {self._table} ({cols}) VALUES ({placeholders})",
            list(row_dict.values()),
        )
        self._commit(db)
        if cursor.rowcount == 0:
            return None
        return self.get_by_id(cursor.lastrowid)

    def save(self, obj: T) -> T:
        """Generic UPDATE by obj.id: serializes all non-skipped fields."""
        db = self._db()
        row_dict = self._mapper.to_db_dict(obj, skip=self._insert_skip)
        set_parts = [f"{col} = ?" for col in row_dict]
        if any(f.name == "updated_at" for f in self._mapper._fields):
            set_parts.append("updated_at = CURRENT_TIMESTAMP")
        db.conn.execute(
            f"UPDATE {self._table} SET {', '.join(set_parts)} WHERE id = ?",
            [*row_dict.values(), obj.id],
        )
        self._commit(db)
        return self.get_by_id(obj.id)
