import os
import subprocess
import uuid

import pytest
from mcp import Client, StdioServerParameters

pytestmark = pytest.mark.container

IMAGE = os.environ.get("PSXDATA_MCP_IMAGE", "psxdata-mcp:dev")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_container_speaks_mcp_over_stdio() -> None:
    params = StdioServerParameters(command="docker", args=["run", "-i", "--rm", IMAGE])
    async with Client(params) as c:
        tools = await c.list_tools()
        r = await c.call_tool("query", {"sql": "SELECT 42 AS answer"})
    assert len(tools.tools) == 11
    assert "| 42 |" in r.content[0].text


def test_container_runs_as_non_root() -> None:
    out = subprocess.run(
        ["docker", "run", "--rm", "--entrypoint", "id", IMAGE, "-u"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == "1000"


def test_container_cache_dir_writable() -> None:
    volume = f"psxdata-test-{uuid.uuid4().hex[:8]}"
    script = (
        "import pathlib; p = pathlib.Path.home() / '.psxdata' / 'cache';"
        " p.mkdir(parents=True, exist_ok=True); (p / 'probe').write_text('ok')"
    )
    try:
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{volume}:/home/app/.psxdata",
                "--entrypoint",
                "python",
                IMAGE,
                "-c",
                script,
            ],
            check=True,
        )
    finally:
        subprocess.run(["docker", "volume", "rm", "-f", volume], check=False)
