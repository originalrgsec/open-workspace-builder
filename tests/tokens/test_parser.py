"""Tests for JSONL session file parser."""

from __future__ import annotations

import json
from pathlib import Path


from open_workspace_builder.tokens.parser import (
    discover_session_files,
    parse_session_file,
    project_name_from_dir,
)


def _write_jsonl(path: Path, messages: list[dict]) -> None:
    """Write a list of dicts as JSONL."""
    with path.open("w", encoding="utf-8") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")


def _make_assistant_msg(
    model: str = "claude-opus-4-6",
    input_tokens: int = 10,
    output_tokens: int = 50,
    cache_creation: int = 1000,
    cache_read: int = 5000,
    timestamp: str = "2026-03-28T10:00:00.000Z",
) -> dict:
    """Create a minimal assistant message with usage data."""
    return {
        "type": "assistant",
        "timestamp": timestamp,
        "message": {
            "model": model,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_creation_input_tokens": cache_creation,
                "cache_read_input_tokens": cache_read,
            },
        },
    }


def _make_user_msg(timestamp: str = "2026-03-28T09:59:00.000Z") -> dict:
    return {
        "type": "user",
        "timestamp": timestamp,
        "message": {"role": "user", "content": "hello"},
    }


class TestProjectNameFromDir:
    def test_standard_path(self) -> None:
        name = project_name_from_dir("-Users-rgraber-projects-PersonalCode-open-workspace-builder")
        assert name == "open-workspace-builder"

    def test_short_path(self) -> None:
        name = project_name_from_dir("-Users-rgraber")
        assert name == "rgraber"

    def test_single_segment(self) -> None:
        name = project_name_from_dir("-")
        assert name == "-"

    def test_home_siem(self) -> None:
        name = project_name_from_dir("-Users-rgraber-projects-PersonalCode-Home-SIEM")
        assert name == "Home-SIEM"

    def test_cowork_context(self) -> None:
        name = project_name_from_dir("-Users-rgraber-Documents-Claude-Cowork-Claude-Context")
        assert name == "Context"

    def test_code_prefix(self) -> None:
        name = project_name_from_dir("-Users-rgraber-projects-Code-ingest-pipeline")
        assert name == "ingest-pipeline"


class TestDiscoverSessionFiles:
    def test_finds_jsonl_files(self, tmp_path: Path) -> None:
        projects_dir = tmp_path / "projects"
        proj = projects_dir / "-Users-test-myproject"
        proj.mkdir(parents=True)
        (proj / "session1.jsonl").write_text("{}\n")
        (proj / "session2.jsonl").write_text("{}\n")
        (proj / "session1").mkdir()  # non-jsonl dir should be ignored

        files = discover_session_files(projects_dir)
        assert len(files) == 2
        assert all(f.suffix == ".jsonl" for f in files)

    def test_empty_projects_dir(self, tmp_path: Path) -> None:
        projects_dir = tmp_path / "projects"
        projects_dir.mkdir()
        files = discover_session_files(projects_dir)
        assert files == []

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        files = discover_session_files(tmp_path / "nonexistent")
        assert files == []


class TestParseSessionFile:
    def test_parses_assistant_messages(self, tmp_path: Path) -> None:
        session_file = tmp_path / "session.jsonl"
        messages = [
            _make_user_msg(),
            _make_assistant_msg(input_tokens=10, output_tokens=50),
            _make_user_msg(timestamp="2026-03-28T10:05:00.000Z"),
            _make_assistant_msg(
                input_tokens=20,
                output_tokens=100,
                timestamp="2026-03-28T10:06:00.000Z",
            ),
        ]
        _write_jsonl(session_file, messages)

        usages = parse_session_file(session_file)
        assert len(usages) == 2
        assert usages[0].input_tokens == 10
        assert usages[0].output_tokens == 50
        assert usages[1].input_tokens == 20
        assert usages[1].output_tokens == 100

    def test_extracts_model_name(self, tmp_path: Path) -> None:
        session_file = tmp_path / "session.jsonl"
        _write_jsonl(session_file, [_make_assistant_msg(model="claude-sonnet-4-6")])

        usages = parse_session_file(session_file)
        assert usages[0].model == "claude-sonnet-4-6"

    def test_extracts_cache_tokens(self, tmp_path: Path) -> None:
        session_file = tmp_path / "session.jsonl"
        _write_jsonl(
            session_file,
            [_make_assistant_msg(cache_creation=1500, cache_read=8000)],
        )

        usages = parse_session_file(session_file)
        assert usages[0].cache_creation_tokens == 1500
        assert usages[0].cache_read_tokens == 8000

    def test_skips_non_assistant_messages(self, tmp_path: Path) -> None:
        session_file = tmp_path / "session.jsonl"
        messages = [
            {"type": "file-history-snapshot", "messageId": "x"},
            _make_user_msg(),
            _make_assistant_msg(),
        ]
        _write_jsonl(session_file, messages)

        usages = parse_session_file(session_file)
        assert len(usages) == 1

    def test_skips_assistant_without_usage(self, tmp_path: Path) -> None:
        session_file = tmp_path / "session.jsonl"
        messages = [
            {"type": "assistant", "timestamp": "2026-03-28T10:00:00.000Z", "message": {}},
            _make_assistant_msg(),
        ]
        _write_jsonl(session_file, messages)

        usages = parse_session_file(session_file)
        assert len(usages) == 1

    def test_handles_malformed_lines(self, tmp_path: Path) -> None:
        session_file = tmp_path / "session.jsonl"
        with session_file.open("w") as f:
            f.write("not valid json\n")
            f.write(json.dumps(_make_assistant_msg()) + "\n")

        usages = parse_session_file(session_file)
        assert len(usages) == 1

    def test_extracts_timestamp(self, tmp_path: Path) -> None:
        session_file = tmp_path / "session.jsonl"
        _write_jsonl(
            session_file,
            [_make_assistant_msg(timestamp="2026-03-28T15:30:00.000Z")],
        )

        usages = parse_session_file(session_file)
        assert usages[0].timestamp == "2026-03-28T15:30:00.000Z"

    def test_empty_file(self, tmp_path: Path) -> None:
        session_file = tmp_path / "session.jsonl"
        session_file.write_text("")
        usages = parse_session_file(session_file)
        assert usages == []
