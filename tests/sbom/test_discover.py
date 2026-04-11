"""OWB-S107a — component discovery tests.

Discovery walks a workspace and emits one Component per:
- .claude/skills/**/SKILL.md
- .claude/agents/**/*.md
- .claude/commands/**/*.md
- .mcp.json server declarations
- Workspace-level skills/ and agents/ folders (outside .claude/)

Discovery is additive: it reads files but does not modify the scanner walk.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from open_workspace_builder.sbom.discover import (
    Component,
    ComponentKind,
    discover_components,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_fixture_workspace(tmp_path: Path) -> Path:
    """Build a representative workspace with one of each artifact kind."""
    ws = tmp_path / "workspace"

    # Claude Code skill
    skill_dir = ws / ".claude" / "skills" / "xlsx"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: xlsx\nversion: 1.2.0\n---\n# XLSX skill\n",
        encoding="utf-8",
    )

    # Claude Code agent
    agents_dir = ws / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "planner.md").write_text(
        "---\nname: planner\n---\n# Planner agent\n",
        encoding="utf-8",
    )

    # Claude Code slash command
    commands_dir = ws / ".claude" / "commands"
    commands_dir.mkdir(parents=True)
    (commands_dir / "commit.md").write_text(
        "---\nname: commit\n---\n# Commit command\n",
        encoding="utf-8",
    )

    # MCP server declaration
    mcp_config = {
        "mcpServers": {
            "github": {
                "command": "npx",
                "args": ["@modelcontextprotocol/server-github"],
            },
            "filesystem": {
                "command": "npx",
                "args": ["@modelcontextprotocol/server-filesystem", "/tmp"],
            },
        }
    }
    (ws / ".mcp.json").write_text(json.dumps(mcp_config), encoding="utf-8")

    return ws


# ---------------------------------------------------------------------------
# Discovery coverage
# ---------------------------------------------------------------------------


class TestDiscoverAllKinds:
    def test_finds_skill(self, tmp_path: Path) -> None:
        ws = _make_fixture_workspace(tmp_path)
        components = discover_components(ws)
        skills = [c for c in components if c.kind == ComponentKind.SKILL]
        assert len(skills) == 1
        assert skills[0].name == "xlsx"

    def test_finds_agent(self, tmp_path: Path) -> None:
        ws = _make_fixture_workspace(tmp_path)
        components = discover_components(ws)
        agents = [c for c in components if c.kind == ComponentKind.AGENT]
        assert len(agents) == 1
        assert agents[0].name == "planner"

    def test_finds_command(self, tmp_path: Path) -> None:
        ws = _make_fixture_workspace(tmp_path)
        components = discover_components(ws)
        commands = [c for c in components if c.kind == ComponentKind.COMMAND]
        assert len(commands) == 1
        assert commands[0].name == "commit"

    def test_finds_mcp_servers(self, tmp_path: Path) -> None:
        ws = _make_fixture_workspace(tmp_path)
        components = discover_components(ws)
        servers = [c for c in components if c.kind == ComponentKind.MCP_SERVER]
        assert {s.name for s in servers} == {"github", "filesystem"}

    def test_total_component_count(self, tmp_path: Path) -> None:
        ws = _make_fixture_workspace(tmp_path)
        components = discover_components(ws)
        # 1 skill + 1 agent + 1 command + 2 MCP servers
        assert len(components) == 5


class TestComponentFields:
    def test_skill_has_bom_ref(self, tmp_path: Path) -> None:
        ws = _make_fixture_workspace(tmp_path)
        components = discover_components(ws)
        skill = next(c for c in components if c.kind == ComponentKind.SKILL)
        assert skill.bom_ref.startswith("owb:skill/xlsx@")

    def test_skill_has_normalized_hash(self, tmp_path: Path) -> None:
        ws = _make_fixture_workspace(tmp_path)
        components = discover_components(ws)
        skill = next(c for c in components if c.kind == ComponentKind.SKILL)
        assert skill.content_hash.startswith("sha256-norm1:")

    def test_skill_version_from_frontmatter(self, tmp_path: Path) -> None:
        ws = _make_fixture_workspace(tmp_path)
        components = discover_components(ws)
        skill = next(c for c in components if c.kind == ComponentKind.SKILL)
        assert skill.version == "1.2.0"

    def test_agent_version_defaults_to_hash_prefix(self, tmp_path: Path) -> None:
        """Agents without a frontmatter version fall back to the first 12 chars of the hash hex."""
        ws = _make_fixture_workspace(tmp_path)
        components = discover_components(ws)
        agent = next(c for c in components if c.kind == ComponentKind.AGENT)
        # Fallback version is the first 12 hex chars, not the full hash prefix.
        assert len(agent.version) == 12
        assert all(c in "0123456789abcdef" for c in agent.version)

    def test_evidence_records_relative_path(self, tmp_path: Path) -> None:
        ws = _make_fixture_workspace(tmp_path)
        components = discover_components(ws)
        skill = next(c for c in components if c.kind == ComponentKind.SKILL)
        assert ".claude/skills/xlsx/SKILL.md" in skill.evidence_path

    def test_source_field_defaults_to_local(self, tmp_path: Path) -> None:
        ws = _make_fixture_workspace(tmp_path)
        components = discover_components(ws)
        agent = next(c for c in components if c.kind == ComponentKind.AGENT)
        # No explicit `source:` in frontmatter → local fallback.
        assert agent.source == "local"

    def test_source_field_from_frontmatter(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        skill_dir = ws / ".claude" / "skills" / "cool"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: cool\nsource: https://github.com/example/cool\n---\n# body\n",
            encoding="utf-8",
        )
        components = discover_components(ws)
        skill = next(c for c in components if c.name == "cool")
        assert skill.source == "https://github.com/example/cool"


class TestHashStability:
    """Component hashes must be stable across whitespace and `updated:` changes."""

    def test_hash_stable_across_whitespace_change(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        skill_dir = ws / ".claude" / "skills" / "x"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"

        skill_file.write_text("---\nname: x\nversion: 1.0\n---\n# body\n", encoding="utf-8")
        h1 = next(c for c in discover_components(ws) if c.name == "x").content_hash

        skill_file.write_text("---\nname: x   \nversion: 1.0\n---\n# body  \n", encoding="utf-8")
        h2 = next(c for c in discover_components(ws) if c.name == "x").content_hash

        assert h1 == h2

    def test_hash_stable_across_updated_field_change(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        skill_dir = ws / ".claude" / "skills" / "x"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"

        skill_file.write_text(
            "---\nname: x\nupdated: 2026-04-10\nversion: 1.0\n---\n# body\n",
            encoding="utf-8",
        )
        h1 = next(c for c in discover_components(ws) if c.name == "x").content_hash

        skill_file.write_text(
            "---\nname: x\nupdated: 2099-12-31\nversion: 1.0\n---\n# body\n",
            encoding="utf-8",
        )
        h2 = next(c for c in discover_components(ws) if c.name == "x").content_hash

        assert h1 == h2

    def test_hash_changes_when_body_changes(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        skill_dir = ws / ".claude" / "skills" / "x"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"

        skill_file.write_text("---\nname: x\n---\n# body v1\n", encoding="utf-8")
        h1 = next(c for c in discover_components(ws) if c.name == "x").content_hash

        skill_file.write_text("---\nname: x\n---\n# body v2\n", encoding="utf-8")
        h2 = next(c for c in discover_components(ws) if c.name == "x").content_hash

        assert h1 != h2


class TestEmptyAndMissing:
    def test_empty_workspace_returns_empty_list(self, tmp_path: Path) -> None:
        ws = tmp_path / "empty"
        ws.mkdir()
        assert discover_components(ws) == ()

    def test_missing_workspace_returns_empty_list(self, tmp_path: Path) -> None:
        assert discover_components(tmp_path / "does-not-exist") == ()

    def test_missing_mcp_json_is_ignored(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        (ws / ".claude" / "skills" / "x").mkdir(parents=True)
        (ws / ".claude" / "skills" / "x" / "SKILL.md").write_text(
            "---\nname: x\n---\n", encoding="utf-8"
        )
        components = discover_components(ws)
        assert all(c.kind != ComponentKind.MCP_SERVER for c in components)

    def test_malformed_mcp_json_does_not_crash(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".mcp.json").write_text("not valid json {", encoding="utf-8")
        # Discovery must tolerate a malformed file, skipping it.
        assert discover_components(ws) == ()


class TestComponentImmutability:
    def test_component_is_frozen(self) -> None:
        c = Component(
            kind=ComponentKind.SKILL,
            name="x",
            version="1.0",
            bom_ref="owb:skill/x@1.0",
            content_hash="sha256-norm1:abc",
            evidence_path=".claude/skills/x/SKILL.md",
            source="local",
        )
        with pytest.raises((AttributeError, Exception)):
            c.name = "changed"  # type: ignore[misc]


class TestDeterministicOrdering:
    def test_components_sorted_for_stable_output(self, tmp_path: Path) -> None:
        ws = _make_fixture_workspace(tmp_path)
        run1 = discover_components(ws)
        run2 = discover_components(ws)
        assert [c.bom_ref for c in run1] == [c.bom_ref for c in run2]
