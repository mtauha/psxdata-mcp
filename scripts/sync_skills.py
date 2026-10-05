"""Regenerate the Claude Code plugin skills from src/psxdata_mcp/skills/*.md.

Both plugins ship the same skills: the Docker plugin from skills/ and the hosted plugin from
plugins/psxdata-hosted/skills/.

Usage: python scripts/sync_skills.py [dest]   (dest defaults to both plugin skill directories)
"""

import shutil
import sys
from pathlib import Path

from psxdata_mcp.prompts import PLAYBOOK, load_skills, render_skill_md

ROOT = Path(__file__).resolve().parents[1]
DESTS = (ROOT / "skills", ROOT / "plugins" / "psxdata-hosted" / "skills")


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
        for name in skill.includes:
            (folder / f"{name}.md").write_text(skills[name].body, encoding="utf-8")


def main() -> None:
    if len(sys.argv) > 2:
        sys.exit(__doc__)
    for dest in [Path(sys.argv[1])] if len(sys.argv) == 2 else DESTS:
        build(dest)


if __name__ == "__main__":
    main()
