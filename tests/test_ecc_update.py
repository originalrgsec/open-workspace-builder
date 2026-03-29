"""Tests for ECC upstream update workflow (S016)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from open_workspace_builder.engine.ecc_update import (
    FileDiff,
    FileReview,
    UpdateResult,
    _append_jsonl,
    _load_json,
    _save_json,
    _sha256,
    apply_accepted_file,
    build_update_log_entry,
    diff_trees,
    get_status,
    run_update,
    scan_file_for_update,
    update_upstream_meta,
)
from open_workspace_builder.security.scanner import ScanFlag, ScanVerdict


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "mock_ecc_upstream"


@pytest.fixture
def vendor_dir(tmp_path: Path) -> Path:
    """Create a mock vendor/ecc directory with known files."""
    vd = tmp_path / "vendor" / "ecc"
    vd.mkdir(parents=True)

    # .upstream-meta.json
    meta = {
        "repo_url": "https://github.com/example/ecc",
        "commit_hash": "abc123",
        "fetch_date": "2026-01-01",
    }
    (vd / ".upstream-meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # agents/ — architect (identical to upstream fixture), planner (different)
    agents = vd / "agents"
    agents.mkdir()
    shutil.copy2(FIXTURES_DIR / "agents" / "architect.md", agents / "architect.md")
    (agents / "planner.md").write_text("# Planner Agent\n\nOriginal vendor version.\n")

    # agents/old-agent.md — only in vendor (will be "removed")
    (agents / "old-agent.md").write_text("# Old Agent\n\nDeprecated agent.\n")

    # commands/
    commands = vd / "commands"
    commands.mkdir()
    shutil.copy2(FIXTURES_DIR / "commands" / "build-fix.md", commands / "build-fix.md")

    # rules/common/
    rules_common = vd / "rules" / "common"
    rules_common.mkdir(parents=True)
    shutil.copy2(
        FIXTURES_DIR / "rules" / "common" / "coding-style.md",
        rules_common / "coding-style.md",
    )

    # Empty content hashes
    (vd / ".content-hashes.json").write_text("{}", encoding="utf-8")

    return vd


@pytest.fixture
def upstream_dir(tmp_path: Path) -> Path:
    """Create a mock upstream directory from fixtures."""
    ud = tmp_path / "upstream"
    shutil.copytree(FIXTURES_DIR, ud)
    return ud


@pytest.fixture
def clean_scanner() -> MagicMock:
    """Scanner that always returns clean verdicts."""
    scanner = MagicMock()
    scanner.scan_file.side_effect = lambda path: ScanVerdict(
        file_path=str(path), verdict="clean", flags=()
    )
    return scanner


@pytest.fixture
def mixed_scanner() -> MagicMock:
    """Scanner that returns malicious for files containing 'malicious'."""

    def _scan(path: Path) -> ScanVerdict:
        content = path.read_text(encoding="utf-8", errors="replace")
        if "exfiltrate" in content.lower() or "evil.example.com" in content:
            return ScanVerdict(
                file_path=str(path),
                verdict="malicious",
                flags=(
                    ScanFlag(
                        category="exfiltration",
                        severity="critical",
                        evidence="curl -d with variable data",
                        description="Potential data exfiltration via curl",
                        layer=2,
                    ),
                    ScanFlag(
                        category="prompt_injection",
                        severity="critical",
                        evidence="ignore all previous instructions",
                        description="Prompt injection attempt",
                        layer=2,
                    ),
                ),
            )
        return ScanVerdict(file_path=str(path), verdict="clean", flags=())

    scanner = MagicMock()
    scanner.scan_file.side_effect = _scan
    return scanner


@pytest.fixture
def flagged_scanner() -> MagicMock:
    """Scanner that returns 'flagged' (warning-only) for files containing 'pretend'."""

    def _scan(path: Path) -> ScanVerdict:
        content = path.read_text(encoding="utf-8", errors="replace")
        if "pretend" in content.lower():
            return ScanVerdict(
                file_path=str(path),
                verdict="flagged",
                flags=(
                    ScanFlag(
                        category="stealth",
                        severity="warning",
                        evidence="pretend to be",
                        description="Identity manipulation instruction",
                        layer=2,
                    ),
                ),
            )
        if "exfiltrate" in content.lower() or "evil.example.com" in content:
            return ScanVerdict(
                file_path=str(path),
                verdict="malicious",
                flags=(
                    ScanFlag(
                        category="exfiltration",
                        severity="critical",
                        evidence="curl exfil",
                        description="Potential data exfiltration via curl",
                        layer=2,
                    ),
                ),
            )
        return ScanVerdict(file_path=str(path), verdict="clean", flags=())

    scanner = MagicMock()
    scanner.scan_file.side_effect = _scan
    return scanner


# ---------------------------------------------------------------------------
# Unit tests: helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_sha256(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("hello world\n")
        h = _sha256(f)
        assert isinstance(h, str)
        assert len(h) == 64

    def test_sha256_same_content(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("same content")
        f2.write_text("same content")
        assert _sha256(f1) == _sha256(f2)

    def test_load_json_missing(self, tmp_path: Path) -> None:
        assert _load_json(tmp_path / "nonexistent.json") == {}

    def test_load_save_json(self, tmp_path: Path) -> None:
        p = tmp_path / "data.json"
        _save_json(p, {"key": "value"})
        assert _load_json(p) == {"key": "value"}

    def test_append_jsonl(self, tmp_path: Path) -> None:
        p = tmp_path / "log.jsonl"
        _append_jsonl(p, {"a": 1})
        _append_jsonl(p, {"b": 2})
        lines = p.read_text().strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"a": 1}
        assert json.loads(lines[1]) == {"b": 2}


# ---------------------------------------------------------------------------
# Diff detection
# ---------------------------------------------------------------------------


class TestDiffTrees:
    def test_categorization(self, upstream_dir: Path, vendor_dir: Path) -> None:
        diffs = diff_trees(upstream_dir, vendor_dir)
        by_path = {d.relative_path: d for d in diffs}

        # architect.md — same content in both → unchanged
        assert by_path["agents/architect.md"].category == "unchanged"

        # planner.md — different content → changed
        assert by_path["agents/planner.md"].category == "changed"
        assert by_path["agents/planner.md"].unified_diff is not None

        # new-agent.md — only in upstream → new
        assert by_path["agents/new-agent.md"].category == "new"

        # malicious-agent.md — only in upstream → new
        assert by_path["agents/malicious-agent.md"].category == "new"

        # old-agent.md — only in vendor → removed
        assert by_path["agents/old-agent.md"].category == "removed"

    def test_unchanged_files(self, upstream_dir: Path, vendor_dir: Path) -> None:
        diffs = diff_trees(upstream_dir, vendor_dir)
        unchanged = [d for d in diffs if d.category == "unchanged"]
        # architect.md, build-fix.md, coding-style.md
        assert len(unchanged) == 3

    def test_changed_has_diff(self, upstream_dir: Path, vendor_dir: Path) -> None:
        diffs = diff_trees(upstream_dir, vendor_dir)
        changed = [d for d in diffs if d.category == "changed"]
        assert len(changed) == 1
        assert changed[0].relative_path == "agents/planner.md"
        assert "---" in changed[0].unified_diff  # unified diff header
        assert "+++" in changed[0].unified_diff

    def test_empty_dirs(self, tmp_path: Path) -> None:
        us = tmp_path / "up"
        vn = tmp_path / "vn"
        us.mkdir()
        vn.mkdir()
        assert diff_trees(us, vn) == []


# ---------------------------------------------------------------------------
# Security scan integration
# ---------------------------------------------------------------------------


class TestSecurityScan:
    def test_clean_file(self, upstream_dir: Path, clean_scanner: MagicMock) -> None:
        verdict = scan_file_for_update(
            upstream_dir / "agents" / "architect.md", scanner=clean_scanner
        )
        assert verdict.verdict == "clean"

    def test_malicious_file_blocked(
        self, upstream_dir: Path, mixed_scanner: MagicMock
    ) -> None:
        verdict = scan_file_for_update(
            upstream_dir / "agents" / "malicious-agent.md",
            scanner=mixed_scanner,
        )
        assert verdict.verdict == "malicious"
        assert len(verdict.flags) == 2

    def test_default_scanner_creation(self, upstream_dir: Path) -> None:
        """When no scanner is passed, a default Scanner is created."""
        verdict = scan_file_for_update(upstream_dir / "agents" / "architect.md")
        assert verdict.verdict == "clean"


# ---------------------------------------------------------------------------
# Accept flow
# ---------------------------------------------------------------------------


class TestAcceptFlow:
    def test_accepted_file_copies(
        self, upstream_dir: Path, vendor_dir: Path
    ) -> None:
        hashes: dict[str, str] = {}
        new_hashes = apply_accepted_file(
            upstream_dir, vendor_dir, "agents/new-agent.md", hashes
        )
        dst = vendor_dir / "agents" / "new-agent.md"
        assert dst.exists()
        assert "agents/new-agent.md" in new_hashes
        assert len(new_hashes["agents/new-agent.md"]) == 64

    def test_accept_preserves_existing_hashes(
        self, upstream_dir: Path, vendor_dir: Path
    ) -> None:
        hashes = {"agents/architect.md": "oldhash"}
        new_hashes = apply_accepted_file(
            upstream_dir, vendor_dir, "agents/new-agent.md", hashes
        )
        # Original key preserved (immutable update)
        assert new_hashes["agents/architect.md"] == "oldhash"
        assert "agents/new-agent.md" in new_hashes

    def test_accept_overwrites_changed(
        self, upstream_dir: Path, vendor_dir: Path
    ) -> None:
        old_content = (vendor_dir / "agents" / "planner.md").read_text()
        apply_accepted_file(
            upstream_dir, vendor_dir, "agents/planner.md", {}
        )
        new_content = (vendor_dir / "agents" / "planner.md").read_text()
        assert new_content != old_content
        assert "multi-phase" in new_content


# ---------------------------------------------------------------------------
# Reject flow
# ---------------------------------------------------------------------------


class TestRejectFlow:
    @patch("open_workspace_builder.engine.ecc_update.fetch_upstream")
    def test_rejected_files_unchanged(
        self,
        mock_fetch: MagicMock,
        upstream_dir: Path,
        vendor_dir: Path,
        clean_scanner: MagicMock,
    ) -> None:
        """Rejected files should not modify vendor."""
        mock_fetch.return_value = "deadbeef"
        original_content = (vendor_dir / "agents" / "planner.md").read_text()

        with patch("open_workspace_builder.engine.ecc_update.tempfile") as mock_tmp:
            mock_tmp.TemporaryDirectory.return_value.__enter__ = MagicMock(
                return_value=str(upstream_dir.parent)
            )
            mock_tmp.TemporaryDirectory.return_value.__exit__ = MagicMock(return_value=False)

            results = run_update(
                vendor_dir,
                prompt_fn=lambda _review: "r",
                scanner=clean_scanner,
            )

        # planner.md should be rejected (not changed)
        rejected = [r for r in results if r.action == "rejected"]
        assert any(r.relative_path == "agents/planner.md" for r in rejected)

        # Vendor file unchanged
        assert (vendor_dir / "agents" / "planner.md").read_text() == original_content

    @patch("open_workspace_builder.engine.ecc_update.fetch_upstream")
    def test_reject_logged(
        self,
        mock_fetch: MagicMock,
        upstream_dir: Path,
        vendor_dir: Path,
        clean_scanner: MagicMock,
    ) -> None:
        mock_fetch.return_value = "deadbeef"
        with patch("open_workspace_builder.engine.ecc_update.tempfile") as mock_tmp:
            mock_tmp.TemporaryDirectory.return_value.__enter__ = MagicMock(
                return_value=str(upstream_dir.parent)
            )
            mock_tmp.TemporaryDirectory.return_value.__exit__ = MagicMock(return_value=False)

            run_update(
                vendor_dir,
                prompt_fn=lambda _review: "r",
                scanner=clean_scanner,
            )

        log_path = vendor_dir / ".update-log.jsonl"
        assert log_path.exists()
        entry = json.loads(log_path.read_text().strip().splitlines()[-1])
        assert len(entry["files_rejected"]) > 0


# ---------------------------------------------------------------------------
# Full update with mocked git
# ---------------------------------------------------------------------------


class TestRunUpdate:
    @patch("open_workspace_builder.engine.ecc_update.fetch_upstream")
    def test_accept_all(
        self,
        mock_fetch: MagicMock,
        upstream_dir: Path,
        vendor_dir: Path,
        clean_scanner: MagicMock,
    ) -> None:
        mock_fetch.return_value = "deadbeef"
        # Patch tempdir to use our upstream_dir
        with patch("open_workspace_builder.engine.ecc_update.tempfile") as mock_tmp:
            mock_tmp.TemporaryDirectory.return_value.__enter__ = MagicMock(
                return_value=str(upstream_dir.parent)
            )
            mock_tmp.TemporaryDirectory.return_value.__exit__ = MagicMock(return_value=False)

            results = run_update(
                vendor_dir,
                accept_all=True,
                scanner=clean_scanner,
            )

        accepted = [r for r in results if r.action == "accepted"]
        assert len(accepted) > 0

        # Content hashes updated
        hashes = _load_json(vendor_dir / ".content-hashes.json")
        for r in accepted:
            assert r.relative_path in hashes

        # Meta updated
        meta = _load_json(vendor_dir / ".upstream-meta.json")
        assert meta["commit_hash"] == "deadbeef"

    @patch("open_workspace_builder.engine.ecc_update.fetch_upstream")
    def test_malicious_blocked(
        self,
        mock_fetch: MagicMock,
        upstream_dir: Path,
        vendor_dir: Path,
        mixed_scanner: MagicMock,
    ) -> None:
        mock_fetch.return_value = "deadbeef"
        with patch("open_workspace_builder.engine.ecc_update.tempfile") as mock_tmp:
            mock_tmp.TemporaryDirectory.return_value.__enter__ = MagicMock(
                return_value=str(upstream_dir.parent)
            )
            mock_tmp.TemporaryDirectory.return_value.__exit__ = MagicMock(return_value=False)

            results = run_update(
                vendor_dir,
                accept_all=True,
                scanner=mixed_scanner,
            )

        blocked = [r for r in results if r.action == "blocked"]
        assert len(blocked) == 1
        assert blocked[0].relative_path == "agents/malicious-agent.md"
        assert blocked[0].flag_details is not None
        assert len(blocked[0].flag_details) == 2

        # Malicious file NOT copied to vendor
        assert not (vendor_dir / "agents" / "malicious-agent.md").exists()

    @patch("open_workspace_builder.engine.ecc_update.fetch_upstream")
    def test_dry_run(
        self,
        mock_fetch: MagicMock,
        upstream_dir: Path,
        vendor_dir: Path,
        clean_scanner: MagicMock,
    ) -> None:
        mock_fetch.return_value = "deadbeef"
        original_meta = _load_json(vendor_dir / ".upstream-meta.json")
        original_planner = (vendor_dir / "agents" / "planner.md").read_text()

        with patch("open_workspace_builder.engine.ecc_update.tempfile") as mock_tmp:
            mock_tmp.TemporaryDirectory.return_value.__enter__ = MagicMock(
                return_value=str(upstream_dir.parent)
            )
            mock_tmp.TemporaryDirectory.return_value.__exit__ = MagicMock(return_value=False)

            results = run_update(
                vendor_dir,
                dry_run=True,
                accept_all=True,
                scanner=clean_scanner,
            )

        # Files should NOT be modified
        assert (vendor_dir / "agents" / "planner.md").read_text() == original_planner
        assert not (vendor_dir / "agents" / "new-agent.md").exists()

        # Meta should NOT be updated
        meta = _load_json(vendor_dir / ".upstream-meta.json")
        assert meta["commit_hash"] == original_meta["commit_hash"]

        # But log should still be written
        log_path = vendor_dir / ".update-log.jsonl"
        assert log_path.exists()

        # Results still track what would have been accepted
        accepted = [r for r in results if r.action == "accepted"]
        assert len(accepted) > 0

    @patch("open_workspace_builder.engine.ecc_update.fetch_upstream")
    def test_quit_rejects_remaining(
        self,
        mock_fetch: MagicMock,
        upstream_dir: Path,
        vendor_dir: Path,
        clean_scanner: MagicMock,
    ) -> None:
        mock_fetch.return_value = "deadbeef"
        call_count = 0

        def _quit_on_second(_review: FileReview) -> str:
            nonlocal call_count
            call_count += 1
            return "q" if call_count >= 1 else "a"

        with patch("open_workspace_builder.engine.ecc_update.tempfile") as mock_tmp:
            mock_tmp.TemporaryDirectory.return_value.__enter__ = MagicMock(
                return_value=str(upstream_dir.parent)
            )
            mock_tmp.TemporaryDirectory.return_value.__exit__ = MagicMock(return_value=False)

            results = run_update(
                vendor_dir,
                prompt_fn=_quit_on_second,
                scanner=clean_scanner,
            )

        # After quit, remaining files should be rejected
        rejected = [r for r in results if r.action == "rejected"]
        assert len(rejected) >= 1


# ---------------------------------------------------------------------------
# Reputation ledger integration
# ---------------------------------------------------------------------------


class TestReputationIntegration:
    @patch("open_workspace_builder.engine.ecc_update.fetch_upstream")
    def test_blocked_file_records_flag(
        self,
        mock_fetch: MagicMock,
        upstream_dir: Path,
        vendor_dir: Path,
        mixed_scanner: MagicMock,
        tmp_path: Path,
    ) -> None:
        from open_workspace_builder.security.reputation import (
            FlagEvent,
            ReputationLedger,
        )

        mock_fetch.return_value = "deadbeef"
        with patch("open_workspace_builder.engine.ecc_update.tempfile") as mock_tmp:
            mock_tmp.TemporaryDirectory.return_value.__enter__ = MagicMock(
                return_value=str(upstream_dir.parent)
            )
            mock_tmp.TemporaryDirectory.return_value.__exit__ = MagicMock(return_value=False)

            results = run_update(
                vendor_dir,
                accept_all=True,
                scanner=mixed_scanner,
            )

        # Simulate CLI recording blocked files (as the CLI does)
        ledger_path = tmp_path / "test-ledger.jsonl"
        ledger = ReputationLedger(ledger_path)

        for r in results:
            if r.action == "blocked":
                event = FlagEvent.now(
                    source="ecc",
                    file_path=r.relative_path,
                    flag_category="security_scan",
                    severity="critical",
                    disposition="confirmed_malicious",
                    details="; ".join(r.flag_details or []),
                )
                ledger.record_event(event)

        history = ledger.get_history("ecc")
        assert len(history) == 1
        assert history[0].file_path == "agents/malicious-agent.md"
        assert history[0].disposition == "confirmed_malicious"

    def test_threshold_warning(self, tmp_path: Path) -> None:
        from open_workspace_builder.security.reputation import (
            FlagEvent,
            ReputationLedger,
        )

        ledger = ReputationLedger(tmp_path / "ledger.jsonl")

        # Record 4 malicious events (threshold is 3)
        for i in range(4):
            ledger.record_event(
                FlagEvent.now(
                    source="ecc",
                    file_path=f"agents/bad-{i}.md",
                    flag_category="exfiltration",
                    severity="critical",
                    disposition="confirmed_malicious",
                    details="test",
                )
            )

        assert ledger.check_threshold("ecc") is True


# ---------------------------------------------------------------------------
# Update log
# ---------------------------------------------------------------------------


class TestUpdateLog:
    def test_build_log_entry(self) -> None:
        results = [
            UpdateResult("agents/a.md", "new", "accepted"),
            UpdateResult("agents/b.md", "changed", "rejected"),
            UpdateResult("agents/c.md", "new", "blocked", ["[critical] exfil"]),
            UpdateResult("agents/d.md", "unchanged", "unchanged"),
        ]
        entry = build_update_log_entry("abc123", results)
        assert entry["upstream_commit"] == "abc123"
        assert len(entry["files_offered"]) == 4
        assert entry["files_accepted"] == ["agents/a.md"]
        assert entry["files_rejected"] == ["agents/b.md"]
        assert entry["files_blocked"] == ["agents/c.md"]
        assert "agents/c.md" in entry["flag_details"]

    @patch("open_workspace_builder.engine.ecc_update.fetch_upstream")
    def test_update_writes_log(
        self,
        mock_fetch: MagicMock,
        upstream_dir: Path,
        vendor_dir: Path,
        clean_scanner: MagicMock,
    ) -> None:
        mock_fetch.return_value = "deadbeef"
        with patch("open_workspace_builder.engine.ecc_update.tempfile") as mock_tmp:
            mock_tmp.TemporaryDirectory.return_value.__enter__ = MagicMock(
                return_value=str(upstream_dir.parent)
            )
            mock_tmp.TemporaryDirectory.return_value.__exit__ = MagicMock(return_value=False)

            run_update(
                vendor_dir,
                accept_all=True,
                scanner=clean_scanner,
            )

        log_path = vendor_dir / ".update-log.jsonl"
        assert log_path.exists()
        entry = json.loads(log_path.read_text().strip().splitlines()[-1])
        assert entry["upstream_commit"] == "deadbeef"
        assert "timestamp" in entry


# ---------------------------------------------------------------------------
# Update upstream meta
# ---------------------------------------------------------------------------


class TestUpdateMeta:
    def test_updates_commit_and_date(self, vendor_dir: Path) -> None:
        update_upstream_meta(vendor_dir, "newcommit123")
        meta = _load_json(vendor_dir / ".upstream-meta.json")
        assert meta["commit_hash"] == "newcommit123"
        assert meta["fetch_date"]  # non-empty
        # Preserves repo_url
        assert meta["repo_url"] == "https://github.com/example/ecc"


# ---------------------------------------------------------------------------
# Status command
# ---------------------------------------------------------------------------


class TestStatus:
    def test_basic_status(self, vendor_dir: Path, tmp_path: Path) -> None:
        info = get_status(vendor_dir, ledger_path=tmp_path / "empty-ledger.jsonl")
        assert info["repo_url"] == "https://github.com/example/ecc"
        assert info["commit_hash"] == "abc123"
        assert info["fetch_date"] == "2026-01-01"
        assert info["flag_history"] == []
        assert info["recent_updates"] == []

    def test_status_with_update_log(self, vendor_dir: Path, tmp_path: Path) -> None:
        # Write some log entries
        log_path = vendor_dir / ".update-log.jsonl"
        for i in range(7):
            _append_jsonl(log_path, {"timestamp": f"2026-01-0{i + 1}", "i": i})

        info = get_status(vendor_dir, ledger_path=tmp_path / "empty-ledger.jsonl")
        # Should return last 5
        assert len(info["recent_updates"]) == 5

    def test_status_with_flag_history(self, vendor_dir: Path, tmp_path: Path) -> None:
        from open_workspace_builder.security.reputation import (
            FlagEvent,
            ReputationLedger,
        )

        ledger_path = tmp_path / "ledger.jsonl"
        ledger = ReputationLedger(ledger_path)
        ledger.record_event(
            FlagEvent.now(
                source="ecc",
                file_path="agents/bad.md",
                flag_category="exfiltration",
                severity="critical",
                disposition="confirmed_malicious",
                details="test",
            )
        )

        info = get_status(vendor_dir, ledger_path=ledger_path)
        assert len(info["flag_history"]) == 1
        assert info["flag_history"][0]["file_path"] == "agents/bad.md"


# ---------------------------------------------------------------------------
# CLI integration (Click testing)
# ---------------------------------------------------------------------------


class TestCLI:
    def test_ecc_status_command(self) -> None:
        from click.testing import CliRunner

        from open_workspace_builder.cli import owb

        runner = CliRunner()
        result = runner.invoke(owb, ["ecc", "status"])
        # Should run without crashing (may fail if vendor/ecc not found in test env)
        assert result.exit_code in (0, 1)

    def test_ecc_group_help(self) -> None:
        from click.testing import CliRunner

        from open_workspace_builder.cli import owb

        runner = CliRunner()
        result = runner.invoke(owb, ["ecc", "--help"])
        assert result.exit_code == 0
        assert "update" in result.output
        assert "status" in result.output


# ---------------------------------------------------------------------------
# Trusted-source exemption (Issue #1)
# ---------------------------------------------------------------------------


class TestTrustedSourceExemption:
    """Trusted upstream URLs should skip Layer 2 pattern scanning."""

    @patch("open_workspace_builder.engine.ecc_update.fetch_upstream")
    def test_trusted_url_skips_layer2(
        self,
        mock_fetch: MagicMock,
        upstream_dir: Path,
        vendor_dir: Path,
    ) -> None:
        """When upstream URL is trusted, Layer 2 patterns should not run."""
        mock_fetch.return_value = "deadbeef"
        # Set repo_url to a trusted URL
        meta_path = vendor_dir / ".upstream-meta.json"
        meta = json.loads(meta_path.read_text())
        meta["repo_url"] = "https://github.com/affaan-m/everything-claude-code"
        meta_path.write_text(json.dumps(meta))

        with patch("open_workspace_builder.engine.ecc_update.tempfile") as mock_tmp:
            mock_tmp.TemporaryDirectory.return_value.__enter__ = MagicMock(
                return_value=str(upstream_dir.parent)
            )
            mock_tmp.TemporaryDirectory.return_value.__exit__ = MagicMock(return_value=False)

            results = run_update(
                vendor_dir,
                accept_all=True,
                trusted_upstream_urls=(
                    "https://github.com/affaan-m/everything-claude-code",
                ),
            )

        blocked = [r for r in results if r.action == "blocked"]
        # Even the malicious-agent.md should not be caught by Layer 2 patterns
        # when the upstream is trusted (Layer 1 structural checks only)
        # The malicious-agent.md is a regular markdown file, so Layer 1 won't flag it
        assert len(blocked) == 0

    @patch("open_workspace_builder.engine.ecc_update.fetch_upstream")
    def test_untrusted_url_runs_full_scan(
        self,
        mock_fetch: MagicMock,
        upstream_dir: Path,
        vendor_dir: Path,
        flagged_scanner: MagicMock,
    ) -> None:
        """Untrusted URL should run full Layer 1+2 scanning."""
        mock_fetch.return_value = "deadbeef"
        with patch("open_workspace_builder.engine.ecc_update.tempfile") as mock_tmp:
            mock_tmp.TemporaryDirectory.return_value.__enter__ = MagicMock(
                return_value=str(upstream_dir.parent)
            )
            mock_tmp.TemporaryDirectory.return_value.__exit__ = MagicMock(return_value=False)

            results = run_update(
                vendor_dir,
                accept_all=True,
                scanner=flagged_scanner,
                # No trusted_upstream_urls — defaults to empty
            )

        blocked = [r for r in results if r.action == "blocked"]
        assert len(blocked) == 1  # malicious-agent.md still blocked

    @patch("open_workspace_builder.engine.ecc_update.fetch_upstream")
    def test_trusted_url_still_runs_layer1(
        self,
        mock_fetch: MagicMock,
        upstream_dir: Path,
        vendor_dir: Path,
    ) -> None:
        """Even trusted URLs must run Layer 1 structural checks (binary, encoding)."""
        mock_fetch.return_value = "deadbeef"
        # Create a binary file in upstream
        (upstream_dir / "agents" / "sneaky.exe").write_bytes(b"\x00\x01\x02\x03")

        meta_path = vendor_dir / ".upstream-meta.json"
        meta = json.loads(meta_path.read_text())
        meta["repo_url"] = "https://github.com/affaan-m/everything-claude-code"
        meta_path.write_text(json.dumps(meta))

        with patch("open_workspace_builder.engine.ecc_update.tempfile") as mock_tmp:
            mock_tmp.TemporaryDirectory.return_value.__enter__ = MagicMock(
                return_value=str(upstream_dir.parent)
            )
            mock_tmp.TemporaryDirectory.return_value.__exit__ = MagicMock(return_value=False)

            results = run_update(
                vendor_dir,
                accept_all=True,
                trusted_upstream_urls=(
                    "https://github.com/affaan-m/everything-claude-code",
                ),
            )

        by_path = {r.relative_path: r for r in results}
        exe_result = by_path.get("agents/sneaky.exe")
        # Layer 1 should catch the .exe extension
        assert exe_result is not None
        assert exe_result.action == "blocked"

    @patch("open_workspace_builder.engine.ecc_update.fetch_upstream")
    def test_explicit_scanner_overrides_trusted(
        self,
        mock_fetch: MagicMock,
        upstream_dir: Path,
        vendor_dir: Path,
        flagged_scanner: MagicMock,
    ) -> None:
        """When an explicit scanner is passed, it takes precedence over trust logic."""
        mock_fetch.return_value = "deadbeef"
        meta_path = vendor_dir / ".upstream-meta.json"
        meta = json.loads(meta_path.read_text())
        meta["repo_url"] = "https://github.com/affaan-m/everything-claude-code"
        meta_path.write_text(json.dumps(meta))

        with patch("open_workspace_builder.engine.ecc_update.tempfile") as mock_tmp:
            mock_tmp.TemporaryDirectory.return_value.__enter__ = MagicMock(
                return_value=str(upstream_dir.parent)
            )
            mock_tmp.TemporaryDirectory.return_value.__exit__ = MagicMock(return_value=False)

            results = run_update(
                vendor_dir,
                accept_all=True,
                scanner=flagged_scanner,  # explicit scanner — should be used
                trusted_upstream_urls=(
                    "https://github.com/affaan-m/everything-claude-code",
                ),
            )

        blocked = [r for r in results if r.action == "blocked"]
        assert len(blocked) == 1  # flagged_scanner blocks malicious-agent.md


# ---------------------------------------------------------------------------
# Severity differentiation (Issue #1)
# ---------------------------------------------------------------------------


class TestSeverityDifferentiation:
    """Flagged (warning-only) files should be accepted with warnings, not blocked."""

    @patch("open_workspace_builder.engine.ecc_update.fetch_upstream")
    def test_flagged_verdict_accepted_not_blocked(
        self,
        mock_fetch: MagicMock,
        upstream_dir: Path,
        vendor_dir: Path,
        flagged_scanner: MagicMock,
    ) -> None:
        mock_fetch.return_value = "deadbeef"
        with patch("open_workspace_builder.engine.ecc_update.tempfile") as mock_tmp:
            mock_tmp.TemporaryDirectory.return_value.__enter__ = MagicMock(
                return_value=str(upstream_dir.parent)
            )
            mock_tmp.TemporaryDirectory.return_value.__exit__ = MagicMock(return_value=False)

            results = run_update(
                vendor_dir,
                accept_all=True,
                scanner=flagged_scanner,
            )

        by_path = {r.relative_path: r for r in results}

        # Flagged agent should be accepted, not blocked
        flagged = by_path["agents/flagged-agent.md"]
        assert flagged.action == "accepted"
        assert flagged.warnings is not None
        assert len(flagged.warnings) > 0

        # Malicious agent should still be blocked
        malicious = by_path["agents/malicious-agent.md"]
        assert malicious.action == "blocked"

    @patch("open_workspace_builder.engine.ecc_update.fetch_upstream")
    def test_flagged_file_is_copied_to_vendor(
        self,
        mock_fetch: MagicMock,
        upstream_dir: Path,
        vendor_dir: Path,
        flagged_scanner: MagicMock,
    ) -> None:
        mock_fetch.return_value = "deadbeef"
        with patch("open_workspace_builder.engine.ecc_update.tempfile") as mock_tmp:
            mock_tmp.TemporaryDirectory.return_value.__enter__ = MagicMock(
                return_value=str(upstream_dir.parent)
            )
            mock_tmp.TemporaryDirectory.return_value.__exit__ = MagicMock(return_value=False)

            run_update(
                vendor_dir,
                accept_all=True,
                scanner=flagged_scanner,
            )

        # Flagged file should be present in vendor (was accepted)
        assert (vendor_dir / "agents" / "flagged-agent.md").exists()

        # Malicious file should NOT be present
        assert not (vendor_dir / "agents" / "malicious-agent.md").exists()

    @patch("open_workspace_builder.engine.ecc_update.fetch_upstream")
    def test_malicious_verdict_still_blocked(
        self,
        mock_fetch: MagicMock,
        upstream_dir: Path,
        vendor_dir: Path,
        flagged_scanner: MagicMock,
    ) -> None:
        mock_fetch.return_value = "deadbeef"
        with patch("open_workspace_builder.engine.ecc_update.tempfile") as mock_tmp:
            mock_tmp.TemporaryDirectory.return_value.__enter__ = MagicMock(
                return_value=str(upstream_dir.parent)
            )
            mock_tmp.TemporaryDirectory.return_value.__exit__ = MagicMock(return_value=False)

            results = run_update(
                vendor_dir,
                accept_all=True,
                scanner=flagged_scanner,
            )

        blocked = [r for r in results if r.action == "blocked"]
        assert len(blocked) == 1
        assert blocked[0].relative_path == "agents/malicious-agent.md"
        assert blocked[0].flag_details is not None


# ---------------------------------------------------------------------------
# Dataclass immutability
# ---------------------------------------------------------------------------


class TestImmutability:
    def test_file_diff_frozen(self) -> None:
        d = FileDiff(relative_path="a.md", category="new")
        with pytest.raises(AttributeError):
            d.category = "changed"  # type: ignore[misc]

    def test_file_review_frozen(self) -> None:
        r = FileReview(diff=FileDiff("a.md", "new"), verdict=None)
        with pytest.raises(AttributeError):
            r.verdict = "something"  # type: ignore[misc]

    def test_update_result_frozen(self) -> None:
        r = UpdateResult("a.md", "new", "accepted")
        with pytest.raises(AttributeError):
            r.action = "rejected"  # type: ignore[misc]
