"""CLI contract tests for Level C token tracking commands."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from open_workspace_builder.cli import owb


def _setup_session_files(projects_dir: Path) -> None:
    """Create minimal session fixtures for CLI testing."""
    proj = projects_dir / "-Users-test-projects-Code-myproject"
    proj.mkdir(parents=True)

    session = proj / "test-session.jsonl"
    messages = [
        {
            "type": "assistant",
            "timestamp": "2026-03-28T10:00:00.000Z",
            "message": {
                "model": "claude-opus-4-6",
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 500,
                    "cache_creation_input_tokens": 2000,
                    "cache_read_input_tokens": 10000,
                },
            },
        },
        {
            "type": "assistant",
            "timestamp": "2026-03-28T11:00:00.000Z",
            "message": {
                "model": "claude-opus-4-6",
                "usage": {
                    "input_tokens": 50,
                    "output_tokens": 200,
                    "cache_creation_input_tokens": 1000,
                    "cache_read_input_tokens": 5000,
                },
            },
        },
    ]
    with session.open("w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")


class TestMetricsRecord:
    """owb metrics record — append session cost to local ledger."""

    def test_records_to_ledger(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        _setup_session_files(claude_dir / "projects")
        ledger_path = tmp_path / "ledger.jsonl"

        runner = CliRunner()
        result = runner.invoke(
            owb,
            [
                "metrics", "record",
                "--claude-dir", str(claude_dir),
                "--ledger", str(ledger_path),
            ],
        )
        assert result.exit_code == 0
        assert "Recorded" in result.output
        assert ledger_path.exists()
        lines = ledger_path.read_text().strip().splitlines()
        assert len(lines) >= 1

    def test_record_with_story_tag(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        _setup_session_files(claude_dir / "projects")
        ledger_path = tmp_path / "ledger.jsonl"

        runner = CliRunner()
        result = runner.invoke(
            owb,
            [
                "metrics", "record",
                "--claude-dir", str(claude_dir),
                "--ledger", str(ledger_path),
                "--story", "OWB-S076",
            ],
        )
        assert result.exit_code == 0
        record = json.loads(ledger_path.read_text().strip().splitlines()[0])
        assert record["story_id"] == "OWB-S076"

    def test_record_skips_duplicates(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        _setup_session_files(claude_dir / "projects")
        ledger_path = tmp_path / "ledger.jsonl"

        runner = CliRunner()
        for _ in range(2):
            runner.invoke(
                owb,
                [
                    "metrics", "record",
                    "--claude-dir", str(claude_dir),
                    "--ledger", str(ledger_path),
                ],
            )
        lines = ledger_path.read_text().strip().splitlines()
        assert len(lines) == 1

    def test_record_nonexistent_claude_dir(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            owb,
            [
                "metrics", "record",
                "--claude-dir", str(tmp_path / "nope"),
                "--ledger", str(tmp_path / "ledger.jsonl"),
            ],
        )
        assert result.exit_code == 1


class TestMetricsForecast:
    """owb metrics forecast — show cost forecast for sprint planning."""

    def test_forecast_with_ledger_data(self, tmp_path: Path) -> None:
        ledger_path = tmp_path / "ledger.jsonl"
        # Write some ledger entries
        for day in range(1, 15):
            entry = {
                "session_id": f"s{day}",
                "project": "proj",
                "timestamp": f"2026-03-{day:02d}T10:00:00.000Z",
                "total_input": 100,
                "total_output": 500,
                "total_cache_creation": 0,
                "total_cache_read": 0,
                "cost": {
                    "input_cost": 5.0,
                    "output_cost": 0.0,
                    "cache_write_cost": 0.0,
                    "cache_read_cost": 0.0,
                },
                "story_id": "",
            }
            with ledger_path.open("a") as f:
                f.write(json.dumps(entry) + "\n")

        runner = CliRunner()
        result = runner.invoke(
            owb,
            [
                "metrics", "forecast",
                "--ledger", str(ledger_path),
                "--current-date", "2026-03-28",
            ],
        )
        assert result.exit_code == 0
        assert "Month-to-date" in result.output
        assert "Projected" in result.output

    def test_forecast_json_format(self, tmp_path: Path) -> None:
        ledger_path = tmp_path / "ledger.jsonl"
        entry = {
            "session_id": "s1",
            "project": "proj",
            "timestamp": "2026-03-15T10:00:00.000Z",
            "total_input": 100,
            "total_output": 500,
            "total_cache_creation": 0,
            "total_cache_read": 0,
            "cost": {
                "input_cost": 50.0,
                "output_cost": 0.0,
                "cache_write_cost": 0.0,
                "cache_read_cost": 0.0,
            },
            "story_id": "",
        }
        ledger_path.write_text(json.dumps(entry) + "\n")

        runner = CliRunner()
        result = runner.invoke(
            owb,
            [
                "metrics", "forecast",
                "--ledger", str(ledger_path),
                "--current-date", "2026-03-28",
                "--format", "json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "month_to_date" in data
        assert "projected_total" in data

    def test_forecast_empty_ledger(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            owb,
            [
                "metrics", "forecast",
                "--ledger", str(tmp_path / "nope.jsonl"),
                "--current-date", "2026-03-28",
            ],
        )
        assert result.exit_code == 0
        assert "No ledger data" in result.output


class TestMetricsBudgetCheck:
    """owb metrics budget-check — check budget threshold."""

    def test_under_budget(self, tmp_path: Path) -> None:
        ledger_path = tmp_path / "ledger.jsonl"
        entry = {
            "session_id": "s1",
            "project": "proj",
            "timestamp": "2026-03-15T10:00:00.000Z",
            "total_input": 100,
            "total_output": 500,
            "total_cache_creation": 0,
            "total_cache_read": 0,
            "cost": {
                "input_cost": 50.0,
                "output_cost": 0.0,
                "cache_write_cost": 0.0,
                "cache_read_cost": 0.0,
            },
            "story_id": "",
        }
        ledger_path.write_text(json.dumps(entry) + "\n")

        runner = CliRunner()
        result = runner.invoke(
            owb,
            [
                "metrics", "budget-check",
                "--ledger", str(ledger_path),
                "--threshold", "200",
                "--current-date", "2026-03-28",
            ],
        )
        assert result.exit_code == 0
        assert "Under budget" in result.output

    def test_over_budget_exit_code(self, tmp_path: Path) -> None:
        ledger_path = tmp_path / "ledger.jsonl"
        entry = {
            "session_id": "s1",
            "project": "proj",
            "timestamp": "2026-03-15T10:00:00.000Z",
            "total_input": 100,
            "total_output": 500,
            "total_cache_creation": 0,
            "total_cache_read": 0,
            "cost": {
                "input_cost": 250.0,
                "output_cost": 0.0,
                "cache_write_cost": 0.0,
                "cache_read_cost": 0.0,
            },
            "story_id": "",
        }
        ledger_path.write_text(json.dumps(entry) + "\n")

        runner = CliRunner()
        result = runner.invoke(
            owb,
            [
                "metrics", "budget-check",
                "--ledger", str(ledger_path),
                "--threshold", "200",
                "--current-date", "2026-03-28",
            ],
        )
        assert result.exit_code == 2
        assert "OVER BUDGET" in result.output


class TestMetricsSync:
    """owb metrics sync — record + export in one command."""

    def test_sync_records_to_ledger(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        _setup_session_files(claude_dir / "projects")
        ledger_path = tmp_path / "ledger.jsonl"

        runner = CliRunner()
        # Sync without sheet-id should record only, skip export
        result = runner.invoke(
            owb,
            [
                "metrics", "sync",
                "--claude-dir", str(claude_dir),
                "--ledger", str(ledger_path),
            ],
        )
        assert result.exit_code == 0
        assert "Recorded" in result.output
        assert ledger_path.exists()

    def test_sync_nonexistent_claude_dir(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            owb,
            [
                "metrics", "sync",
                "--claude-dir", str(tmp_path / "nope"),
                "--ledger", str(tmp_path / "ledger.jsonl"),
            ],
        )
        assert result.exit_code == 1


class TestMetricsByStory:
    """owb metrics tokens --by-story groups costs by story tag from ledger."""

    def test_by_story_grouping(self, tmp_path: Path) -> None:
        ledger_path = tmp_path / "ledger.jsonl"
        entries = [
            {
                "session_id": "s1",
                "project": "proj",
                "timestamp": "2026-03-15T10:00:00.000Z",
                "total_input": 100,
                "total_output": 500,
                "total_cache_creation": 0,
                "total_cache_read": 0,
                "cost": {
                    "input_cost": 20.0,
                    "output_cost": 0.0,
                    "cache_write_cost": 0.0,
                    "cache_read_cost": 0.0,
                },
                "story_id": "OWB-S075",
            },
            {
                "session_id": "s2",
                "project": "proj",
                "timestamp": "2026-03-16T10:00:00.000Z",
                "total_input": 100,
                "total_output": 500,
                "total_cache_creation": 0,
                "total_cache_read": 0,
                "cost": {
                    "input_cost": 30.0,
                    "output_cost": 0.0,
                    "cache_write_cost": 0.0,
                    "cache_read_cost": 0.0,
                },
                "story_id": "OWB-S076",
            },
            {
                "session_id": "s3",
                "project": "proj",
                "timestamp": "2026-03-17T10:00:00.000Z",
                "total_input": 100,
                "total_output": 500,
                "total_cache_creation": 0,
                "total_cache_read": 0,
                "cost": {
                    "input_cost": 15.0,
                    "output_cost": 0.0,
                    "cache_write_cost": 0.0,
                    "cache_read_cost": 0.0,
                },
                "story_id": "OWB-S075",
            },
        ]
        with ledger_path.open("w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        runner = CliRunner()
        result = runner.invoke(
            owb,
            [
                "metrics", "by-story",
                "--ledger", str(ledger_path),
                "--format", "json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "OWB-S075" in data
        assert "OWB-S076" in data
        assert data["OWB-S075"]["total_cost"] == 35.0
        assert data["OWB-S076"]["total_cost"] == 30.0
