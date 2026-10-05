"""Regenerate the Claude Code plugin skills (skills/) from src/psxdata_mcp/skills/*.md.

Usage: python scripts/sync_skills.py [dest]   (dest defaults to <repo>/skills)
"""

import shutil
import sys
from pathlib import Path

from psxdata_mcp.prompts import PLAYBOOK, load_skills, render_skill_md

ROOT = Path(__file__).resolve().parents[1]


def build(dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    skills = load_skills()
    playbook = skills[PLAYBOOK]
    for skill in skills.values():
        folder = dest / skill.name
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text(render_skill_md(skill), encoding="utf-8")
        if skill.name != PLAYBOOK:
            (folder / "playbook.md").write_text(playbook.body, encoding="utf-8")


def main() -> None:
    if len(sys.argv) > 2:
        sys.exit(__doc__)
    build(Path(sys.argv[1]) if len(sys.argv) == 2 else ROOT / "skills")


if __name__ == "__main__":
    main()
