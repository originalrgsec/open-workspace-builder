"""OWB-S107c — Tests for the SBOM quarantine window check + gate hook."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from open_workspace_builder.sbom.quarantine import (
    DEFAULT_QUARANTINE_DAYS,
    check_quarantine,
    check_workspace_quarantine,
    render_report_json,
    render_report_text,
)


def _component(
    *,
    bom_ref: str = "owb:skill/a@1",
    name: str = "demo",
    kind: str = "skill",
    added_at: str | None = None,
) -> dict[str, Any]:
    properties: list[dict[str, str]] = [{"name": "owb:kind", "value": kind}]
    if added_at is not None:
        properties.append({"name": "owb:provenance:added-at", "value": added_at})
    return {
        "type": "library",
        "bom-ref": bom_ref,
        "name": name,
        "version": "1.0",
        "hashes": [{"alg": "SHA-256", "content": "a" * 64}],
        "properties": properties,
    }


def _bom(*components: dict[str, Any]) -> dict[str, Any]:
    return {"bomFormat": "CycloneDX", "specVersion": "1.6", "components": list(components)}


# ---------------------------------------------------------------------------
# Window logic
# ---------------------------------------------------------------------------


class TestWindowLogic:
    def _today(self) -> date:
        return date(2026, 4, 11)

    def test_no_components_no_quarantine(self) -> None:
        report = check_quarantine(_bom(), days=7, today=self._today())
        assert report.total_components == 0
        assert report.quarantined == ()

    def test_inside_window_today(self) -> None:
        bom = _bom(_component(added_at="2026-04-11"))
        report = check_quarantine(bom, days=7, today=self._today())
        assert len(report.quarantined) == 1
        assert report.quarantined[0].age_days == 0

    def test_inside_window_n_minus_1(self) -> None:
        bom = _bom(_component(added_at="2026-04-05"))  # 6 days ago
        report = check_quarantine(bom, days=7, today=self._today())
        assert len(report.quarantined) == 1
        assert report.quarantined[0].age_days == 6

    def test_at_window_boundary_n_days(self) -> None:
        # Exactly N days ago — boundary stays inside the window.
        bom = _bom(_component(added_at="2026-04-04"))  # 7 days ago
        report = check_quarantine(bom, days=7, today=self._today())
        assert len(report.quarantined) == 1
        assert report.quarantined[0].age_days == 7

    def test_outside_window_n_plus_1(self) -> None:
        bom = _bom(_component(added_at="2026-04-03"))  # 8 days ago
        report = check_quarantine(bom, days=7, today=self._today())
        assert report.quarantined == ()

    def test_future_date_skipped(self) -> None:
        bom = _bom(_component(added_at="2026-12-31"))
        report = check_quarantine(bom, days=7, today=self._today())
        assert report.quarantined == ()

    def test_missing_added_at_skipped(self) -> None:
        bom = _bom(_component(added_at=None))
        report = check_quarantine(bom, days=7, today=self._today())
        assert report.total_components == 1
        assert report.quarantined == ()

    def test_malformed_added_at_skipped(self) -> None:
        bom = _bom(_component(added_at="not-a-date"))
        report = check_quarantine(bom, days=7, today=self._today())
        assert report.quarantined == ()

    def test_days_zero_window(self) -> None:
        bom = _bom(_component(added_at="2026-04-11"))
        report = check_quarantine(bom, days=0, today=self._today())
        assert len(report.quarantined) == 1

    def test_negative_days_raises(self) -> None:
        with pytest.raises(ValueError):
            check_quarantine(_bom(), days=-1)

    def test_default_days_constant(self) -> None:
        assert DEFAULT_QUARANTINE_DAYS == 7


# ---------------------------------------------------------------------------
# Workspace wrapper
# ---------------------------------------------------------------------------


class TestWorkspaceWrapper:
    def test_missing_workspace_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            check_workspace_quarantine(workspace=tmp_path / "nope")

    def test_empty_workspace_returns_empty_report(self, tmp_path: Path) -> None:
        # Create an empty workspace dir.
        report = check_workspace_quarantine(workspace=tmp_path, days=7)
        assert report.total_components == 0
        assert report.quarantined == ()

    def test_workspace_with_skill_reports_added_at(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / ".claude" / "skills" / "demo"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: demo\n---\nbody\n")
        # Skill was just created — added_at should be today via mtime fallback.
        report = check_workspace_quarantine(workspace=tmp_path, days=7)
        assert report.total_components == 1
        assert len(report.quarantined) == 1


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


class TestRenderers:
    def _today(self) -> date:
        return date(2026, 4, 11)

    def test_text_clean_report(self) -> None:
        report = check_quarantine(
            _bom(_component(added_at="2026-01-01")),
            days=7,
            today=self._today(),
        )
        text = render_report_text(report)
        assert "OK" in text
        assert "0 of 1" in text

    def test_text_warning_report(self) -> None:
        report = check_quarantine(
            _bom(_component(added_at="2026-04-11", name="hello")),
            days=7,
            today=self._today(),
        )
        text = render_report_text(report)
        assert "WARNING" in text
        assert "hello" in text

    def test_json_renders(self) -> None:
        import json

        report = check_quarantine(
            _bom(_component(added_at="2026-04-11", name="hello")),
            days=7,
            today=self._today(),
        )
        parsed = json.loads(render_report_json(report))
        assert parsed["days"] == 7
        assert len(parsed["quarantined"]) == 1
        assert parsed["quarantined"][0]["name"] == "hello"


# ---------------------------------------------------------------------------
# Gate hook
# ---------------------------------------------------------------------------


class TestGateHook:
    def test_clean_workspace_passes(self, tmp_path: Path) -> None:
        from open_workspace_builder.security.gate import _check_skill_quarantine

        check = _check_skill_quarantine(tmp_path, days=7)
        assert check.name == "skill-quarantine"
        assert check.passed is True

    def test_workspace_with_recent_skill_fails(self, tmp_path: Path) -> None:
        from open_workspace_builder.security.gate import _check_skill_quarantine

        skill_dir = tmp_path / ".claude" / "skills" / "demo"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: demo\n---\nbody\n")

        check = _check_skill_quarantine(tmp_path, days=7)
        assert check.passed is False
        assert "demo" in check.details

    def test_missing_workspace_skipped_not_failed(self, tmp_path: Path) -> None:
        from open_workspace_builder.security.gate import _check_skill_quarantine

        check = _check_skill_quarantine(tmp_path / "nope", days=7)
        assert check.passed is True
        assert "skipped" in check.details
