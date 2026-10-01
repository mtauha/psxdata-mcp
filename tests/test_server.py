from collections.abc import AsyncIterator

import pandas as pd
import psxdata
import pytest
from mcp import Client
from psxdata.exceptions import PSXConnectionError

from psxdata_mcp import loaders
from psxdata_mcp.server import build_server
from psxdata_mcp.store import Store

pytestmark = pytest.mark.anyio

TOOLS = {
    "load_prices",
    "load_screener",
    "load_index",
    "load_sectors",
    "load_fundamentals",
    "load_symbols",
    "load_debt_market",
    "load_eligible_scrips",
    "query",
    "list_tables",
    "quote",
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client(fake_psx: dict[str, list[str]]) -> AsyncIterator[Client]:
    async with Client(build_server(Store())) as c:
        yield c


async def call(c: Client, name: str, /, **args: object) -> tuple[bool, str]:
    r = await c.call_tool(name, args)
    return bool(r.is_error), r.content[0].text


async def test_exactly_eleven_tools(client: Client) -> None:
    tools = await client.list_tools()
    assert {t.name for t in tools.tools} == TOOLS


async def test_instructions_mention_workflow(client: Client) -> None:
    assert client.instructions is not None
    assert "DESCRIBE" in client.instructions
    assert "NOT adjusted" in client.instructions


async def test_load_prices_summary_and_query(client: Client) -> None:
    err, text = await call(client, "load_prices", symbols=["ogdc", "PPL", "OGDC"])
    assert not err
    assert text == "prices: loaded 2 symbol(s), 6 rows, 2024-01-01 → 2024-01-03."
    _, out = await call(client, "query", sql="SELECT count(*) AS n FROM prices")
    assert "| 6 |" in out


async def test_load_prices_date_args(client: Client) -> None:
    err, _ = await call(
        client, "load_prices", symbols=["OGDC"], start="2024-01-01", end="2024-02-01"
    )
    assert not err


async def test_load_prices_reload_replaces(client: Client) -> None:
    await call(client, "load_prices", symbols=["OGDC"])
    await call(client, "load_prices", symbols=["OGDC"])
    _, out = await call(client, "query", sql="SELECT count(*) FROM prices")
    assert "| 3 |" in out


async def test_load_prices_partial_failure(client: Client) -> None:
    err, text = await call(client, "load_prices", symbols=["OGDC", "NOPE", "EMPTY"])
    assert not err
    assert "1 symbol(s), 3 rows" in text
    assert "NOPE (unknown symbol)" in text
    assert "EMPTY (no data in range)" in text


async def test_load_prices_all_failed_is_error(client: Client) -> None:
    err, text = await call(client, "load_prices", symbols=["NOPE"])
    assert err
    assert "nothing loaded" in text


async def test_load_prices_psx_down(client: Client) -> None:
    err, text = await call(client, "load_prices", symbols=["DOWN", "LATER"])
    assert err
    assert "DOWN (PSX unreachable)" in text
    assert "LATER (skipped — PSX unreachable)" in text


async def test_load_prices_skips_validation_when_symbol_list_empty(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(psxdata, "symbols", lambda cache=True: pd.DataFrame())
    err, text = await call(client, "load_prices", symbols=["LATER"])
    assert not err
    assert "1 symbol(s)" in text


async def test_load_prices_limits(client: Client) -> None:
    err, text = await call(client, "load_prices", symbols=[f"S{i}" for i in range(51)])
    assert err and "At most 50" in text
    err, text = await call(client, "load_prices", symbols=[])
    assert err and "at least one symbol" in text
    err, text = await call(
        client, "load_prices", symbols=["OGDC"], start="2024-02-01", end="2024-01-01"
    )
    assert err and "after" in text


async def test_load_index_unknown(client: Client) -> None:
    err, text = await call(client, "load_index", name="KSE999")
    assert err
    assert "KSE100" in text and "KMI30" in text


async def test_index_columns_are_double_across_shapes(client: Client) -> None:
    err, text = await call(client, "load_index", name="kse100")
    assert not err and text == "index_constituents: loaded 2 constituents of KSE100."
    await call(client, "load_index", name="KMI30")
    _, desc = await call(client, "query", sql="DESCRIBE index_constituents")
    shares_line = next(ln for ln in desc.splitlines() if ln.startswith("| shares_m "))
    assert "DOUBLE" in shares_line
    _, out = await call(
        client, "query", sql="SELECT sum(shares_m) FROM index_constituents WHERE index_name='KMI30'"
    )
    assert "19.75" in out


@pytest.mark.parametrize(
    ("tool", "expected"),
    [
        ("load_screener", "screener: loaded 2 rows."),
        ("load_sectors", "sectors: loaded 1 rows."),
        ("load_symbols", "symbols: loaded 5 rows."),
        ("load_debt_market", "debt_market: loaded 4 rows across 4 categories."),
        ("load_eligible_scrips", "eligible_scrips: loaded 9 rows across 9 categories."),
        ("load_fundamentals", "fundamentals: loaded 2 rows."),
    ],
)
async def test_snapshot_tools(client: Client, tool: str, expected: str) -> None:
    err, text = await call(client, tool)
    assert not err
    assert text == expected


async def test_load_fundamentals_for_symbols(client: Client) -> None:
    err, text = await call(client, "load_fundamentals", symbols=["OGDC"])
    assert not err and text == "fundamentals: loaded 1 rows for OGDC."


async def test_snapshot_psx_down(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    def down(cache: bool = True) -> pd.DataFrame:
        raise PSXConnectionError("refused")

    monkeypatch.setattr(psxdata, "screener", down)
    err, text = await call(client, "load_screener")
    assert err and "PSX unreachable after retries" in text


async def test_snapshot_empty_is_not_error(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(psxdata, "sectors", lambda cache=True: pd.DataFrame())
    err, text = await call(client, "load_sectors")
    assert not err and text == "sectors: loaded 0 rows (PSX returned no data)."
    _, tables = await call(client, "list_tables")
    assert "sectors" not in tables


async def test_empty_refresh_keeps_previous_snapshot(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    await call(client, "load_screener")
    monkeypatch.setattr(psxdata, "screener", lambda cache=True: pd.DataFrame())
    err, text = await call(client, "load_screener")
    assert not err
    assert text.startswith("screener: PSX returned no data — kept the previous load from ")
    _, out = await call(client, "query", sql="SELECT count(*) FROM screener")
    assert "| 2 |" in out


async def test_empty_refresh_keeps_previous_index_rows(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    await call(client, "load_index", name="KSE100")
    monkeypatch.setattr(psxdata, "indices", lambda name, cache=True: pd.DataFrame())
    err, text = await call(client, "load_index", name="KSE100")
    assert not err
    assert text == (
        "index_constituents: PSX returned no data for KSE100 — kept the 2 previously loaded rows."
    )
    _, out = await call(client, "query", sql="SELECT count(*) FROM index_constituents")
    assert "| 2 |" in out


async def test_empty_fundamentals_for_symbol(client: Client) -> None:
    err, text = await call(client, "load_fundamentals", symbols=["PPL", "LATER"])
    assert not err and "1 rows for PPL, LATER" in text
    err, text = await call(client, "load_fundamentals", symbols=["LATER"])
    assert not err
    assert text == "fundamentals: PSX lists no filings for LATER."


async def test_empty_fundamentals_reports_kept_rows(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    err, text = await call(client, "load_fundamentals", symbols=["OGDC"])
    assert not err and "1 rows for OGDC" in text
    monkeypatch.setattr(psxdata, "fundamentals", lambda symbol=None, cache=True: pd.DataFrame())
    err, text = await call(client, "load_fundamentals", symbols=["OGDC"])
    assert not err
    assert text == (
        "fundamentals: PSX lists no filings for OGDC — kept the 1 previously loaded rows."
    )


async def test_load_surfaces_agent_object_collision(client: Client) -> None:
    err, _ = await call(client, "query", sql="CREATE VIEW prices AS SELECT 1 AS x")
    assert not err
    err, text = await call(client, "load_prices", symbols=["OGDC"])
    assert err and "could not write table 'prices'" in text


async def test_query_errors(client: Client) -> None:
    err, text = await call(client, "query", sql="SELECT * FROM nope")
    assert err and "nope" in text
    err, _ = await call(client, "query", sql="SELECT * FROM read_csv('/etc/passwd')")
    assert err


async def test_list_tables(client: Client) -> None:
    _, text = await call(client, "list_tables")
    assert text == "No tables yet — call a load_* tool first."
    await call(client, "load_prices", symbols=["OGDC"])
    await call(client, "query", sql="CREATE VIEW v AS SELECT 1 AS x")
    _, text = await call(client, "list_tables")
    lines = text.splitlines()
    assert lines[0].startswith("prices — 3 rows, loaded ") and lines[0].endswith(" UTC")
    assert lines[1] == "v — view"
    assert "close" not in text


async def test_quote(client: Client) -> None:
    err, text = await call(client, "quote", symbol="ogdc")
    assert not err
    assert "symbol: OGDC" in text and "price: 200.0" in text
    assert "dividend_yield: 8.0" in text
    err, text = await call(client, "quote", symbol="NOPE")
    assert err and "NOPE" in text


async def test_unexpected_exception_is_generic_error(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom() -> pd.DataFrame:
        raise RuntimeError("secret internals")

    monkeypatch.setattr(loaders, "load_screener", boom)
    err, text = await call(client, "load_screener")
    assert err
    assert "load_screener" in text
    assert "secret internals" not in text


async def test_nothing_written_to_stdout(
    client: Client, capsys: pytest.CaptureFixture[str]
) -> None:
    await call(client, "load_prices", symbols=["OGDC", "NOPE"])
    await call(client, "load_screener")
    await call(client, "query", sql="SELECT * FROM prices")
    await call(client, "query", sql="SELECT * FROM nope")
    await call(client, "list_tables")
    await call(client, "quote", symbol="PPL")
    assert capsys.readouterr().out == ""
