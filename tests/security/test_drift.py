"""Tests for directive drift detection (S082)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from open_workspace_builder.security.drift import (
    DriftEntry,
    DriftReport,
    DriftStatus,
    check_drift,
    update_baseline,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_workspace(tmp_path: Path) -> Path:
    """Create a minimal workspace with directive files."""
    ws = tmp_path / "workspace"
    claude_dir = ws / ".claude"
    agents_dir = claude_dir / "agents"
    rules_dir = claude_dir / "rules"

    agents_dir.mkdir(parents=True)
    rules_dir.mkdir(parents=True)

    (ws / "CLAUDE.md").write_text("# Main config\n", encoding="utf-8")
    (agents_dir / "planner.md").write_text("# Planner agent\n", encoding="utf-8")
    (rules_dir / "style.md").write_text("# Style rule\n", encoding="utf-8")

    return ws


# ---------------------------------------------------------------------------
# Baseline creation
# ---------------------------------------------------------------------------


class TestUpdateBaseline:
    """owb security drift --update-baseline creates a baseline file."""

    def test_creates_baseline_file(self, tmp_path: Path) -> None:
        ws = _create_workspace(tmp_path)
        baseline_path = tmp_path / "drift-baseline.json"

        update_baseline(ws, baseline_path)

        assert baseline_path.is_file()

    def test_baseline_contains_hashes(self, tmp_path: Path) -> None:
        ws = _create_workspace(tmp_path)
        baseline_path = tmp_path / "drift-baseline.json"

        update_baseline(ws, baseline_path)

        data = json.loads(baseline_path.read_text(encoding="utf-8"))
        assert "files" in data
        assert len(data["files"]) > 0
        # Each entry should have a hash
        for entry in data["files"].values():
            assert "sha256" in entry
            assert len(entry["sha256"]) == 64  # SHA-256 hex length

    def test_baseline_has_schema_version(self, tmp_path: Path) -> None:
        ws = _create_workspace(tmp_path)
        baseline_path = tmp_path / "drift-baseline.json"

        update_baseline(ws, baseline_path)

        data = json.loads(baseline_path.read_text(encoding="utf-8"))
        assert "schema_version" in data
        assert data["schema_version"] == 1

    def test_baseline_has_timestamp(self, tmp_path: Path) -> None:
        ws = _create_workspace(tmp_path)
        baseline_path = tmp_path / "drift-baseline.json"

        update_baseline(ws, baseline_path)

        data = json.loads(baseline_path.read_text(encoding="utf-8"))
        assert "timestamp" in data

    def test_baseline_tracks_claude_md(self, tmp_path: Path) -> None:
        ws = _create_workspace(tmp_path)
        baseline_path = tmp_path / "drift-baseline.json"

        update_baseline(ws, baseline_path)

        data = json.loads(baseline_path.read_text(encoding="utf-8"))
        paths = list(data["files"].keys())
        assert any("CLAUDE.md" in p for p in paths)

    def test_baseline_tracks_agents(self, tmp_path: Path) -> None:
        ws = _create_workspace(tmp_path)
        baseline_path = tmp_path / "drift-baseline.json"

        update_baseline(ws, baseline_path)

        data = json.loads(baseline_path.read_text(encoding="utf-8"))
        paths = list(data["files"].keys())
        assert any("planner.md" in p for p in paths)

    def test_baseline_tracks_rules(self, tmp_path: Path) -> None:
        ws = _create_workspace(tmp_path)
        baseline_path = tmp_path / "drift-baseline.json"

        update_baseline(ws, baseline_path)

        data = json.loads(baseline_path.read_text(encoding="utf-8"))
        paths = list(data["files"].keys())
        assert any("style.md" in p for p in paths)

    def test_baseline_uses_atomic_write(self, tmp_path: Path) -> None:
        """AC-7: Baseline uses atomic writes."""
        ws = _create_workspace(tmp_path)
        baseline_path = tmp_path / "drift-baseline.json"

        # Write initial baseline
        update_baseline(ws, baseline_path)
        initial = baseline_path.read_text(encoding="utf-8")

        # Update baseline — should not corrupt if interrupted
        (ws / "CLAUDE.md").write_text("# Modified\n", encoding="utf-8")
        update_baseline(ws, baseline_path)
        updated = baseline_path.read_text(encoding="utf-8")

        assert initial != updated
        # Verify it's valid JSON
        json.loads(updated)


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------


class TestCheckDrift:
    """owb security drift compares current state against baseline."""

    def test_no_drift_returns_clean(self, tmp_path: Path) -> None:
        ws = _create_workspace(tmp_path)
        baseline_path = tmp_path / "drift-baseline.json"
        update_baseline(ws, baseline_path)

        report = check_drift(ws, baseline_path)

        assert report.has_drift is False
        assert report.modified == ()
        assert report.added == ()
        assert report.deleted == ()

    def test_modified_file_detected(self, tmp_path: Path) -> None:
        """AC-2: Modified files are reported."""
        ws = _create_workspace(tmp_path)
        baseline_path = tmp_path / "drift-baseline.json"
        update_baseline(ws, baseline_path)

        # Modify a tracked file
        (ws / "CLAUDE.md").write_text("# MODIFIED config\n", encoding="utf-8")

        report = check_drift(ws, baseline_path)

        assert report.has_drift is True
        assert len(report.modified) == 1
        assert "CLAUDE.md" in report.modified[0].rel_path

    def test_added_file_detected(self, tmp_path: Path) -> None:
        """AC-2: New files not in baseline are reported as added."""
        ws = _create_workspace(tmp_path)
        baseline_path = tmp_path / "drift-baseline.json"
        update_baseline(ws, baseline_path)

        # Add a new agent
        (ws / ".claude" / "agents" / "new-agent.md").write_text(
            "# New agent\n", encoding="utf-8"
        )

        report = check_drift(ws, baseline_path)

        assert report.has_drift is True
        assert len(report.added) == 1
        assert "new-agent.md" in report.added[0].rel_path

    def test_deleted_file_detected(self, tmp_path: Path) -> None:
        """AC-2: Files in baseline but missing from disk are reported."""
        ws = _create_workspace(tmp_path)
        baseline_path = tmp_path / "drift-baseline.json"
        update_baseline(ws, baseline_path)

        # Delete a tracked file
        (ws / ".claude" / "agents" / "planner.md").unlink()

        report = check_drift(ws, baseline_path)

        assert report.has_drift is True
        assert len(report.deleted) == 1
        assert "planner.md" in report.deleted[0].rel_path

    def test_unchanged_files_in_ok_list(self, tmp_path: Path) -> None:
        ws = _create_workspace(tmp_path)
        baseline_path = tmp_path / "drift-baseline.json"
        update_baseline(ws, baseline_path)

        report = check_drift(ws, baseline_path)

        assert len(report.unchanged) > 0

    def test_multiple_changes_detected(self, tmp_path: Path) -> None:
        ws = _create_workspace(tmp_path)
        baseline_path = tmp_path / "drift-baseline.json"
        update_baseline(ws, baseline_path)

        (ws / "CLAUDE.md").write_text("# Modified\n", encoding="utf-8")
        (ws / ".claude" / "agents" / "planner.md").unlink()
        (ws / ".claude" / "rules" / "new-rule.md").write_text(
            "# New\n", encoding="utf-8"
        )

        report = check_drift(ws, baseline_path)

        assert report.has_drift is True
        assert len(report.modified) == 1
        assert len(report.deleted) == 1
        assert len(report.added) == 1


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------


class TestDriftExitCodes:
    """AC-3: Exit codes are 0 (clean), 1 (drift), 2 (no baseline)."""

    def test_exit_code_no_drift(self, tmp_path: Path) -> None:
        ws = _create_workspace(tmp_path)
        baseline_path = tmp_path / "drift-baseline.json"
        update_baseline(ws, baseline_path)

        report = check_drift(ws, baseline_path)
        assert report.exit_code == 0

    def test_exit_code_drift_detected(self, tmp_path: Path) -> None:
        ws = _create_workspace(tmp_path)
        baseline_path = tmp_path / "drift-baseline.json"
        update_baseline(ws, baseline_path)

        (ws / "CLAUDE.md").write_text("# Modified\n", encoding="utf-8")

        report = check_drift(ws, baseline_path)
        assert report.exit_code == 1

    def test_exit_code_no_baseline(self, tmp_path: Path) -> None:
        ws = _create_workspace(tmp_path)
        baseline_path = tmp_path / "drift-baseline.json"
        # Don't create a baseline

        report = check_drift(ws, baseline_path)
        assert report.exit_code == 2


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------


class TestDriftJsonOutput:
    """AC-4: --json produces machine-readable output."""

    def test_report_to_json(self, tmp_path: Path) -> None:
        ws = _create_workspace(tmp_path)
        baseline_path = tmp_path / "drift-baseline.json"
        update_baseline(ws, baseline_path)

        (ws / "CLAUDE.md").write_text("# Modified\n", encoding="utf-8")

        report = check_drift(ws, baseline_path)
        json_output = report.to_json()

        parsed = json.loads(json_output)
        assert "has_drift" in parsed
        assert parsed["has_drift"] is True
        assert "modified" in parsed
        assert "added" in parsed
        assert "deleted" in parsed
        assert "unchanged" in parsed

    def test_clean_report_to_json(self, tmp_path: Path) -> None:
        ws = _create_workspace(tmp_path)
        baseline_path = tmp_path / "drift-baseline.json"
        update_baseline(ws, baseline_path)

        report = check_drift(ws, baseline_path)
        parsed = json.loads(report.to_json())

        assert parsed["has_drift"] is False
        assert parsed["exit_code"] == 0


# ---------------------------------------------------------------------------
# File glob filtering
# ---------------------------------------------------------------------------


class TestDriftFileFiltering:
    """AC-5: --files <glob> restricts check to matching paths."""

    def test_filter_by_glob(self, tmp_path: Path) -> None:
        ws = _create_workspace(tmp_path)
        baseline_path = tmp_path / "drift-baseline.json"
        update_baseline(ws, baseline_path)

        # Modify both CLAUDE.md and an agent
        (ws / "CLAUDE.md").write_text("# Modified\n", encoding="utf-8")
        (ws / ".claude" / "agents" / "planner.md").write_text(
            "# Modified planner\n", encoding="utf-8"
        )

        # Filter to only agents
        report = check_drift(ws, baseline_path, file_glob="**/agents/**")

        assert report.has_drift is True
        assert len(report.modified) == 1
        assert "planner.md" in report.modified[0].rel_path


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestDriftErrorHandling:
    """AC-8: Unreadable files reported as errors."""

    def test_unreadable_file_in_baseline_reports_error(self, tmp_path: Path) -> None:
        ws = _create_workspace(tmp_path)
        baseline_path = tmp_path / "drift-baseline.json"
        update_baseline(ws, baseline_path)

        # Make file unreadable
        agent_file = ws / ".claude" / "agents" / "planner.md"
        agent_file.chmod(0o000)

        try:
            report = check_drift(ws, baseline_path)
            assert len(report.errors) > 0
        finally:
            agent_file.chmod(0o644)
