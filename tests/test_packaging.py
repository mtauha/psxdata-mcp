import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _version() -> str:
    return str(tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"])


def test_plugin_image_tag_matches_version() -> None:
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    server = plugin["mcpServers"]["psxdata"]
    assert server["command"] == "docker"
    assert server["args"][:3] == ["run", "-i", "--rm"]
    assert "psxdata-cache:/home/app/.psxdata" in server["args"]
    assert server["args"][-1] == f"mtauha/psxdata-mcp:{_version()}"
    assert plugin["version"] == _version()


def test_marketplace_points_at_repo_root() -> None:
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    assert market["name"] == "psxdata-mcp"
    [entry] = market["plugins"]
    assert entry["name"] == "psxdata"
    assert entry["source"] == "./"
