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

    def test_format_spdx_accepted_in_s107c(self, tmp_path: Path) -> None:
        """S107c: SPDX 2.3 emitter is wired into `owb sbom generate --format spdx`."""
        ws = _make_workspace(tmp_path)
        runner = CliRunner()
        result = runner.invoke(owb, ["sbom", "generate", str(ws), "--format", "spdx"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["spdxVersion"] == "SPDX-2.3"
        assert "packages" in data


class TestSbomGroupHelp:
    def test_sbom_group_is_registered(self) -> None:
        runner = CliRunner()
        result = runner.invoke(owb, ["sbom", "--help"])
        assert result.exit_code == 0
        assert "generate" in result.output

    def test_all_s107c_subcommands_registered(self) -> None:
        runner = CliRunner()
        result = runner.invoke(owb, ["sbom", "--help"])
        for sub in ("generate", "diff", "verify", "show", "quarantine"):
            assert sub in result.output


# ---------------------------------------------------------------------------
# S107c subcommand CLI integration
# ---------------------------------------------------------------------------


def _generate_sbom(ws: Path, runner: CliRunner) -> Path:
    out = ws.parent / f"{ws.name}.cdx.json"
    result = runner.invoke(owb, ["sbom", "generate", str(ws), "--output", str(out)])
    assert result.exit_code == 0, result.output
    return out


class TestDiffCommand:
    def test_no_diff_exits_zero(self, tmp_path: Path) -> None:
        ws = _make_workspace(tmp_path)
        runner = CliRunner()
        sbom = _generate_sbom(ws, runner)
        result = runner.invoke(owb, ["sbom", "diff", str(sbom), str(sbom)])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["added"] == [] and parsed["removed"] == [] and parsed["changed"] == []

    def test_drift_exits_two(self, tmp_path: Path) -> None:
        ws = _make_workspace(tmp_path)
        runner = CliRunner()
        old_sbom = _generate_sbom(ws, runner)
        # Mutate workspace and regen.
        skill = ws / ".claude" / "skills" / "xlsx" / "SKILL.md"
        skill.write_text("---\nname: xlsx\nversion: 2.0\n---\n# changed body\n")
        new_sbom = ws.parent / "new.cdx.json"
        runner.invoke(owb, ["sbom", "generate", str(ws), "--output", str(new_sbom)])

        result = runner.invoke(owb, ["sbom", "diff", str(old_sbom), str(new_sbom)])
        assert result.exit_code == 2

    def test_text_format(self, tmp_path: Path) -> None:
        ws = _make_workspace(tmp_path)
        runner = CliRunner()
        sbom = _generate_sbom(ws, runner)
        result = runner.invoke(owb, ["sbom", "diff", str(sbom), str(sbom), "--format", "text"])
        assert result.exit_code == 0
        assert "summary:" in result.output

    def test_missing_file_exits_one(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            owb, ["sbom", "diff", str(tmp_path / "a.json"), str(tmp_path / "b.json")]
        )
        # Click validates the exists path before our code runs, so the exit
        # code may be 2 from Click's UsageError. The relevant assertion is
        # that the command does not return 0.
        assert result.exit_code != 0


class TestVerifyCommand:
    def test_match_exits_zero(self, tmp_path: Path) -> None:
        ws = _make_workspace(tmp_path)
        runner = CliRunner()
        canonical = ws / ".owb" / "sbom.cdx.json"
        canonical.parent.mkdir(parents=True, exist_ok=True)
        runner.invoke(owb, ["sbom", "generate", str(ws), "--output", str(canonical)])

        result = runner.invoke(owb, ["sbom", "verify", "--workspace", str(ws)])
        assert result.exit_code == 0, result.output

    def test_drift_exits_two(self, tmp_path: Path) -> None:
        ws = _make_workspace(tmp_path)
        runner = CliRunner()
        canonical = ws / ".owb" / "sbom.cdx.json"
        canonical.parent.mkdir(parents=True, exist_ok=True)
        runner.invoke(owb, ["sbom", "generate", str(ws), "--output", str(canonical)])

        # Mutate.
        skill = ws / ".claude" / "skills" / "xlsx" / "SKILL.md"
        skill.write_text("---\nname: xlsx\nversion: 1.0\n---\n# DRIFT\n")

        result = runner.invoke(owb, ["sbom", "verify", "--workspace", str(ws)])
        assert result.exit_code == 2, result.output

    def test_missing_canonical_exits_one(self, tmp_path: Path) -> None:
        ws = _make_workspace(tmp_path)
        runner = CliRunner()
        result = runner.invoke(owb, ["sbom", "verify", "--workspace", str(ws)])
        assert result.exit_code == 1


class TestShowCommand:
    def test_summary_lists_components(self, tmp_path: Path) -> None:
        ws = _make_workspace(tmp_path)
        runner = CliRunner()
        sbom = _generate_sbom(ws, runner)
        result = runner.invoke(owb, ["sbom", "show", str(sbom)])
        assert result.exit_code == 0
        assert "xlsx" in result.output and "planner" in result.output

    def test_component_detail(self, tmp_path: Path) -> None:
        ws = _make_workspace(tmp_path)
        runner = CliRunner()
        sbom = _generate_sbom(ws, runner)
        # Find a real bom-ref from the generated file.
        bom = json.loads(sbom.read_text())
        ref = bom["components"][0]["bom-ref"]
        result = runner.invoke(owb, ["sbom", "show", str(sbom), "--component", ref])
        assert result.exit_code == 0
        assert ref in result.output

    def test_component_not_found_exits_two(self, tmp_path: Path) -> None:
        ws = _make_workspace(tmp_path)
        runner = CliRunner()
        sbom = _generate_sbom(ws, runner)
        result = runner.invoke(
            owb, ["sbom", "show", str(sbom), "--component", "owb:skill/missing@9"]
        )
        assert result.exit_code == 2


class TestQuarantineCommand:
    def test_recently_added_exits_two(self, tmp_path: Path) -> None:
        ws = _make_workspace(tmp_path)
        runner = CliRunner()
        result = runner.invoke(owb, ["sbom", "quarantine", "--workspace", str(ws), "--days", "7"])
        # Files were just created — added_at = today via mtime, expect drift.
        assert result.exit_code == 2

    def test_zero_days_baseline(self, tmp_path: Path) -> None:
        ws = _make_workspace(tmp_path)
        runner = CliRunner()
        result = runner.invoke(owb, ["sbom", "quarantine", "--workspace", str(ws), "--days", "0"])
        # days=0 still flags components added today (age 0 == cutoff).
        assert result.exit_code == 2

    def test_with_explicit_sbom(self, tmp_path: Path) -> None:
        ws = _make_workspace(tmp_path)
        runner = CliRunner()
        sbom = _generate_sbom(ws, runner)
        result = runner.invoke(owb, ["sbom", "quarantine", "--sbom", str(sbom), "--days", "7"])
        assert result.exit_code == 2


# ---------------------------------------------------------------------------
# S107c workflow AC — full pipeline through the CLI
# ---------------------------------------------------------------------------


class TestWorkflowAcceptance:
    def test_generate_show_diff_verify_quarantine_pipeline(self, tmp_path: Path) -> None:
        ws = _make_workspace(tmp_path)
        runner = CliRunner()

        # 1. Generate canonical SBOM
        canonical = ws / ".owb" / "sbom.cdx.json"
        canonical.parent.mkdir(parents=True, exist_ok=True)
        gen = runner.invoke(owb, ["sbom", "generate", str(ws), "--output", str(canonical)])
        assert gen.exit_code == 0, gen.output

        # 2. show summary works
        show = runner.invoke(owb, ["sbom", "show", str(canonical)])
        assert show.exit_code == 0

        # 3. verify on the just-generated SBOM matches
        ver = runner.invoke(owb, ["sbom", "verify", "--workspace", str(ws)])
        assert ver.exit_code == 0, ver.output

        # 4. diff against itself yields no changes
        diff = runner.invoke(owb, ["sbom", "diff", str(canonical), str(canonical)])
        assert diff.exit_code == 0

        # 5. quarantine flags fresh components
        quar = runner.invoke(owb, ["sbom", "quarantine", "--workspace", str(ws), "--days", "7"])
        assert quar.exit_code == 2

        # 6. SPDX format works alongside CycloneDX
        spdx = runner.invoke(owb, ["sbom", "generate", str(ws), "--format", "spdx"])
        assert spdx.exit_code == 0
        assert '"SPDX-2.3"' in spdx.output
