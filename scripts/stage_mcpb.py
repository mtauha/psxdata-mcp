"""Assemble the directory that `mcpb pack` turns into the Claude Desktop bundle.

Usage: python scripts/stage_mcpb.py <dest>
"""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ["pyproject.toml", "uv.lock", "README.md", "LICENSE"]


def stage(dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for name in FILES:
        shutil.copy2(ROOT / name, dest / name)
    shutil.copy2(ROOT / "mcpb" / "manifest.json", dest / "manifest.json")
    shutil.copytree(
        ROOT / "src", dest / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    stage(Path(sys.argv[1]))


if __name__ == "__main__":
    main()
