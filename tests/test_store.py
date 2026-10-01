import datetime as dt

import pandas as pd
import pytest

from psxdata_mcp.store import MAX_ROWS, QueryError, QueryTimeout, Store


def _df(symbol: str, n: int = 3) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": [symbol] * n,
            "date": [dt.date(2024, 1, i + 1) for i in range(n)],
            "close": [float(i) for i in range(n)],
        }
    )


def test_replace_creates_and_overwrites() -> None:
    s = Store()
    s.replace("t", _df("A"))
    s.replace("t", _df("B", 2))
    assert "| 2 |" in s.query("SELECT count(*) AS n FROM t")


def test_upsert_replaces_only_scope_rows() -> None:
    s = Store()
    s.upsert("prices", _df("A"), "symbol")
    s.upsert("prices", _df("B"), "symbol")
    s.upsert("prices", _df("A", 1), "symbol")
    out = s.query("SELECT symbol, count(*) AS n FROM prices GROUP BY 1 ORDER BY 1")
    assert "| A | 1 |" in out
    assert "| B | 3 |" in out


def test_upsert_recreates_table_dropped_by_agent() -> None:
    s = Store()
    s.upsert("prices", _df("A"), "symbol")
    s.query("DROP TABLE prices")
    s.upsert("prices", _df("B"), "symbol")
    assert "| 3 |" in s.query("SELECT count(*) FROM prices")


def test_upsert_inserts_by_name_with_missing_columns_null() -> None:
    s = Store()
    s.upsert("t", pd.DataFrame({"k": ["a"], "x": [1.0], "y": [2.0]}), "k")
    s.upsert("t", pd.DataFrame({"k": ["b"], "x": [3.0]}), "k")
    assert "| b | 3.0 | NULL |" in s.query("SELECT k, x, y FROM t WHERE k = 'b'")


def test_dates_are_date_type() -> None:
    s = Store()
    s.replace("t", _df("A"))
    assert "DATE" in s.query("DESCRIBE t")


def test_query_formats_markdown_table() -> None:
    s = Store()
    out = s.query("SELECT 1 AS a, 'x' AS b")
    assert out.splitlines()[:3] == ["| a | b |", "|---|---|", "| 1 | x |"]


def test_query_zero_rows() -> None:
    s = Store()
    s.replace("t", _df("A"))
    out = s.query("SELECT * FROM t WHERE false")
    assert out.endswith("(0 rows)")
    assert out.startswith("| symbol | date | close |")


def test_query_truncates_rows() -> None:
    s = Store()
    out = s.query("SELECT * FROM range(250)")
    assert len([ln for ln in out.splitlines() if ln.startswith("| ")]) == MAX_ROWS + 1
    assert "… 50 more rows — add LIMIT or aggregate" in out


def test_query_truncates_long_cells_and_escapes_pipes() -> None:
    s = Store()
    out = s.query("SELECT repeat('x', 300) AS a, 'p|q' AS b")
    row = out.splitlines()[2]
    assert "x" * 99 + "…" in row
    assert "x" * 100 not in row
    assert "p\\|q" in row


def test_query_error_is_query_error() -> None:
    with pytest.raises(QueryError, match="nope"):
        Store().query("SELECT * FROM nope")


def test_ddl_allowed() -> None:
    s = Store()
    s.query("CREATE VIEW v AS SELECT 42 AS x")
    assert "| 42 |" in s.query("SELECT x FROM v")


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM read_csv('/etc/passwd')",
        "SELECT * FROM read_csv('https://example.com/x.csv')",
        "ATTACH 'x.db'",
        "COPY (SELECT 1) TO 'out.csv'",
        "INSTALL httpfs",
        "SET enable_external_access = true",
    ],
)
def test_sandbox_blocks(sql: str) -> None:
    with pytest.raises(QueryError):
        Store().query(sql)


def test_timeout_then_connection_still_usable() -> None:
    s = Store(timeout_s=0.5)
    with pytest.raises(QueryTimeout, match="cancelled after 0.5s"):
        s.query("SELECT count(*) FROM range(1000000000) a, range(1000) b")
    assert "| 1 |" in s.query("SELECT 1")


def test_tables_lists_tables_and_views_without_schema() -> None:
    s = Store()
    assert s.tables() == []
    s.replace("prices", _df("A"))
    s.query("CREATE VIEW v AS SELECT 1 AS x")
    s.query("CREATE TABLE mine AS SELECT 1 AS x")
    infos = s.tables()
    assert [(t.name, t.kind) for t in infos] == [
        ("mine", "table"),
        ("prices", "table"),
        ("v", "view"),
    ]
    prices = infos[1]
    assert prices.rows == 3
    assert prices.loaded_at is not None and prices.loaded_at.tzinfo is not None
    assert infos[0].loaded_at is None
    assert infos[2].rows is None


def test_loaded_at_and_scope_count() -> None:
    s = Store()
    assert s.loaded_at("prices") is None
    assert s.scope_count("prices", "symbol", "A") == 0
    s.upsert("prices", _df("A"), "symbol")
    assert s.loaded_at("prices") is not None
    assert s.scope_count("prices", "symbol", "A") == 3
    assert s.scope_count("prices", "symbol", "B") == 0
    s.query("DROP TABLE prices")
    assert s.loaded_at("prices") is None
    assert s.scope_count("prices", "symbol", "A") == 0
