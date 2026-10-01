import pytest
from mcp import Client

from psxdata_mcp.server import build_server
from psxdata_mcp.store import Store

pytestmark = [pytest.mark.live, pytest.mark.anyio]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def test_live_prices_and_screener() -> None:
    async with Client(build_server(Store())) as c:
        r = await c.call_tool("load_prices", {"symbols": ["OGDC"], "start": "2025-01-01"})
        assert not r.is_error, r.content[0].text
        r = await c.call_tool("load_screener", {})
        assert not r.is_error, r.content[0].text
        r = await c.call_tool(
            "query", {"sql": "SELECT count(*) FROM prices p JOIN screener s USING (symbol)"}
        )
        assert not r.is_error
