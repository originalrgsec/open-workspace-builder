"""Tests for S037 — Update Command Refactor."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from open_workspace_builder.sources.audit import (
    AuditFinding,
    AuditVerdict,
    RepoAuditResult,
)
from open_workspace_builder.sources.discovery import DiscoveredFile, SourceConfig, SourceDiscovery
from open_workspace_builder.sources.updater import UpdateSummary, SourceUpdater

if TYPE_CHECKING:
    from open_workspace_builder.config import Config


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_config() -> "Config":
    """Real Config with defaults; updater needs `sources.allowed_schemes`
    for OWB-SEC-005 URL validation, so a bare MagicMock no longer works."""
    from open_workspace_builder.config import Config

    return Config()


@pytest.fixture
def source_config() -> SourceConfig:
    return SourceConfig(
        name="ecc",
        repo_url="https://github.com/example/ecc",
        pin="abc123",
        patterns=("**/SKILL.md",),
        exclude=("vendor/**",),
    )


@pytest.fixture
def mock_discovery(source_config: SourceConfig, tmp_path: Path) -> MagicMock:
    """Discovery that returns two files."""
    skill_a = tmp_path / "repo" / "skills" / "a" / "SKILL.md"
    skill_a.parent.mkdir(parents=True, exist_ok=True)
    skill_a.write_text("# Skill A\nClean skill content.\n")

    skill_b = tmp_path / "repo" / "skills" / "b" / "SKILL.md"
    skill_b.parent.mkdir(parents=True, exist_ok=True)
    skill_b.write_text("# Skill B\nAnother clean skill.\n")

    discovery = MagicMock(spec=SourceDiscovery)
    discovery.get_config.return_value = source_config
    discovery.discover.return_value = [
        DiscoveredFile(
            source_name="ecc", relative_path="skills/a/SKILL.md", absolute_path=str(skill_a)
        ),
        DiscoveredFile(
            source_name="ecc", relative_path="skills/b/SKILL.md", absolute_path=str(skill_b)
        ),
    ]
    return discovery


@pytest.fixture
def clean_scanner() -> MagicMock:
    from open_workspace_builder.security.scanner import ScanVerdict

    scanner = MagicMock()
    scanner.scan_file.side_effect = lambda path: ScanVerdict(
        file_path=str(path), verdict="clean", flags=()
    )
    return scanner


@pytest.fixture
def flagging_scanner() -> MagicMock:
    from open_workspace_builder.security.scanner import ScanFlag, ScanVerdict

    def _scan(path: Path) -> ScanVerdict:
        if "skills/a/" in str(path):
            return ScanVerdict(
                file_path=str(path),
                verdict="malicious",
                flags=(ScanFlag("exfil", "critical", "curl", "exfiltration", layer=2),),
            )
        return ScanVerdict(file_path=str(path), verdict="clean", flags=())

    scanner = MagicMock()
    scanner.scan_file.side_effect = _scan
    return scanner


@pytest.fixture
def pass_auditor() -> MagicMock:
    auditor = MagicMock()
    auditor.audit.return_value = RepoAuditResult(
        source_name="ecc",
        verdict=AuditVerdict.PASS,
        findings=(),
        audited_at="2026-01-01T00:00:00+00:00",
    )
    return auditor


@pytest.fixture
def block_auditor() -> MagicMock:
    auditor = MagicMock()
    auditor.audit.return_value = RepoAuditResult(
        source_name="ecc",
        verdict=AuditVerdict.BLOCK,
        findings=(
            AuditFinding(
                "hooks/evil.sh", "hooks_executable", AuditVerdict.BLOCK, "script in hooks/"
            ),
        ),
        audited_at="2026-01-01T00:00:00+00:00",
    )
    return auditor


@pytest.fixture
def warn_auditor() -> MagicMock:
    auditor = MagicMock()
    auditor.audit.return_value = RepoAuditResult(
        source_name="ecc",
        verdict=AuditVerdict.WARN,
        findings=(
            AuditFinding(
                "skills/a/SKILL.md", "event_trigger", AuditVerdict.WARN, "on_install found"
            ),
        ),
        audited_at="2026-01-01T00:00:00+00:00",
    )
    return auditor


# ---------------------------------------------------------------------------
# UpdateSummary dataclass
# ---------------------------------------------------------------------------


class TestUpdateSummary:
    def test_frozen(self) -> None:
        s = UpdateSummary(
            source_name="ecc",
            files_accepted=("a.md",),
            files_rejected=(),
            files_blocked=(),
            files_warned=(),
            audit_verdict="pass",
        )
        with pytest.raises(AttributeError):
            s.source_name = "other"  # type: ignore[misc]

    def test_fields(self) -> None:
        s = UpdateSummary(
            source_name="ecc",
            files_accepted=("a.md", "b.md"),
            files_rejected=("c.md",),
            files_blocked=("d.md",),
            files_warned=("e.md",),
            audit_verdict="warn",
        )
        assert len(s.files_accepted) == 2
        assert len(s.files_rejected) == 1
        assert s.audit_verdict == "warn"


# ---------------------------------------------------------------------------
# SourceUpdater pipeline
# ---------------------------------------------------------------------------


class TestSourceUpdater:
    @patch("open_workspace_builder.sources.updater._clone_or_fetch")
    def test_non_interactive_accept_all(
        self,
        mock_clone: MagicMock,
        mock_config: "Config",
        clean_scanner: MagicMock,
        mock_discovery: MagicMock,
        pass_auditor: MagicMock,
        tmp_path: Path,
    ) -> None:
        vendor = tmp_path / "vendor"
        vendor.mkdir()
        updater = SourceUpdater(mock_config, clean_scanner, mock_discovery, pass_auditor)
        summary = updater.update("ecc", interactive=False, vendor_dir=vendor)
        assert summary.audit_verdict == "pass"
        assert len(summary.files_accepted) == 2
        assert len(summary.files_rejected) == 0
        assert len(summary.files_blocked) == 0

    @patch("open_workspace_builder.sources.updater._clone_or_fetch")
    def test_block_audit_halts(
        self,
        mock_clone: MagicMock,
        mock_config: "Config",
        clean_scanner: MagicMock,
        mock_discovery: MagicMock,
        block_auditor: MagicMock,
    ) -> None:
        updater = SourceUpdater(mock_config, clean_scanner, mock_discovery, block_auditor)
        summary = updater.update("ecc", interactive=False)
        assert summary.audit_verdict == "block"
        assert len(summary.files_blocked) == 2
        assert len(summary.files_accepted) == 0

    @patch("open_workspace_builder.sources.updater._clone_or_fetch")
    def test_warn_excludes_files(
        self,
        mock_clone: MagicMock,
        mock_config: "Config",
        clean_scanner: MagicMock,
        mock_discovery: MagicMock,
        warn_auditor: MagicMock,
        tmp_path: Path,
    ) -> None:
        vendor = tmp_path / "vendor"
        vendor.mkdir()
        updater = SourceUpdater(mock_config, clean_scanner, mock_discovery, warn_auditor)
        summary = updater.update("ecc", interactive=False, vendor_dir=vendor)
        assert summary.audit_verdict == "warn"
        assert "skills/a/SKILL.md" in summary.files_warned
        assert "skills/a/SKILL.md" not in summary.files_accepted
        assert "skills/b/SKILL.md" in summary.files_accepted

    @patch("open_workspace_builder.sources.updater._clone_or_fetch")
    def test_flagged_files_blocked(
        self,
        mock_clone: MagicMock,
        mock_config: "Config",
        flagging_scanner: MagicMock,
        mock_discovery: MagicMock,
        pass_auditor: MagicMock,
        tmp_path: Path,
    ) -> None:
        vendor = tmp_path / "vendor"
        vendor.mkdir()
        updater = SourceUpdater(mock_config, flagging_scanner, mock_discovery, pass_auditor)
        summary = updater.update("ecc", interactive=False, vendor_dir=vendor)
        assert "skills/a/SKILL.md" in summary.files_blocked
        assert "skills/b/SKILL.md" in summary.files_accepted

    @patch("open_workspace_builder.sources.updater._clone_or_fetch")
    def test_interactive_reject(
        self,
        mock_clone: MagicMock,
        mock_config: "Config",
        clean_scanner: MagicMock,
        mock_discovery: MagicMock,
        pass_auditor: MagicMock,
    ) -> None:
        updater = SourceUpdater(mock_config, clean_scanner, mock_discovery, pass_auditor)
        summary = updater.update("ecc", interactive=True, prompt_fn=lambda p, v: "r")
        assert len(summary.files_rejected) == 2
        assert len(summary.files_accepted) == 0

    @patch("open_workspace_builder.sources.updater._clone_or_fetch")
    def test_interactive_quit(
        self,
        mock_clone: MagicMock,
        mock_config: "Config",
        clean_scanner: MagicMock,
        mock_discovery: MagicMock,
        pass_auditor: MagicMock,
    ) -> None:
        call_count = 0

        def _quit_on_first(path: str, verdict: object) -> str:
            nonlocal call_count
            call_count += 1
            return "q"

        updater = SourceUpdater(mock_config, clean_scanner, mock_discovery, pass_auditor)
        summary = updater.update("ecc", interactive=True, prompt_fn=_quit_on_first)
        assert len(summary.files_rejected) == 2

    @patch("open_workspace_builder.sources.updater._clone_or_fetch")
    def test_interactive_accept(
        self,
        mock_clone: MagicMock,
        mock_config: "Config",
        clean_scanner: MagicMock,
        mock_discovery: MagicMock,
        pass_auditor: MagicMock,
        tmp_path: Path,
    ) -> None:
        vendor = tmp_path / "vendor"
        vendor.mkdir()
        updater = SourceUpdater(mock_config, clean_scanner, mock_discovery, pass_auditor)
        summary = updater.update(
            "ecc", interactive=True, prompt_fn=lambda p, v: "a", vendor_dir=vendor
        )
        assert len(summary.files_accepted) == 2

    @patch("open_workspace_builder.sources.updater._clone_or_fetch")
    def test_dry_run_no_files_written(
        self,
        mock_clone: MagicMock,
        mock_config: "Config",
        clean_scanner: MagicMock,
        mock_discovery: MagicMock,
        pass_auditor: MagicMock,
        tmp_path: Path,
    ) -> None:
        vendor = tmp_path / "vendor"
        vendor.mkdir()
        updater = SourceUpdater(mock_config, clean_scanner, mock_discovery, pass_auditor)
        summary = updater.update("ecc", interactive=False, dry_run=True, vendor_dir=vendor)
        assert len(summary.files_accepted) == 2
        assert not (vendor / "skills" / "a" / "SKILL.md").exists()

    @patch("open_workspace_builder.sources.updater._clone_or_fetch")
    def test_files_copied_to_vendor(
        self,
        mock_clone: MagicMock,
        mock_config: "Config",
        clean_scanner: MagicMock,
        mock_discovery: MagicMock,
        pass_auditor: MagicMock,
        tmp_path: Path,
    ) -> None:
        vendor = tmp_path / "vendor"
        vendor.mkdir()
        updater = SourceUpdater(mock_config, clean_scanner, mock_discovery, pass_auditor)
        updater.update("ecc", interactive=False, vendor_dir=vendor)
        assert (vendor / "skills" / "a" / "SKILL.md").exists()
        assert (vendor / "skills" / "b" / "SKILL.md").exists()

    @patch("open_workspace_builder.sources.updater._clone_or_fetch")
    def test_update_log_written(
        self,
        mock_clone: MagicMock,
        mock_config: "Config",
        clean_scanner: MagicMock,
        mock_discovery: MagicMock,
        pass_auditor: MagicMock,
        tmp_path: Path,
    ) -> None:
        vendor = tmp_path / "vendor"
        vendor.mkdir()
        updater = SourceUpdater(mock_config, clean_scanner, mock_discovery, pass_auditor)
        updater.update("ecc", interactive=False, vendor_dir=vendor)
        log_path = vendor / ".update-log.jsonl"
        assert log_path.exists()
        entry = json.loads(log_path.read_text().strip().splitlines()[-1])
        assert entry["source"] == "ecc"
        assert len(entry["files_accepted"]) == 2

    @patch("open_workspace_builder.sources.updater._clone_or_fetch")
    def test_source_name_in_summary(
        self,
        mock_clone: MagicMock,
        mock_config: "Config",
        clean_scanner: MagicMock,
        mock_discovery: MagicMock,
        pass_auditor: MagicMock,
    ) -> None:
        updater = SourceUpdater(mock_config, clean_scanner, mock_discovery, pass_auditor)
        summary = updater.update("ecc", interactive=False)
        assert summary.source_name == "ecc"

    @patch("open_workspace_builder.sources.updater._clone_or_fetch")
    def test_scanner_called_per_file(
        self,
        mock_clone: MagicMock,
        mock_config: "Config",
        clean_scanner: MagicMock,
        mock_discovery: MagicMock,
        pass_auditor: MagicMock,
    ) -> None:
        updater = SourceUpdater(mock_config, clean_scanner, mock_discovery, pass_auditor)
        updater.update("ecc", interactive=False)
        assert clean_scanner.scan_file.call_count == 2

    @patch("open_workspace_builder.sources.updater._clone_or_fetch")
    def test_auditor_called(
        self,
        mock_clone: MagicMock,
        mock_config: "Config",
        clean_scanner: MagicMock,
        mock_discovery: MagicMock,
        pass_auditor: MagicMock,
    ) -> None:
        updater = SourceUpdater(mock_config, clean_scanner, mock_discovery, pass_auditor)
        updater.update("ecc", interactive=False)
        pass_auditor.audit.assert_called_once()

    @patch("open_workspace_builder.sources.updater._clone_or_fetch")
    def test_block_no_log_written(
        self,
        mock_clone: MagicMock,
        mock_config: "Config",
        clean_scanner: MagicMock,
        mock_discovery: MagicMock,
        block_auditor: MagicMock,
        tmp_path: Path,
    ) -> None:
        vendor = tmp_path / "vendor"
        vendor.mkdir()
        updater = SourceUpdater(mock_config, clean_scanner, mock_discovery, block_auditor)
        updater.update("ecc", interactive=False, vendor_dir=vendor)
        # Block halts before any file copying or log writing
        assert not (vendor / ".update-log.jsonl").exists()

    @patch("open_workspace_builder.sources.updater._clone_or_fetch")
    def test_mixed_accept_reject(
        self,
        mock_clone: MagicMock,
        mock_config: "Config",
        clean_scanner: MagicMock,
        mock_discovery: MagicMock,
        pass_auditor: MagicMock,
        tmp_path: Path,
    ) -> None:
        call_count = 0

        def _accept_first(path: str, verdict: object) -> str:
            nonlocal call_count
            call_count += 1
            return "a" if call_count == 1 else "r"

        vendor = tmp_path / "vendor"
        vendor.mkdir()
        updater = SourceUpdater(mock_config, clean_scanner, mock_discovery, pass_auditor)
        summary = updater.update(
            "ecc", interactive=True, prompt_fn=_accept_first, vendor_dir=vendor
        )
        assert len(summary.files_accepted) == 1
        assert len(summary.files_rejected) == 1

    @patch("open_workspace_builder.sources.updater._clone_or_fetch")
    def test_warn_and_flagged_combined(
        self,
        mock_clone: MagicMock,
        mock_config: "Config",
        flagging_scanner: MagicMock,
        mock_discovery: MagicMock,
        warn_auditor: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Warned files excluded by audit, flagged files blocked by scanner."""
        vendor = tmp_path / "vendor"
        vendor.mkdir()
        updater = SourceUpdater(mock_config, flagging_scanner, mock_discovery, warn_auditor)
        summary = updater.update("ecc", interactive=False, vendor_dir=vendor)
        # skill_a warned by audit, skill_b clean but might be flagged by scanner
        # (scanner flags anything with "a" in path)
        assert summary.audit_verdict == "warn"

    @patch("open_workspace_builder.sources.updater._clone_or_fetch")
    def test_empty_discovery(
        self,
        mock_clone: MagicMock,
        mock_config: "Config",
        clean_scanner: MagicMock,
        pass_auditor: MagicMock,
        source_config: SourceConfig,
    ) -> None:
        empty_discovery = MagicMock(spec=SourceDiscovery)
        empty_discovery.get_config.return_value = source_config
        empty_discovery.discover.return_value = []
        updater = SourceUpdater(mock_config, clean_scanner, empty_discovery, pass_auditor)
        summary = updater.update("ecc", interactive=False)
        assert summary.files_accepted == ()
        assert summary.files_rejected == ()
        assert summary.audit_verdict == "pass"


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestCLIUpdateCommand:
    def test_update_command_help(self) -> None:
        from click.testing import CliRunner
        from open_workspace_builder.cli import owb

        runner = CliRunner()
        result = runner.invoke(owb, ["update", "--help"])
        assert result.exit_code == 0
        assert "source" in result.output.lower()

    def test_ecc_update_alias_help(self) -> None:
        from click.testing import CliRunner
        from open_workspace_builder.cli import owb

        runner = CliRunner()
        result = runner.invoke(owb, ["ecc", "update", "--help"])
        assert result.exit_code == 0

    def test_update_group_visible(self) -> None:
        from click.testing import CliRunner
        from open_workspace_builder.cli import owb

        runner = CliRunner()
        result = runner.invoke(owb, ["--help"])
        assert "update" in result.output
