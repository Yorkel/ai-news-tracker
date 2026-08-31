"""
pg_client.py
A Postgres-backed stand-in for the Supabase client.

Why this exists
---------------
The pipeline was written against Supabase's PostgREST fluent API
(`client.table("articles").select("*").eq("source", x).execute().data`) in 73
places across 20 files. Moving to a plain Postgres database would otherwise
mean rewriting every one of them into SQL.

This class implements the subset of that API the codebase actually uses, so
those call sites run unchanged against any Postgres server — a local instance,
Neon, RDS, or a future Supabase project.

Surveyed surface (2026-08-29) — everything the repo calls:
    .table()  .select()  .insert()  .upsert()  .update()  .delete()
    .eq()  .gte()  .lte()  .in_()  .like()  .order()  .limit()  .range()
    .execute()  ->  object with .data (list[dict])

Deliberately NOT implemented, because nothing calls them: .single(),
.maybe_single(), .neq(), .is_(), .not_(), .rpc(), and the `count=` argument to
select(). They raise AttributeError/TypeError rather than silently returning
wrong results — a loud failure is the point.

Usage:
    from src.scraping.pg_client import PgClient
    client = PgClient("postgresql://...")
    rows = client.table("articles").select("*").limit(10).execute().data
"""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row


class _Response:
    """Mimics the Supabase APIResponse: only `.data` is ever read."""

    def __init__(self, data: list[dict]):
        self.data = data

    def __repr__(self) -> str:
        return f"_Response(rows={len(self.data)})"


class _Query:
    """Accumulates a query, then renders it to parameterised SQL on execute().

    Values are ALWAYS passed as psycopg parameters, never interpolated, so a
    title containing a quote cannot break or inject into the statement.
    Identifiers (table and column names) come from the codebase, not user
    input, but are still validated against a conservative pattern.
    """

    def __init__(self, conn_factory, table: str):
        self._conn_factory = conn_factory
        self._table = _ident(table)
        self._op: str | None = None
        self._columns = "*"
        self._values: list[dict] | dict | None = None
        self._on_conflict: str | None = None
        self._where: list[tuple[str, str, Any]] = []
        self._order: list[tuple[str, bool]] = []
        self._limit: int | None = None
        self._offset: int | None = None

    # ---- operations -----------------------------------------------------
    def select(self, columns: str = "*"):
        self._op = "select"
        cols = (columns or "*").strip()
        if cols != "*":
            cols = ", ".join(_ident(c.strip()) for c in cols.split(",") if c.strip())
        self._columns = cols
        return self

    def insert(self, records):
        self._op = "insert"
        self._values = [records] if isinstance(records, dict) else list(records)
        return self

    def upsert(self, records, *, on_conflict: str = "url"):
        self._op = "upsert"
        self._values = [records] if isinstance(records, dict) else list(records)
        self._on_conflict = _ident(on_conflict)
        return self

    def update(self, values: dict):
        self._op = "update"
        self._values = values
        return self

    def delete(self):
        self._op = "delete"
        return self

    # ---- filters --------------------------------------------------------
    def eq(self, column: str, value: Any):   return self._filter(column, "=", value)
    def gte(self, column: str, value: Any):  return self._filter(column, ">=", value)
    def lte(self, column: str, value: Any):  return self._filter(column, "<=", value)
    def like(self, column: str, value: Any): return self._filter(column, "LIKE", value)

    def in_(self, column: str, values):
        vals = list(values)
        if not vals:
            # PostgREST returns nothing for an empty IN; `x = ANY('{}')` does too,
            # but be explicit so the intent survives review.
            self._where.append((_ident(column), "IN_EMPTY", None))
        else:
            self._where.append((_ident(column), "= ANY", vals))
        return self

    def _filter(self, column: str, op: str, value: Any):
        self._where.append((_ident(column), op, value))
        return self

    # ---- ordering / paging ----------------------------------------------
    def order(self, column: str, *, desc: bool = False):
        self._order.append((_ident(column), desc))
        return self

    def limit(self, n: int):
        self._limit = int(n)
        return self

    def range(self, start: int, end: int):
        """PostgREST .range() is INCLUSIVE at both ends: range(0, 999) is 1000 rows."""
        self._offset = int(start)
        self._limit = int(end) - int(start) + 1
        return self

    # ---- render + run ---------------------------------------------------
    def _where_sql(self) -> tuple[str, list]:
        if not self._where:
            return "", []
        parts, params = [], []
        for col, op, val in self._where:
            if op == "IN_EMPTY":
                parts.append("false")
            elif op == "= ANY":
                parts.append(f"{col} = ANY(%s)")
                params.append(val)
            else:
                parts.append(f"{col} {op} %s")
                params.append(val)
        return " WHERE " + " AND ".join(parts), params

    def _build(self) -> tuple[str, list]:
        if self._op == "select":
            sql = f"SELECT {self._columns} FROM {self._table}"
            where, params = self._where_sql()
            sql += where
            if self._order:
                sql += " ORDER BY " + ", ".join(
                    f"{c} {'DESC' if d else 'ASC'}" for c, d in self._order
                )
            if self._limit is not None:
                sql += f" LIMIT {self._limit}"
            if self._offset:
                sql += f" OFFSET {self._offset}"
            return sql, params

        if self._op in ("insert", "upsert"):
            rows = self._values or []
            if not rows:
                return "", []
            cols = list(rows[0].keys())
            collist = ", ".join(_ident(c) for c in cols)
            ph = "(" + ", ".join(["%s"] * len(cols)) + ")"
            sql = f"INSERT INTO {self._table} ({collist}) VALUES " + ", ".join([ph] * len(rows))
            params: list = []
            for r in rows:
                params.extend(r.get(c) for c in cols)
            if self._op == "upsert":
                setters = ", ".join(
                    f"{_ident(c)} = EXCLUDED.{_ident(c)}" for c in cols if c != self._on_conflict
                )
                sql += f" ON CONFLICT ({self._on_conflict}) DO " + (
                    f"UPDATE SET {setters}" if setters else "NOTHING"
                )
            return sql + " RETURNING *", params

        if self._op == "update":
            vals = self._values or {}
            cols = list(vals.keys())
            sql = f"UPDATE {self._table} SET " + ", ".join(f"{_ident(c)} = %s" for c in cols)
            params = [vals[c] for c in cols]
            where, wp = self._where_sql()
            sql += where
            return sql + " RETURNING *", params + wp

        if self._op == "delete":
            where, params = self._where_sql()
            return f"DELETE FROM {self._table}{where} RETURNING *", params

        raise RuntimeError("no operation set — call .select()/.insert()/.upsert()/.update()/.delete()")

    def execute(self) -> _Response:
        sql, params = self._build()
        if not sql:                      # empty insert/upsert batch
            return _Response([])
        with self._conn_factory() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall() if cur.description else []
            conn.commit()
        return _Response([dict(r) for r in rows])


class PgClient:
    """Drop-in replacement for the Supabase client, backed by Postgres."""

    def __init__(self, dsn: str):
        self.dsn = dsn

    def _conn(self):
        return psycopg.connect(self.dsn)

    def table(self, name: str) -> _Query:
        return _Query(self._conn, name)

    # Supabase exposes .from_() as an alias for .table()
    def from_(self, name: str) -> _Query:
        return self.table(name)


def _ident(name: str) -> str:
    """Validate and quote an SQL identifier. Rejects anything that is not a
    plain column/table name so a malformed config cannot become injection."""
    n = (name or "").strip()
    if not n or not all(ch.isalnum() or ch == "_" for ch in n):
        raise ValueError(f"unsafe SQL identifier: {name!r}")
    return f'"{n}"'
