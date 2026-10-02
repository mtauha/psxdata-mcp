import os
import zipfile
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

pytestmark = pytest.mark.bundle

BUNDLE = os.environ.get("PSXDATA_MCP_BUNDLE")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.skipif(not BUNDLE, reason="set PSXDATA_MCP_BUNDLE to a packed .mcpb")
@pytest.mark.anyio
async def test_bundle_speaks_mcp_over_stdio(tmp_path: Path) -> None:
    assert BUNDLE
    with zipfile.ZipFile(BUNDLE) as z:
        z.extractall(tmp_path)
    params = StdioServerParameters(
        command="uv",
        args=["run", "--directory", str(tmp_path), "--locked", "--no-dev", "psxdata-mcp"],
    )
    async with Client(params) as c:
        tools = await c.list_tools()
        r = await c.call_tool("query", {"sql": "SELECT 42 AS answer"})
    assert len(tools.tools) == 11
    assert "| 42 |" in r.content[0].text
