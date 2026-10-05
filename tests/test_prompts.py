from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from mcp import Client

from psxdata_mcp.prompts import PLAYBOOK, load_skills, parse, render_skill_md
from psxdata_mcp.server import build_server
from psxdata_mcp.store import Store

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> AsyncIterator[Client]:
    async with Client(build_server(Store())) as c:
        yield c


def test_parse_front_matter() -> None:
    skill = parse(
        "---\nname: x\ntitle: X\ndescription: Does x: well.\n"
        "argument: symbol | required | Ticker | e.g. OGDC\ntask: Do {symbol}.\n---\nBody\n"
    )
    assert skill.description == "Does x: well."
    [arg] = skill.arguments
    assert (arg.name, arg.required, arg.description) == ("symbol", True, "Ticker | e.g. OGDC")
    assert skill.task == "Do {symbol}."
    assert skill.body == "Body\n"


def test_parse_rejects_bad_argument_flag() -> None:
    with pytest.raises(ValueError, match="required|optional"):
        parse("---\nname: x\ntitle: X\ndescription: d\nargument: s | maybe | d\n---\nB\n")


def test_skill_files_are_well_formed() -> None:
    skills = load_skills()
    assert PLAYBOOK in skills
    assert next(iter(skills)) == PLAYBOOK
    for skill in skills.values():
        assert skill.title and skill.body.strip()
        assert 20 < len(skill.description) <= 1024
        names = {a.name for a in skill.arguments}
        placeholders = {p.split("}")[0] for p in skill.task.split("{")[1:]}
        assert placeholders <= names, skill.name
        assert set(skill.includes) <= set(skills) - {PLAYBOOK, skill.name}, skill.name


def test_plugin_skills_match_sources() -> None:
    """skills/ is generated; run `uv run python scripts/sync_skills.py` after editing sources."""
    skills = load_skills()
    on_disk = {p.name for p in (ROOT / "skills").iterdir() if p.is_dir()}
    assert on_disk == set(skills)
    playbook = skills[PLAYBOOK].body
    for skill in skills.values():
        folder = ROOT / "skills" / skill.name
        assert (folder / "SKILL.md").read_text(encoding="utf-8") == render_skill_md(skill)
        expected = {"SKILL.md"} | {f"{n}.md" for n in skill.includes}
        if skill.name != PLAYBOOK:
            expected.add("playbook.md")
            assert (folder / "playbook.md").read_text(encoding="utf-8") == playbook
        assert {p.name for p in folder.iterdir()} == expected
        for name in skill.includes:
            assert (folder / f"{name}.md").read_text(encoding="utf-8") == skills[name].body


@pytest.mark.anyio
async def test_prompts_listed_with_arguments(client: Client) -> None:
    prompts = {p.name: p for p in (await client.list_prompts()).prompts}
    assert set(prompts) == set(load_skills())
    [arg] = prompts["tearsheet"].arguments or []
    assert arg.name == "symbol" and arg.required
    assert not prompts[PLAYBOOK].arguments


@pytest.mark.anyio
async def test_workflow_prompt_fills_task_and_appends_playbook(client: Client) -> None:
    r = await client.get_prompt("tearsheet", {"symbol": " ogdc "})
    [msg] = r.messages
    text = msg.content.text
    assert msg.role == "user"
    assert text.startswith("Build a tearsheet for OGDC.")
    assert "# Stock tearsheet" in text
    assert "# PSX analysis playbook" in text


@pytest.mark.anyio
async def test_playbook_prompt_is_just_the_playbook(client: Client) -> None:
    r = await client.get_prompt(PLAYBOOK)
    text = r.messages[0].content.text
    assert text.startswith("# PSX analysis playbook")
    assert text.count("# PSX analysis playbook") == 1


@pytest.mark.anyio
async def test_missing_required_argument_is_an_error(client: Client) -> None:
    # The SDK reports render errors to clients as a generic internal error.
    with pytest.raises(Exception):  # noqa: B017
        await client.get_prompt("tearsheet", {})


@pytest.mark.anyio
async def test_optional_argument_can_be_omitted(client: Client) -> None:
    r = await client.get_prompt("screen")
    assert r.messages[0].content.text.startswith("Run a PSX stock screen. Criteria: (not given)")
    r = await client.get_prompt("screen", {"criteria": "banks with P/E under 6"})
    text = r.messages[0].content.text
    assert text.startswith("Run a PSX stock screen. Criteria: banks with P/E under 6")


@pytest.mark.anyio
async def test_included_skill_is_appended_before_playbook(client: Client) -> None:
    r = await client.get_prompt("shariah-screen", {"screen": "dividend"})
    text = r.messages[0].content.text
    assert text.startswith("Run a Shariah-compliant PSX screen. Screen: dividend")
    order = [text.index(h) for h in ("# Shariah-compliant", "# Stock screen", "# PSX analysis")]
    assert order == sorted(order)


@pytest.mark.anyio
async def test_two_argument_prompt(client: Client) -> None:
    prompts = {p.name: p for p in (await client.list_prompts()).prompts}
    args = {a.name: a.required for a in prompts["compare"].arguments or []}
    assert args == {"symbols": True, "period": False}
    r = await client.get_prompt("compare", {"symbols": "OGDC, PPL"})
    text = r.messages[0].content.text
    assert text.startswith("Compare these PSX stocks: OGDC, PPL. Period: (not given)")
