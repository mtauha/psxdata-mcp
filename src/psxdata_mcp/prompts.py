"""Skill prompts: markdown files under skills/ served as MCP prompts and as plugin skills.

Each file has a small front matter block:

    ---
    name: tearsheet
    title: Stock tearsheet
    description: One line used by clients to pick the skill.
    argument: symbol | required | PSX ticker, e.g. OGDC     (repeatable, optional)
    task: Build a tearsheet for {symbol}.                    (optional)
    includes: screen                                         (optional, comma-separated)
    ---

The playbook (PLAYBOOK) is the shared rulebook: every other skill gets it appended when served
as an MCP prompt, and shipped as playbook.md beside SKILL.md in the Claude Code plugin.
Included skills are handled the same way (appended, or shipped as <name>.md).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.prompts.base import Prompt, PromptArgument

PLAYBOOK = "psx-playbook"


@dataclass(frozen=True)
class Argument:
    name: str
    required: bool
    description: str


@dataclass(frozen=True)
class Skill:
    name: str
    title: str
    description: str
    body: str
    arguments: tuple[Argument, ...] = ()
    task: str = ""
    includes: tuple[str, ...] = ()


def parse(text: str) -> Skill:
    head, sep, body = text.removeprefix("---\n").partition("\n---\n")
    if not sep:
        raise ValueError("skill file needs a --- front matter block")
    fields: dict[str, str] = {}
    args: list[Argument] = []
    for line in head.splitlines():
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key == "argument":
            name, need, desc = (p.strip() for p in value.split("|", 2))
            if need not in ("required", "optional"):
                raise ValueError(f"argument {name}: expected required|optional, got {need!r}")
            args.append(Argument(name, need == "required", desc))
        elif key:
            fields[key] = value
    return Skill(
        name=fields["name"],
        title=fields["title"],
        description=fields["description"],
        body=body.strip() + "\n",
        arguments=tuple(args),
        task=fields.get("task", ""),
        includes=tuple(n.strip() for n in fields.get("includes", "").split(",") if n.strip()),
    )


def load_skills() -> dict[str, Skill]:
    root = files("psxdata_mcp") / "skills"
    skills = [
        parse(f.read_text(encoding="utf-8")) for f in root.iterdir() if f.name.endswith(".md")
    ]
    return {s.name: s for s in sorted(skills, key=lambda s: (s.name != PLAYBOOK, s.name))}


def render_prompt(skill: Skill, skills: dict[str, Skill], values: dict[str, str]) -> str:
    """Text of the MCP prompt: task line, skill body, included skills, then the playbook."""
    parts = []
    if skill.task:
        parts.append(skill.task.format(**values))
    parts.append(skill.body)
    parts += [f"---\n\n{skills[name].body}" for name in skill.includes]
    if skill.name != PLAYBOOK:
        parts.append(f"---\n\n{skills[PLAYBOOK].body}")
    return "\n\n".join(p.strip() for p in parts) + "\n"


def render_skill_md(skill: Skill) -> str:
    """SKILL.md for the Claude Code plugin; the playbook ships beside it as playbook.md."""
    sections = [f"---\nname: {skill.name}\ndescription: {skill.description}\n---"]
    if skill.name != PLAYBOOK:
        refs = ", ".join(f"`{name}.md`" for name in skill.includes)
        also = f" and {refs}" if refs else ""
        sections.append(f"Read `playbook.md`{also} in this folder before you start.")
    if skill.arguments:
        inputs = "\n".join(
            f"- `{a.name}` ({'required' if a.required else 'optional'}): {a.description}"
            for a in skill.arguments
        )
        sections.append(f"Inputs (ask the user for any required one that is missing):\n{inputs}")
    sections.append(skill.body)
    return "\n\n".join(sections)


def _renderer(skill: Skill, skills: dict[str, Skill]) -> Callable[..., str]:
    known = {a.name for a in skill.arguments}

    def render(**values: Any) -> str:
        clean = {k: str(values.get(k) or "").strip() or "(not given)" for k in known}
        if "symbol" in clean:
            clean["symbol"] = clean["symbol"].upper()
        return render_prompt(skill, skills, clean)

    return render


def register_prompts(server: MCPServer, skills: dict[str, Skill] | None = None) -> None:
    skills = skills or load_skills()
    for skill in skills.values():
        unknown = [n for n in skill.includes if n not in skills]
        if unknown:
            raise ValueError(f"{skill.name} includes unknown skills: {unknown}")
        server.add_prompt(
            Prompt(
                name=skill.name,
                title=skill.title,
                description=skill.description,
                arguments=[
                    PromptArgument(name=a.name, description=a.description, required=a.required)
                    for a in skill.arguments
                ],
                fn=_renderer(skill, skills),
                context_kwarg=None,
            )
        )
