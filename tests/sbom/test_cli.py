"""OWB-S107a — CLI tests for `owb sbom generate`."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from open_workspace_builder.cli import owb


def _make_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    skill_dir = ws / ".claude" / "skills" / "xlsx"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: xlsx\nversion: 1.0\n---\n# body\n", encoding="utf-8"
    )
    agents_dir = ws / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "planner.md").write_text("---\nname: planner\n---\n# body\n", encoding="utf-8")
    return ws


class TestGenerateCommand:
    def test_exit_code_zero_on_success(self, tmp_path: Path) -> None:
        ws = _make_workspace(tmp_path)
        runner = CliRunner()
        result = runner.invoke(owb, ["sbom", "generate", str(ws)])
        assert result.exit_code == 0, result.output

    def test_writes_to_stdout_by_default(self, tmp_path: Path) -> None:
        ws = _make_workspace(tmp_path)
        runner = CliRunner()
        result = runner.invoke(owb, ["sbom", "generate", str(ws)])
        data = json.loads(result.output)
        assert data["bomFormat"] == "CycloneDX"
        assert data["specVersion"] == "1.6"

    def test_output_flag_writes_to_file(self, tmp_path: Path) -> None:
        ws = _make_workspace(tmp_path)
        output_path = tmp_path / "workspace.cdx.json"
        runner = CliRunner()
        result = runner.invoke(owb, ["sbom", "generate", str(ws), "--output", str(output_path)])
        assert result.exit_code == 0, result.output
        assert output_path.is_file()
        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data["bomFormat"] == "CycloneDX"

    def test_generated_sbom_contains_all_components(self, tmp_path: Path) -> None:
        ws = _make_workspace(tmp_path)
        runner = CliRunner()
        result = runner.invoke(owb, ["sbom", "generate", str(ws)])
        data = json.loads(result.output)
        names = {c["name"] for c in data["components"]}
        assert names == {"xlsx", "planner"}

    def test_missing_workspace_exits_nonzero(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(owb, ["sbom", "generate", str(tmp_path / "nope")])
        assert result.exit_code != 0

    def test_empty_workspace_produces_empty_bom(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        runner = CliRunner()
        result = runner.invoke(owb, ["sbom", "generate", str(empty)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data.get("components", []) == []

    def test_format_cyclonedx_accepted(self, tmp_path: Path) -> None:
        ws = _make_workspace(tmp_path)
        runner = CliRunner()
        result = runner.invoke(owb, ["sbom", "generate", str(ws), "--format", "cyclonedx"])
        assert result.exit_code == 0

    def test_format_spdx_rejected_in_s107a(self, tmp_path: Path) -> None:
        """SPDX output is deferred to S107c; attempting it should fail cleanly."""
        ws = _make_workspace(tmp_path)
        runner = CliRunner()
        result = runner.invoke(owb, ["sbom", "generate", str(ws), "--format", "spdx"])
        assert result.exit_code != 0


class TestSbomGroupHelp:
    def test_sbom_group_is_registered(self) -> None:
        runner = CliRunner()
        result = runner.invoke(owb, ["sbom", "--help"])
        assert result.exit_code == 0
        assert "generate" in result.output
