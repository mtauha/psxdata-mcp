"""Session-local, sandboxed DuckDB store."""

from __future__ import annotations

import threading
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

import duckdb
import pandas as pd

MAX_ROWS = 200
MAX_CELL = 100
QUERY_TIMEOUT_S = 30.0

# lock_configuration must come last so queries can't undo the rest.
_SANDBOX = (
    "SET autoload_known_extensions = false",
    "SET autoinstall_known_extensions = false",
    "SET allow_community_extensions = false",
    "SET enable_external_access = false",
    "SET memory_limit = '1GB'",
    "SET threads = 2",
    "SET lock_configuration = true",
)


class QueryError(Exception):
    pass


class QueryTimeout(QueryError):
    pass


@dataclass(frozen=True)
class TableInfo:
    name: str
    rows: int | None
    loaded_at: datetime | None
    kind: str


def _cell(value: object) -> str:
    if value is None:
        return "NULL"
    text = str(value).replace("\n", " ").replace("|", "\\|")
    return text if len(text) <= MAX_CELL else text[: MAX_CELL - 1] + "…"


def _markdown(columns: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    lines = [
        "| " + " | ".join(columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    lines += ["| " + " | ".join(_cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


class Store:
    def __init__(self, timeout_s: float = QUERY_TIMEOUT_S) -> None:
        self._con = duckdb.connect(":memory:")
        for statement in _SANDBOX:
            self._con.execute(statement)
        self._lock = threading.Lock()
        self._loaded: dict[str, datetime] = {}
        self._timeout_s = timeout_s

    def _exists(self, table: str) -> bool:
        row = self._con.execute(
            "SELECT 1 FROM duckdb_tables() WHERE table_name = ?", [table]
        ).fetchone()
        return row is not None

    def replace(self, table: str, df: pd.DataFrame) -> None:
        with self._lock:
            self._con.register("_incoming", df)
            try:
                self._con.execute(f'CREATE OR REPLACE TABLE "{table}" AS SELECT * FROM _incoming')
            finally:
                self._con.unregister("_incoming")
            self._loaded[table] = datetime.now(UTC)

    def upsert(self, table: str, df: pd.DataFrame, scope_col: str) -> None:
        with self._lock:
            self._con.register("_incoming", df)
            try:
                if self._exists(table):
                    self._con.execute(
                        f'DELETE FROM "{table}" WHERE "{scope_col}" IN '
                        f'(SELECT DISTINCT "{scope_col}" FROM _incoming)'
                    )
                    self._con.execute(f'INSERT INTO "{table}" BY NAME SELECT * FROM _incoming')
                else:
                    self._con.execute(f'CREATE TABLE "{table}" AS SELECT * FROM _incoming')
            finally:
                self._con.unregister("_incoming")
            self._loaded[table] = datetime.now(UTC)

    def query(self, sql: str) -> str:
        with self._lock:
            timer = threading.Timer(self._timeout_s, self._con.interrupt)
            timer.start()
            try:
                cursor = self._con.execute(sql)
                if cursor.description is None:
                    return "OK"
                columns = [d[0] for d in cursor.description]
                rows = cursor.fetchmany(MAX_ROWS)
                extra = 0
                while chunk := cursor.fetchmany(10_000):
                    extra += len(chunk)
            except duckdb.InterruptException as exc:
                raise QueryTimeout(
                    f"query cancelled after {self._timeout_s:g}s — simplify or add filters"
                ) from exc
            except duckdb.Error as exc:
                raise QueryError(str(exc)) from exc
            finally:
                timer.cancel()
        out = _markdown(columns, rows)
        if not rows:
            return out + "\n(0 rows)"
        if extra:
            out += f"\n… {extra:,} more rows — add LIMIT or aggregate"
        return out

    def tables(self) -> list[TableInfo]:
        with self._lock:
            names = [
                r[0]
                for r in self._con.execute(
                    "SELECT table_name FROM duckdb_tables() WHERE NOT internal ORDER BY 1"
                ).fetchall()
            ]
            views = [
                r[0]
                for r in self._con.execute(
                    "SELECT view_name FROM duckdb_views() WHERE NOT internal ORDER BY 1"
                ).fetchall()
            ]
            infos = []
            for name in names:
                count = self._con.execute(f'SELECT count(*) FROM "{name}"').fetchone()
                rows = int(count[0]) if count else 0
                infos.append(TableInfo(name, rows, self._loaded.get(name), "table"))
        return infos + [TableInfo(v, None, None, "view") for v in views]

    def loaded_at(self, table: str) -> datetime | None:
        with self._lock:
            return self._loaded.get(table) if self._exists(table) else None

    def scope_count(self, table: str, scope_col: str, value: str) -> int:
        with self._lock:
            if not self._exists(table):
                return 0
            row = self._con.execute(
                f'SELECT count(*) FROM "{table}" WHERE "{scope_col}" = ?', [value]
            ).fetchone()
            return int(row[0]) if row else 0
