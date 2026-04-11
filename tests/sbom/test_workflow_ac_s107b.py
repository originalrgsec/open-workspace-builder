"""OWB-S107b — Workflow-level acceptance test per integration-verification-policy §1.

This test exercises the full ``owb sbom generate`` CLI pipeline end-to-end
on a fixture workspace constructed to cover the four S107b enrichment cases:

1. **Frontmatter explicit source** — a skill with ``source:`` set to a URL.
2. **Git history** — a skill committed in a git repo with an origin remote.
3. **Local fallback** — a skill in a non-git workspace section.
4. **Non-allowed license** — a skill with a sibling LICENSE detected as GPL-3.0.

Each case asserts the expected provenance type, capability properties (where
declared), and license cross-reference outcome. The CLI exit code 2 contract
for non-allowed licenses is verified end-to-end.

Per integration-verification-policy: this test must invoke the CLI as an
operator would (via Click runner), not call internal modules directly.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from open_workspace_builder.cli import owb


GPL3_TEXT = """\
                    GNU GENERAL PUBLIC LICENSE
                       Version 3, 29 June 2007

 Copyright (C) 2007 Free Software Foundation, Inc.

 The GNU General Public License is a free, copyleft license for software.
"""

MIT_TEXT = """\
MIT License

Copyright (c) 2026 Test Author

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software.
"""


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def four_case_workspace(tmp_path: Path) -> Path:
    """Build a fixture workspace exercising all four S107b enrichment cases."""
    ws = tmp_path / "ws"
    ws.mkdir()

    # Workspace-level MIT LICENSE so the parent-walk fallback yields an
    # allowed license for components without their own.
    (ws / "LICENSE").write_text(MIT_TEXT, encoding="utf-8")

    # Make this a git repo with an origin remote so case 2 (git history)
    # has a high-confidence source URL to record.
    _git(ws, "init", "-q", "-b", "main")
    _git(ws, "config", "user.email", "ac@test.example")
    _git(ws, "config", "user.name", "AC Test")
    _git(ws, "config", "commit.gpgsign", "false")
    _git(ws, "remote", "add", "origin", "https://github.com/example/four-case.git")

    # Case 1: explicit frontmatter source — should produce
    # provenance:type=frontmatter regardless of git history.
    skill1_dir = ws / ".claude" / "skills" / "explicit"
    skill1_dir.mkdir(parents=True)
    (skill1_dir / "SKILL.md").write_text(
        "---\n"
        "name: explicit\n"
        "version: 1.0.0\n"
        "source: https://upstream.example.com/explicit\n"
        "allowed-tools: Read, Write\n"
        "---\n"
        "# Explicit skill\n",
        encoding="utf-8",
    )

    # Case 2: git history with origin remote — should produce
    # provenance:type=git-history with high confidence and the origin URL.
    skill2_dir = ws / ".claude" / "skills" / "githistory"
    skill2_dir.mkdir(parents=True)
    (skill2_dir / "SKILL.md").write_text(
        "---\nname: githistory\nversion: 1.0.0\nallowed-tools: Read\n---\n# Git history skill\n",
        encoding="utf-8",
    )

    # Case 3: local fallback skill — has its own dir with no LICENSE so it
    # falls through to the workspace-root LICENSE (MIT, allowed). Without
    # `source:` and outside of git's add commit, it gets git-history. To
    # make this truly "local fallback", we leave it uncommitted.
    skill3_dir = ws / ".claude" / "skills" / "localfallback"
    skill3_dir.mkdir(parents=True)
    (skill3_dir / "SKILL.md").write_text(
        "---\nname: localfallback\nversion: 1.0.0\n---\n# Local fallback skill\n",
        encoding="utf-8",
    )

    # Case 4: non-allowed license — sibling LICENSE detected as GPL-3.0.
    skill4_dir = ws / ".claude" / "skills" / "gplskill"
    skill4_dir.mkdir(parents=True)
    (skill4_dir / "SKILL.md").write_text(
        "---\nname: gplskill\nversion: 1.0.0\n---\n# GPL-licensed skill\n",
        encoding="utf-8",
    )
    (skill4_dir / "LICENSE").write_text(GPL3_TEXT, encoding="utf-8")

    # Commit case 1, 2, and 4 (and the workspace LICENSE) so git-history
    # provenance can find them. Case 3 stays uncommitted to exercise the
    # local fallback path.
    _git(ws, "add", "LICENSE")
    _git(ws, "add", ".claude/skills/explicit/SKILL.md")
    _git(ws, "add", ".claude/skills/githistory/SKILL.md")
    _git(ws, "add", ".claude/skills/gplskill/SKILL.md")
    _git(ws, "add", ".claude/skills/gplskill/LICENSE")
    _git(ws, "commit", "-q", "-m", "add four-case fixture")

    return ws


# ---------------------------------------------------------------------------
# End-to-end CLI invocation
# ---------------------------------------------------------------------------


def _generate_and_load(workspace: Path, output_path: Path) -> tuple[int, dict]:
    """Run `owb sbom generate <workspace> -o <output>` and parse the result."""
    runner = CliRunner()
    result = runner.invoke(
        owb,
        ["sbom", "generate", str(workspace), "-o", str(output_path)],
    )
    sbom_data = json.loads(output_path.read_text(encoding="utf-8"))
    return result.exit_code, sbom_data


def _component_for(sbom: dict, name: str) -> dict:
    for c in sbom["components"]:
        if c.get("name") == name:
            return c
    raise AssertionError(f"component {name!r} not in SBOM")


def _properties(component: dict) -> dict[str, list[str]]:
    """Group component properties by name (one name can have multiple values)."""
    grouped: dict[str, list[str]] = {}
    for p in component.get("properties", []):
        grouped.setdefault(p["name"], []).append(p["value"])
    return grouped


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestS107bWorkflowAC:
    def test_exit_code_2_when_non_allowed_license_present(
        self, four_case_workspace: Path, tmp_path: Path
    ) -> None:
        # The fixture intentionally includes a GPL-3.0 skill, so the CLI
        # must exit with code 2 (warnings).
        exit_code, _ = _generate_and_load(four_case_workspace, tmp_path / "out.json")
        assert exit_code == 2

    def test_case_1_explicit_frontmatter_provenance(
        self, four_case_workspace: Path, tmp_path: Path
    ) -> None:
        _, sbom = _generate_and_load(four_case_workspace, tmp_path / "out.json")
        comp = _component_for(sbom, "explicit")
        props = _properties(comp)
        assert props["owb:provenance:type"] == ["frontmatter"]
        assert props["owb:provenance:confidence"] == ["high"]
        assert props["owb:provenance:source"] == ["https://upstream.example.com/explicit"]

    def test_case_1_capability_extraction(self, four_case_workspace: Path, tmp_path: Path) -> None:
        _, sbom = _generate_and_load(four_case_workspace, tmp_path / "out.json")
        comp = _component_for(sbom, "explicit")
        prop_names = {p["name"] for p in comp.get("properties", [])}
        assert "owb:capability:tool:Read" in prop_names
        assert "owb:capability:tool:Write" in prop_names

    def test_case_2_git_history_provenance(self, four_case_workspace: Path, tmp_path: Path) -> None:
        _, sbom = _generate_and_load(four_case_workspace, tmp_path / "out.json")
        comp = _component_for(sbom, "githistory")
        props = _properties(comp)
        assert props["owb:provenance:type"] == ["git-history"]
        assert props["owb:provenance:confidence"] == ["high"]
        assert props["owb:provenance:source"] == ["https://github.com/example/four-case.git"]
        # commit SHA recorded
        assert "owb:provenance:commit" in props
        assert len(props["owb:provenance:commit"][0]) == 40

    def test_case_3_local_fallback_provenance(
        self, four_case_workspace: Path, tmp_path: Path
    ) -> None:
        _, sbom = _generate_and_load(four_case_workspace, tmp_path / "out.json")
        comp = _component_for(sbom, "localfallback")
        props = _properties(comp)
        # Uncommitted file in a git repo: no add-commit found, falls back
        # to local with low confidence.
        assert props["owb:provenance:type"] == ["local"]
        assert props["owb:provenance:confidence"] == ["low"]

    def test_case_3_inherits_workspace_license(
        self, four_case_workspace: Path, tmp_path: Path
    ) -> None:
        _, sbom = _generate_and_load(four_case_workspace, tmp_path / "out.json")
        comp = _component_for(sbom, "localfallback")
        # Walks up to the workspace LICENSE (MIT) and records it as allowed.
        licenses = comp.get("licenses", [])
        assert len(licenses) == 1
        assert licenses[0]["license"]["id"] == "MIT"

    def test_case_4_gpl_license_marked_warning(
        self, four_case_workspace: Path, tmp_path: Path
    ) -> None:
        _, sbom = _generate_and_load(four_case_workspace, tmp_path / "out.json")
        comp = _component_for(sbom, "gplskill")
        licenses = comp.get("licenses", [])
        assert len(licenses) == 1
        assert licenses[0]["license"]["id"] == "GPL-3.0"
        prop_names = {p["name"] for p in comp.get("properties", [])}
        assert "owb:license:warning" in prop_names

    def test_top_level_non_allowed_count_aggregate(
        self, four_case_workspace: Path, tmp_path: Path
    ) -> None:
        _, sbom = _generate_and_load(four_case_workspace, tmp_path / "out.json")
        metadata = sbom.get("metadata", {})
        meta_props = {p["name"]: p["value"] for p in metadata.get("properties", [])}
        assert "owb:license:non-allowed-count" in meta_props
        # Exactly one GPL-3.0 component in the fixture.
        assert meta_props["owb:license:non-allowed-count"] == "1"

    def test_clean_workspace_exits_zero(self, tmp_path: Path) -> None:
        # Sanity check: a workspace with no GPL components and a clean MIT
        # LICENSE produces exit 0.
        ws = tmp_path / "clean-ws"
        ws.mkdir()
        (ws / "LICENSE").write_text(MIT_TEXT, encoding="utf-8")
        skill = ws / ".claude" / "skills" / "demo"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: demo\nversion: 1.0.0\n---\n# demo\n", encoding="utf-8"
        )

        exit_code, sbom = _generate_and_load(ws, tmp_path / "clean.json")
        assert exit_code == 0
        meta_props = {p["name"]: p["value"] for p in sbom.get("metadata", {}).get("properties", [])}
        assert meta_props.get("owb:license:non-allowed-count") == "0"

    def test_full_sbom_validates_against_cyclonedx_schema(
        self, four_case_workspace: Path, tmp_path: Path
    ) -> None:
        from cyclonedx.schema import SchemaVersion
        from cyclonedx.validation.json import JsonStrictValidator

        out_path = tmp_path / "validate.json"
        _generate_and_load(four_case_workspace, out_path)
        validator = JsonStrictValidator(SchemaVersion.V1_6)
        errors = validator.validate_str(out_path.read_text(encoding="utf-8"))
        assert errors is None, f"S107b SBOM is not valid CycloneDX 1.6: {errors}"
