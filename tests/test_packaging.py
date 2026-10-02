import json
import subprocess
import sys
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


def test_mcpb_manifest_matches_package() -> None:
    manifest = json.loads((ROOT / "mcpb" / "manifest.json").read_text())
    server = manifest["server"]
    assert manifest["version"] == _version()
    assert server["type"] == "uv"
    assert (ROOT / server["entry_point"]).is_file()
    assert server["mcp_config"]["command"] == "uv"
    assert server["mcp_config"]["args"][-1] == "psxdata-mcp"
    scripts = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["scripts"]
    assert "psxdata-mcp" in scripts


def test_stage_mcpb_collects_bundle_files(tmp_path: Path) -> None:
    dest = tmp_path / "bundle"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "stage_mcpb.py"), str(dest)], check=True)
    for name in ("manifest.json", "pyproject.toml", "uv.lock", "README.md", "LICENSE"):
        assert (dest / name).is_file(), name
    assert (dest / "src" / "psxdata_mcp" / "server.py").is_file()
    assert not list(dest.rglob("__pycache__"))
    assert not (dest / "tests").exists()
    assert not (dest / ".venv").exists()


def test_marketplace_points_at_repo_root() -> None:
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    assert market["name"] == "psxdata-mcp"
    [entry] = market["plugins"]
    assert entry["name"] == "psxdata"
    assert entry["source"] == "./"
