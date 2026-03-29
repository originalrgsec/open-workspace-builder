"""Tests for S013 — Reputation ledger."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from open_workspace_builder.security.reputation import FlagEvent, ReputationLedger


class TestFlagEvent:
    """Tests for FlagEvent dataclass."""

    def test_create_with_now(self) -> None:
        event = FlagEvent.now(
            source="test-repo",
            file_path="/tmp/bad.md",
            flag_category="exfiltration",
            severity="critical",
            disposition="confirmed_malicious",
            details="Found curl exfil",
        )
        assert event.source == "test-repo"
        assert event.severity == "critical"
        assert event.timestamp  # Non-empty

    def test_frozen(self) -> None:
        event = FlagEvent.now(
            source="s", file_path="f", flag_category="c",
            severity="w", disposition="d", details="x",
        )
        with pytest.raises(AttributeError):
            event.source = "changed"  # type: ignore[misc]


class TestReputationLedger:
    """Tests for ReputationLedger."""

    def test_creates_file_with_restricted_permissions(self, tmp_path: Path) -> None:
        ledger_path = tmp_path / "test-ledger.jsonl"
        ReputationLedger(ledger_path)
        assert ledger_path.exists()
        mode = stat.S_IMODE(os.stat(ledger_path).st_mode)
        assert mode == 0o600

    def test_record_and_read_event(self, tmp_path: Path) -> None:
        ledger = ReputationLedger(tmp_path / "ledger.jsonl")
        event = FlagEvent.now(
            source="repo-a",
            file_path="/tmp/file.md",
            flag_category="persistence",
            severity="critical",
            disposition="confirmed_malicious",
            details="crontab modification",
        )
        ledger.record_event(event)
        history = ledger.get_history("repo-a")
        assert len(history) == 1
        assert history[0].source == "repo-a"
        assert history[0].disposition == "confirmed_malicious"

    def test_append_only(self, tmp_path: Path) -> None:
        ledger = ReputationLedger(tmp_path / "ledger.jsonl")
        for i in range(3):
            ledger.record_event(FlagEvent.now(
                source="repo-b", file_path=f"/tmp/{i}.md",
                flag_category="test", severity="warning",
                disposition="unreviewed", details=f"event {i}",
            ))
        history = ledger.get_history("repo-b")
        assert len(history) == 3

    def test_check_threshold_below(self, tmp_path: Path) -> None:
        ledger = ReputationLedger(tmp_path / "ledger.jsonl")
        for i in range(2):
            ledger.record_event(FlagEvent.now(
                source="repo-c", file_path=f"/tmp/{i}.md",
                flag_category="test", severity="critical",
                disposition="confirmed_malicious", details="bad",
            ))
        assert ledger.check_threshold("repo-c", threshold=3) is False

    def test_check_threshold_exceeded(self, tmp_path: Path) -> None:
        ledger = ReputationLedger(tmp_path / "ledger.jsonl")
        for i in range(5):
            ledger.record_event(FlagEvent.now(
                source="repo-d", file_path=f"/tmp/{i}.md",
                flag_category="test", severity="critical",
                disposition="confirmed_malicious", details="bad",
            ))
        assert ledger.check_threshold("repo-d", threshold=3) is True

    def test_threshold_ignores_other_dispositions(self, tmp_path: Path) -> None:
        ledger = ReputationLedger(tmp_path / "ledger.jsonl")
        for i in range(5):
            ledger.record_event(FlagEvent.now(
                source="repo-e", file_path=f"/tmp/{i}.md",
                flag_category="test", severity="critical",
                disposition="false_positive", details="not bad",
            ))
        assert ledger.check_threshold("repo-e", threshold=3) is False

    def test_get_history_filters_by_source(self, tmp_path: Path) -> None:
        ledger = ReputationLedger(tmp_path / "ledger.jsonl")
        ledger.record_event(FlagEvent.now(
            source="repo-f", file_path="/a.md",
            flag_category="t", severity="w",
            disposition="unreviewed", details="x",
        ))
        ledger.record_event(FlagEvent.now(
            source="repo-g", file_path="/b.md",
            flag_category="t", severity="w",
            disposition="unreviewed", details="y",
        ))
        assert len(ledger.get_history("repo-f")) == 1
        assert len(ledger.get_history("repo-g")) == 1
        assert len(ledger.get_history("repo-h")) == 0

    def test_malformed_line_skipped(self, tmp_path: Path) -> None:
        ledger_path = tmp_path / "ledger.jsonl"
        ledger_path.write_text("not valid json\n", encoding="utf-8")
        os.chmod(ledger_path, 0o600)
        ledger = ReputationLedger(ledger_path)
        assert ledger.get_history("any") == []

    def test_dedup_same_source_file_updates_not_appends(self, tmp_path: Path) -> None:
        """Recording twice for the same (source, file_path) should upsert, not append."""
        ledger = ReputationLedger(tmp_path / "ledger.jsonl")
        ledger.record_event(FlagEvent.now(
            source="ecc", file_path="agents/a.md",
            flag_category="test", severity="warning",
            disposition="flagged", details="first run",
        ))
        ledger.record_event(FlagEvent.now(
            source="ecc", file_path="agents/a.md",
            flag_category="test", severity="critical",
            disposition="confirmed_malicious", details="second run",
        ))
        history = ledger.get_history("ecc")
        assert len(history) == 1
        assert history[0].severity == "critical"
        assert history[0].details == "second run"

    def test_dedup_different_files_both_kept(self, tmp_path: Path) -> None:
        """Different file_paths under the same source should both be kept."""
        ledger = ReputationLedger(tmp_path / "ledger.jsonl")
        ledger.record_event(FlagEvent.now(
            source="ecc", file_path="agents/a.md",
            flag_category="test", severity="critical",
            disposition="confirmed_malicious", details="file a",
        ))
        ledger.record_event(FlagEvent.now(
            source="ecc", file_path="agents/b.md",
            flag_category="test", severity="critical",
            disposition="confirmed_malicious", details="file b",
        ))
        history = ledger.get_history("ecc")
        assert len(history) == 2

    def test_threshold_counts_distinct_files(self, tmp_path: Path) -> None:
        """Threshold should count distinct files, not accumulated repeat entries."""
        ledger = ReputationLedger(tmp_path / "ledger.jsonl")
        # Record 5 events for the SAME file — should count as 1 distinct file
        for i in range(5):
            ledger.record_event(FlagEvent.now(
                source="ecc", file_path="agents/same.md",
                flag_category="test", severity="critical",
                disposition="confirmed_malicious", details=f"run {i}",
            ))
        assert ledger.check_threshold("ecc", threshold=1) is False  # 1 file, not > 1

        # Now add 3 more distinct files to reach 4 distinct files total
        for name in ("b.md", "c.md", "d.md"):
            ledger.record_event(FlagEvent.now(
                source="ecc", file_path=f"agents/{name}",
                flag_category="test", severity="critical",
                disposition="confirmed_malicious", details="distinct",
            ))
        assert ledger.check_threshold("ecc", threshold=3) is True  # 4 > 3

    def test_dedup_across_different_sources(self, tmp_path: Path) -> None:
        """Dedup is scoped to (source, file_path) — same file under different sources kept."""
        ledger = ReputationLedger(tmp_path / "ledger.jsonl")
        ledger.record_event(FlagEvent.now(
            source="ecc", file_path="agents/a.md",
            flag_category="test", severity="critical",
            disposition="confirmed_malicious", details="ecc source",
        ))
        ledger.record_event(FlagEvent.now(
            source="other", file_path="agents/a.md",
            flag_category="test", severity="critical",
            disposition="confirmed_malicious", details="other source",
        ))
        assert len(ledger.get_history("ecc")) == 1
        assert len(ledger.get_history("other")) == 1
