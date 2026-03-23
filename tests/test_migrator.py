"""Tests for engine/migrator.py — workspace migration functionality."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from open_workspace_builder.config import Config, load_config
from open_workspace_builder.engine.builder import WorkspaceBuilder
from open_workspace_builder.engine.migrator import (
    MigrateAction,
    MigrateReport,
    format_migrate_report,
    migrate_workspace,
)
from open_workspace_builder.security.scanner import ScanFlag, ScanVerdict


@pytest.fixture
def content_root() -> Path:
    """Return the project content root."""
    root = Path(__file__).resolve().parent.parent
    assert (root / "content").is_dir()
    assert (root / "vendor").is_dir()
    return root


@pytest.fixture
def default_config() -> Config:
    """Return a default config."""
    return load_config()


@pytest.fixture
def drifted_workspace(tmp_path: Path, content_root: Path, default_config: Config) -> Path:
    """Build a workspace with known drift (same as differ test fixture)."""
    ws = tmp_path / "drifted"
    builder = WorkspaceBuilder(default_config, content_root, dry_run=False)
    builder.build(ws)

    all_files = sorted(f for f in ws.rglob("*") if f.is_file())
    assert len(all_files) > 5

    # Delete 2 files → "missing"
    all_files[0].unlink()
    all_files[1].unlink()

    # Replace 1 file with shorter content → "outdated"
    all_files[2].write_text("outdated content\n", encoding="utf-8")

    # Expand 1 file with user additions → "modified"
    original = all_files[3].read_text(encoding="utf-8")
    all_files[3].write_text(
        original + "\n\n## User additions\nCustom section.\n", encoding="utf-8"
    )

    # Add 2 extra user files
    (ws / "my-notes.md").write_text("Personal notes\n", encoding="utf-8")
    (ws / "custom-project.md").write_text("Custom project doc\n", encoding="utf-8")

    return ws


class TestMigrateBatchMode:
    """Test migrate in --accept-all (batch) mode."""

    def test_batch_creates_missing_files(
        self, drifted_workspace: Path, content_root: Path, default_config: Config
    ) -> None:
        report = migrate_workspace(
            drifted_workspace,
            config=default_config,
            content_root=content_root,
            accept_all=True,
        )
        assert report.summary["created"] == 2

    def test_batch_updates_outdated_files(
        self, drifted_workspace: Path, content_root: Path, default_config: Config
    ) -> None:
        report = migrate_workspace(
            drifted_workspace,
            config=default_config,
            content_root=content_root,
            accept_all=True,
        )
        assert report.summary["updated"] == 1

    def test_batch_skips_modified_files(
        self, drifted_workspace: Path, content_root: Path, default_config: Config
    ) -> None:
        report = migrate_workspace(
            drifted_workspace,
            config=default_config,
            content_root=content_root,
            accept_all=True,
        )
        # Modified files should be skipped in batch mode
        assert report.summary["skipped"] == 1

    def test_batch_ignores_extra_files(
        self, drifted_workspace: Path, content_root: Path, default_config: Config
    ) -> None:
        report = migrate_workspace(
            drifted_workspace,
            config=default_config,
            content_root=content_root,
            accept_all=True,
        )
        # Extra files should not appear in actions at all
        extra_actions = [a for a in report.actions if "extra" in a.reason.lower()]
        assert len(extra_actions) == 0

    def test_batch_files_actually_written(
        self, drifted_workspace: Path, content_root: Path, default_config: Config
    ) -> None:
        report = migrate_workspace(
            drifted_workspace,
            config=default_config,
            content_root=content_root,
            accept_all=True,
        )
        created_actions = [a for a in report.actions if a.action == "created"]
        for action in created_actions:
            assert (drifted_workspace / action.path).exists()


class TestMigrateSecurityBlocking:
    """Test that security scanner blocks flagged files."""

    def test_flagged_file_is_blocked(
        self, drifted_workspace: Path, content_root: Path, default_config: Config
    ) -> None:
        flagged_verdict = ScanVerdict(
            file_path="test.md",
            verdict="flagged",
            flags=(
                ScanFlag(
                    category="exfiltration",
                    severity="warning",
                    evidence="curl suspicious",
                    description="Potential data exfiltration",
                    layer=2,
                ),
            ),
        )

        with patch(
            "open_workspace_builder.engine.migrator.Scanner"
        ) as MockScanner:
            mock_instance = MagicMock()
            mock_instance.scan_file.return_value = flagged_verdict
            MockScanner.return_value = mock_instance

            report = migrate_workspace(
                drifted_workspace,
                config=default_config,
                content_root=content_root,
                accept_all=True,
            )

        assert report.summary["blocked"] > 0
        blocked_actions = [a for a in report.actions if a.action == "blocked"]
        assert len(blocked_actions) > 0
        assert len(report.security_flags) > 0

    def test_malicious_file_is_blocked(
        self, drifted_workspace: Path, content_root: Path, default_config: Config
    ) -> None:
        malicious_verdict = ScanVerdict(
            file_path="evil.md",
            verdict="malicious",
            flags=(
                ScanFlag(
                    category="prompt_injection",
                    severity="critical",
                    evidence="you are now",
                    description="Prompt injection attack",
                    layer=2,
                ),
            ),
        )

        with patch(
            "open_workspace_builder.engine.migrator.Scanner"
        ) as MockScanner:
            mock_instance = MagicMock()
            mock_instance.scan_file.return_value = malicious_verdict
            MockScanner.return_value = mock_instance

            report = migrate_workspace(
                drifted_workspace,
                config=default_config,
                content_root=content_root,
                accept_all=True,
            )

        assert report.summary["blocked"] > 0


class TestMigrateDryRun:
    """Test that dry-run mode does not write files."""

    def test_dry_run_no_files_written(
        self, drifted_workspace: Path, content_root: Path, default_config: Config
    ) -> None:
        # Snapshot the workspace before migration
        files_before = set()
        for f in drifted_workspace.rglob("*"):
            if f.is_file():
                files_before.add((str(f.relative_to(drifted_workspace)), f.read_bytes()))

        migrate_workspace(
            drifted_workspace,
            config=default_config,
            content_root=content_root,
            accept_all=True,
            dry_run=True,
        )

        # Verify no files were changed or created (except migration log)
        files_after = set()
        for f in drifted_workspace.rglob("*"):
            if f.is_file() and ".owb" not in str(f.relative_to(drifted_workspace)):
                files_after.add((str(f.relative_to(drifted_workspace)), f.read_bytes()))

        # The non-.owb files should be identical
        assert files_before == files_after

    def test_dry_run_produces_report(
        self, drifted_workspace: Path, content_root: Path, default_config: Config
    ) -> None:
        report = migrate_workspace(
            drifted_workspace,
            config=default_config,
            content_root=content_root,
            accept_all=True,
            dry_run=True,
        )
        # Should still produce a report with actions
        total = sum(report.summary.values())
        assert total > 0

    def test_dry_run_no_migration_log(
        self, drifted_workspace: Path, content_root: Path, default_config: Config
    ) -> None:
        migrate_workspace(
            drifted_workspace,
            config=default_config,
            content_root=content_root,
            accept_all=True,
            dry_run=True,
        )
        log_file = drifted_workspace / ".owb" / "migration-log.jsonl"
        assert not log_file.exists()


class TestMigrationLog:
    """Test that migration log is created correctly."""

    def test_migration_log_created(
        self, drifted_workspace: Path, content_root: Path, default_config: Config
    ) -> None:
        migrate_workspace(
            drifted_workspace,
            config=default_config,
            content_root=content_root,
            accept_all=True,
        )
        log_file = drifted_workspace / ".owb" / "migration-log.jsonl"
        assert log_file.exists()

    def test_migration_log_entries_valid_json(
        self, drifted_workspace: Path, content_root: Path, default_config: Config
    ) -> None:
        migrate_workspace(
            drifted_workspace,
            config=default_config,
            content_root=content_root,
            accept_all=True,
        )
        log_file = drifted_workspace / ".owb" / "migration-log.jsonl"
        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) > 0
        for line in lines:
            entry = json.loads(line)
            assert "timestamp" in entry
            assert "action" in entry
            assert "path" in entry
            assert "reason" in entry

    def test_migration_log_entry_count_matches_actions(
        self, drifted_workspace: Path, content_root: Path, default_config: Config
    ) -> None:
        report = migrate_workspace(
            drifted_workspace,
            config=default_config,
            content_root=content_root,
            accept_all=True,
        )
        log_file = drifted_workspace / ".owb" / "migration-log.jsonl"
        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        # Log entries should match the number of non-extra actions
        assert len(lines) == len(report.actions)


class TestMigrateReportFormatting:
    """Test report formatting."""

    def test_format_empty_report(self) -> None:
        report = MigrateReport(
            actions=(),
            summary={"created": 0, "updated": 0, "skipped": 0, "rejected": 0, "blocked": 0},
            security_flags=(),
        )
        text = format_migrate_report(report)
        assert "Migration Report" in text

    def test_format_with_actions(self) -> None:
        report = MigrateReport(
            actions=(
                MigrateAction(path="foo.md", action="created", reason="Batch auto-accept"),
                MigrateAction(path="bar.md", action="blocked", reason="Security flagged"),
            ),
            summary={"created": 1, "updated": 0, "skipped": 0, "rejected": 0, "blocked": 1},
            security_flags=(
                ScanVerdict(file_path="bar.md", verdict="flagged", flags=()),
            ),
        )
        text = format_migrate_report(report)
        assert "foo.md" in text
        assert "bar.md" in text
        assert "blocked" in text.lower()

    def test_format_shows_security_flags(self) -> None:
        report = MigrateReport(
            actions=(
                MigrateAction(path="evil.md", action="blocked", reason="Security flagged"),
            ),
            summary={"created": 0, "updated": 0, "skipped": 0, "rejected": 0, "blocked": 1},
            security_flags=(
                ScanVerdict(file_path="evil.md", verdict="malicious", flags=()),
            ),
        )
        text = format_migrate_report(report)
        assert "Security flags" in text
        assert "evil.md" in text


class TestMigrateInteractive:
    """Test interactive mode with mocked prompts."""

    def test_interactive_accept(
        self, drifted_workspace: Path, content_root: Path, default_config: Config
    ) -> None:
        responses = iter(["y"] * 20)  # Accept everything

        report = migrate_workspace(
            drifted_workspace,
            config=default_config,
            content_root=content_root,
            accept_all=False,
            prompt_fn=lambda _msg: next(responses),
        )
        created = report.summary.get("created", 0)
        updated = report.summary.get("updated", 0)
        assert created + updated > 0

    def test_interactive_reject(
        self, drifted_workspace: Path, content_root: Path, default_config: Config
    ) -> None:
        responses = iter(["n"] * 20)  # Reject everything

        report = migrate_workspace(
            drifted_workspace,
            config=default_config,
            content_root=content_root,
            accept_all=False,
            prompt_fn=lambda _msg: next(responses),
        )
        assert report.summary.get("rejected", 0) > 0
        assert report.summary.get("created", 0) == 0

    def test_interactive_quit(
        self, drifted_workspace: Path, content_root: Path, default_config: Config
    ) -> None:
        # Accept first, then quit
        responses = iter(["y", "q"] + ["y"] * 20)

        report = migrate_workspace(
            drifted_workspace,
            config=default_config,
            content_root=content_root,
            accept_all=False,
            prompt_fn=lambda _msg: next(responses),
        )
        skipped = report.summary.get("skipped", 0)
        assert skipped > 0
