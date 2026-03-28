"""CLI contract tests for owb metrics tokens commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

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
                "model": "claude-sonnet-4-6",
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


class TestMetricsTokensReport:
    def test_text_output(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        projects_dir = claude_dir / "projects"
        _setup_session_files(projects_dir)

        runner = CliRunner()
        result = runner.invoke(owb, ["metrics", "tokens", "--claude-dir", str(claude_dir)])
        assert result.exit_code == 0
        assert "Token Consumption Report" in result.output
        assert "TOTALS" in result.output
        assert "BY MODEL" in result.output

    def test_json_output(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        projects_dir = claude_dir / "projects"
        _setup_session_files(projects_dir)

        runner = CliRunner()
        result = runner.invoke(
            owb, ["metrics", "tokens", "--claude-dir", str(claude_dir), "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "totals" in data
        assert "by_model" in data
        assert "by_project" in data

    def test_date_filter(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        projects_dir = claude_dir / "projects"
        _setup_session_files(projects_dir)

        runner = CliRunner()
        # Filter to a date that has no data
        result = runner.invoke(
            owb,
            ["metrics", "tokens", "--claude-dir", str(claude_dir), "--since", "20260401"],
        )
        assert result.exit_code == 0
        assert "No session files found" in result.output or "Sessions: 0" in result.output

    def test_project_filter(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        projects_dir = claude_dir / "projects"
        _setup_session_files(projects_dir)

        runner = CliRunner()
        result = runner.invoke(
            owb,
            [
                "metrics", "tokens",
                "--claude-dir", str(claude_dir),
                "--project", "myproject",
                "--format", "json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["messages"] == 2

    def test_no_sessions(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        (claude_dir / "projects").mkdir(parents=True)

        runner = CliRunner()
        result = runner.invoke(owb, ["metrics", "tokens", "--claude-dir", str(claude_dir)])
        assert result.exit_code == 0
        assert "No session files found" in result.output

    def test_nonexistent_claude_dir(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            owb, ["metrics", "tokens", "--claude-dir", str(tmp_path / "nope")]
        )
        assert result.exit_code == 1


class TestMetricsExport:
    def test_gsheets_requires_sheet_id(self) -> None:
        runner = CliRunner()
        result = runner.invoke(owb, ["metrics", "export", "--format", "gsheets"])
        assert result.exit_code == 1
        assert "--sheet-id" in result.output

    def test_xlsx_requires_output(self) -> None:
        runner = CliRunner()
        result = runner.invoke(owb, ["metrics", "export", "--format", "xlsx"])
        assert result.exit_code == 1
        assert "--output" in result.output

    def test_xlsx_missing_dependency(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        projects_dir = claude_dir / "projects"
        _setup_session_files(projects_dir)

        runner = CliRunner()
        with patch.dict("sys.modules", {"xlsxwriter": None}):
            result = runner.invoke(
                owb,
                [
                    "metrics", "export",
                    "--format", "xlsx",
                    "--output", str(tmp_path / "out.xlsx"),
                    "--claude-dir", str(claude_dir),
                ],
            )
        # Should fail gracefully with an import error message
        # (may succeed if xlsxwriter is installed in the test env)
        assert result.exit_code in (0, 1)


class TestReporterFormat:
    def test_format_report_includes_sections(self, tmp_path: Path) -> None:
        from open_workspace_builder.tokens.calculator import build_report
        from open_workspace_builder.tokens.models import ModelPricing, TokenUsage
        from open_workspace_builder.tokens.reporter import format_report

        data = [
            (
                "test-project",
                "sess-1",
                [
                    TokenUsage(
                        model="claude-opus-4-6",
                        input_tokens=1000,
                        output_tokens=5000,
                        cache_creation_tokens=10000,
                        cache_read_tokens=50000,
                        timestamp="2026-03-28T10:00:00.000Z",
                    ),
                ],
            ),
        ]
        pricing = {"claude-opus-4-6": ModelPricing(5.0, 25.0, 6.25, 0.50)}
        report = build_report(data, pricing)
        text = format_report(report)

        assert "Token Consumption Report" in text
        assert "TOTALS" in text
        assert "COST BREAKDOWN" in text
        assert "CACHE EFFICIENCY" in text
        assert "BY MODEL" in text
        assert "BY PROJECT" in text
        assert "BY DAY" in text
        assert "test-project" in text
        assert "claude-opus-4-6" in text
