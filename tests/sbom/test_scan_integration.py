"""OWB-S107a — `owb scan --emit-sbom PATH` integration tests."""

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
    return ws


class TestEmitSbomFlag:
    def test_scan_emits_sbom_to_file(self, tmp_path: Path) -> None:
        ws = _make_workspace(tmp_path)
        sbom_path = tmp_path / "workspace.cdx.json"
        runner = CliRunner()
        result = runner.invoke(
            owb,
            ["security", "scan", str(ws), "--emit-sbom", str(sbom_path), "--layers", "1"],
        )
        # Scan may exit 0 (clean) or 2 (findings). Both are acceptable here.
        assert result.exit_code in (0, 2), result.output
        assert sbom_path.is_file()

    def test_emitted_sbom_is_valid_cyclonedx(self, tmp_path: Path) -> None:
        ws = _make_workspace(tmp_path)
        sbom_path = tmp_path / "workspace.cdx.json"
        runner = CliRunner()
        runner.invoke(
            owb,
            ["security", "scan", str(ws), "--emit-sbom", str(sbom_path), "--layers", "1"],
        )
        data = json.loads(sbom_path.read_text(encoding="utf-8"))
        assert data["bomFormat"] == "CycloneDX"
        assert data["specVersion"] == "1.6"

    def test_emitted_sbom_contains_discovered_components(self, tmp_path: Path) -> None:
        ws = _make_workspace(tmp_path)
        sbom_path = tmp_path / "workspace.cdx.json"
        runner = CliRunner()
        runner.invoke(
            owb,
            ["security", "scan", str(ws), "--emit-sbom", str(sbom_path), "--layers", "1"],
        )
        data = json.loads(sbom_path.read_text(encoding="utf-8"))
        names = {c["name"] for c in data.get("components", [])}
        assert "xlsx" in names

    def test_scan_without_emit_sbom_unchanged(self, tmp_path: Path) -> None:
        """Baseline: scan without --emit-sbom behaves exactly as before."""
        ws = _make_workspace(tmp_path)
        runner = CliRunner()
        result = runner.invoke(owb, ["security", "scan", str(ws), "--layers", "1"])
        assert result.exit_code in (0, 2)
        # No SBOM side-effect files anywhere nearby.
        assert not (tmp_path / "workspace.cdx.json").exists()
