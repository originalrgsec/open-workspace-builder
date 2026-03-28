"""Tests for local cost ledger — append-only JSONL session cost records."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from open_workspace_builder.tokens.models import LedgerEntry, TokenCost


class TestLedgerEntry:
    """LedgerEntry is a frozen dataclass holding one session's cost record."""

    def test_create_entry(self) -> None:
        entry = LedgerEntry(
            session_id="abc-123",
            project="open-workspace-builder",
            timestamp="2026-03-28T10:00:00.000Z",
            total_input=1000,
            total_output=5000,
            total_cache_creation=2000,
            total_cache_read=10000,
            cost=TokenCost(
                input_cost=0.005,
                output_cost=0.125,
                cache_write_cost=0.0125,
                cache_read_cost=0.005,
            ),
        )
        assert entry.session_id == "abc-123"
        assert entry.project == "open-workspace-builder"
        assert entry.cost.total == pytest.approx(0.1475)

    def test_entry_is_frozen(self) -> None:
        entry = LedgerEntry(
            session_id="abc",
            project="test",
            timestamp="2026-03-28T10:00:00.000Z",
            total_input=0,
            total_output=0,
            total_cache_creation=0,
            total_cache_read=0,
            cost=TokenCost(),
        )
        with pytest.raises(AttributeError):
            entry.session_id = "changed"  # type: ignore[misc]

    def test_optional_story_id(self) -> None:
        entry = LedgerEntry(
            session_id="abc",
            project="test",
            timestamp="2026-03-28T10:00:00.000Z",
            total_input=0,
            total_output=0,
            total_cache_creation=0,
            total_cache_read=0,
            cost=TokenCost(),
            story_id="OWB-S076",
        )
        assert entry.story_id == "OWB-S076"

    def test_story_id_defaults_empty(self) -> None:
        entry = LedgerEntry(
            session_id="abc",
            project="test",
            timestamp="2026-03-28T10:00:00.000Z",
            total_input=0,
            total_output=0,
            total_cache_creation=0,
            total_cache_read=0,
            cost=TokenCost(),
        )
        assert entry.story_id == ""


class TestAppendEntry:
    """append_entry writes a single JSONL line to the ledger file."""

    def test_creates_file_if_missing(self, tmp_path: Path) -> None:
        from open_workspace_builder.tokens.ledger import append_entry

        ledger_path = tmp_path / "ledger.jsonl"
        entry = LedgerEntry(
            session_id="s1",
            project="proj",
            timestamp="2026-03-28T10:00:00.000Z",
            total_input=100,
            total_output=500,
            total_cache_creation=0,
            total_cache_read=0,
            cost=TokenCost(input_cost=0.01, output_cost=0.05),
        )
        append_entry(ledger_path, entry)

        assert ledger_path.exists()
        lines = ledger_path.read_text().strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["session_id"] == "s1"
        assert record["cost"]["input_cost"] == 0.01

    def test_appends_to_existing_file(self, tmp_path: Path) -> None:
        from open_workspace_builder.tokens.ledger import append_entry

        ledger_path = tmp_path / "ledger.jsonl"
        for i in range(3):
            entry = LedgerEntry(
                session_id=f"s{i}",
                project="proj",
                timestamp=f"2026-03-{28 + i:02d}T10:00:00.000Z",
                total_input=100 * (i + 1),
                total_output=500 * (i + 1),
                total_cache_creation=0,
                total_cache_read=0,
                cost=TokenCost(input_cost=0.01 * (i + 1)),
            )
            append_entry(ledger_path, entry)

        lines = ledger_path.read_text().strip().splitlines()
        assert len(lines) == 3
        assert json.loads(lines[2])["session_id"] == "s2"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        from open_workspace_builder.tokens.ledger import append_entry

        ledger_path = tmp_path / "deep" / "nested" / "ledger.jsonl"
        entry = LedgerEntry(
            session_id="s1",
            project="proj",
            timestamp="2026-03-28T10:00:00.000Z",
            total_input=100,
            total_output=500,
            total_cache_creation=0,
            total_cache_read=0,
            cost=TokenCost(),
        )
        append_entry(ledger_path, entry)
        assert ledger_path.exists()

    def test_preserves_story_id(self, tmp_path: Path) -> None:
        from open_workspace_builder.tokens.ledger import append_entry

        ledger_path = tmp_path / "ledger.jsonl"
        entry = LedgerEntry(
            session_id="s1",
            project="proj",
            timestamp="2026-03-28T10:00:00.000Z",
            total_input=100,
            total_output=500,
            total_cache_creation=0,
            total_cache_read=0,
            cost=TokenCost(),
            story_id="OWB-S076",
        )
        append_entry(ledger_path, entry)

        record = json.loads(ledger_path.read_text().strip())
        assert record["story_id"] == "OWB-S076"

    def test_skips_duplicate_session_id(self, tmp_path: Path) -> None:
        from open_workspace_builder.tokens.ledger import append_entry

        ledger_path = tmp_path / "ledger.jsonl"
        entry = LedgerEntry(
            session_id="s1",
            project="proj",
            timestamp="2026-03-28T10:00:00.000Z",
            total_input=100,
            total_output=500,
            total_cache_creation=0,
            total_cache_read=0,
            cost=TokenCost(),
        )
        append_entry(ledger_path, entry)
        append_entry(ledger_path, entry)  # duplicate

        lines = ledger_path.read_text().strip().splitlines()
        assert len(lines) == 1


class TestReadEntries:
    """read_entries loads all LedgerEntry records from the ledger file."""

    def test_reads_entries(self, tmp_path: Path) -> None:
        from open_workspace_builder.tokens.ledger import append_entry, read_entries

        ledger_path = tmp_path / "ledger.jsonl"
        for i in range(3):
            append_entry(
                ledger_path,
                LedgerEntry(
                    session_id=f"s{i}",
                    project="proj",
                    timestamp=f"2026-03-{28 + i:02d}T10:00:00.000Z",
                    total_input=100,
                    total_output=500,
                    total_cache_creation=0,
                    total_cache_read=0,
                    cost=TokenCost(input_cost=0.01),
                ),
            )

        entries = read_entries(ledger_path)
        assert len(entries) == 3
        assert entries[0].session_id == "s0"
        assert entries[2].session_id == "s2"

    def test_returns_empty_for_missing_file(self, tmp_path: Path) -> None:
        from open_workspace_builder.tokens.ledger import read_entries

        entries = read_entries(tmp_path / "nope.jsonl")
        assert entries == []

    def test_skips_malformed_lines(self, tmp_path: Path) -> None:
        from open_workspace_builder.tokens.ledger import read_entries

        ledger_path = tmp_path / "ledger.jsonl"
        good = json.dumps({
            "session_id": "s1",
            "project": "proj",
            "timestamp": "2026-03-28T10:00:00.000Z",
            "total_input": 100,
            "total_output": 500,
            "total_cache_creation": 0,
            "total_cache_read": 0,
            "cost": {
                "input_cost": 0.01,
                "output_cost": 0.0,
                "cache_write_cost": 0.0,
                "cache_read_cost": 0.0,
            },
            "story_id": "",
        })
        ledger_path.write_text(f"not json\n{good}\n{{bad: true}}\n")

        entries = read_entries(ledger_path)
        assert len(entries) == 1
        assert entries[0].session_id == "s1"

    def test_date_filter(self, tmp_path: Path) -> None:
        from open_workspace_builder.tokens.ledger import append_entry, read_entries

        ledger_path = tmp_path / "ledger.jsonl"
        for day in (25, 26, 27, 28):
            append_entry(
                ledger_path,
                LedgerEntry(
                    session_id=f"s{day}",
                    project="proj",
                    timestamp=f"2026-03-{day}T10:00:00.000Z",
                    total_input=100,
                    total_output=500,
                    total_cache_creation=0,
                    total_cache_read=0,
                    cost=TokenCost(input_cost=0.01),
                ),
            )

        entries = read_entries(ledger_path, since="20260327")
        assert len(entries) == 2
        assert entries[0].session_id == "s27"

        entries = read_entries(ledger_path, until="20260326")
        assert len(entries) == 2
        assert entries[1].session_id == "s26"

        entries = read_entries(ledger_path, since="20260326", until="20260327")
        assert len(entries) == 2
