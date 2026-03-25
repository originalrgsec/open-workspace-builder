"""Tests for SAST scanning via Semgrep (OWB-S056).

All subprocess calls are mocked — semgrep does not need to be installed.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from open_workspace_builder.cli import owb
from open_workspace_builder.security.sast import (
    SastFinding,
    SastReport,
    _parse_semgrep_json,
    run_semgrep,
)


# ── Sample data ──────────────────────────────────────────────────────────


SAMPLE_SEMGREP_JSON = {
    "results": [
        {
            "check_id": "python.lang.security.audit.exec-detected",
            "path": "src/foo.py",
            "start": {"line": 42, "col": 1},
            "end": {"line": 42, "col": 20},
            "extra": {
                "severity": "ERROR",
                "message": "Use of exec() detected",
                "lines": "exec(user_input)",
            },
        },
        {
            "check_id": "python.lang.security.audit.subprocess-shell-true",
            "path": "src/bar.py",
            "start": {"line": 18, "col": 1},
            "end": {"line": 18, "col": 40},
            "extra": {
                "severity": "WARNING",
                "message": "subprocess call with shell=True",
                "lines": "subprocess.run(cmd, shell=True)",
            },
        },
    ],
    "errors": [],
    "paths": {
        "scanned": ["src/foo.py", "src/bar.py", "src/baz.py"],
    },
}

SAMPLE_EMPTY_JSON = {
    "results": [],
    "errors": [],
    "paths": {
        "scanned": ["src/foo.py", "src/bar.py"],
    },
}


# ── Dataclass tests ──────────────────────────────────────────────────────


class TestSastFindingDataclass:
    def test_construction(self) -> None:
        f = SastFinding(
            rule_id="test.rule",
            severity="ERROR",
            message="bad code",
            file="src/a.py",
            line=10,
            code="exec(x)",
        )
        assert f.rule_id == "test.rule"
        assert f.severity == "ERROR"
        assert f.message == "bad code"
        assert f.file == "src/a.py"
        assert f.line == 10
        assert f.code == "exec(x)"

    def test_immutability(self) -> None:
        f = SastFinding("r", "WARNING", "msg", "f.py", 1, "code")
        with pytest.raises(AttributeError):
            f.rule_id = "other"  # type: ignore[misc]


class TestSastReportDataclass:
    def test_construction(self) -> None:
        r = SastReport(findings=(), errors=(), rules_run=42)
        assert r.findings == ()
        assert r.errors == ()
        assert r.rules_run == 42

    def test_immutability(self) -> None:
        r = SastReport(findings=(), errors=(), rules_run=0)
        with pytest.raises(AttributeError):
            r.rules_run = 5  # type: ignore[misc]


# ── Parser tests ─────────────────────────────────────────────────────────


class TestParseSemgrepJson:
    def test_parse_findings(self) -> None:
        report = _parse_semgrep_json(SAMPLE_SEMGREP_JSON)
        assert isinstance(report, SastReport)
        assert len(report.findings) == 2

        f0 = report.findings[0]
        assert f0.rule_id == "python.lang.security.audit.exec-detected"
        assert f0.severity == "ERROR"
        assert f0.file == "src/foo.py"
        assert f0.line == 42
        assert f0.code == "exec(user_input)"

        f1 = report.findings[1]
        assert f1.severity == "WARNING"
        assert f1.line == 18

    def test_parse_rules_run(self) -> None:
        report = _parse_semgrep_json(SAMPLE_SEMGREP_JSON)
        assert report.rules_run == 3

    def test_parse_empty(self) -> None:
        report = _parse_semgrep_json(SAMPLE_EMPTY_JSON)
        assert len(report.findings) == 0
        assert len(report.errors) == 0
        assert report.rules_run == 2

    def test_parse_errors(self) -> None:
        raw = {
            "results": [],
            "errors": [{"message": "config error"}],
            "paths": {"scanned": []},
        }
        report = _parse_semgrep_json(raw)
        assert len(report.errors) == 1
        assert report.errors[0] == "config error"

    def test_parse_completely_empty(self) -> None:
        report = _parse_semgrep_json({})
        assert len(report.findings) == 0
        assert report.rules_run == 0


# ── run_semgrep tests ────────────────────────────────────────────────────


class TestRunSemgrep:
    @patch("open_workspace_builder.security.sast.subprocess.run")
    def test_semgrep_not_installed(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError("No such file or directory: 'semgrep'")
        with pytest.raises(ImportError, match="semgrep is not installed"):
            run_semgrep(Path("src/"))

    @patch("open_workspace_builder.security.sast.subprocess.run")
    def test_semgrep_timeout(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="semgrep", timeout=300)
        with pytest.raises(RuntimeError, match="timed out"):
            run_semgrep(Path("src/"))

    @patch("open_workspace_builder.security.sast.subprocess.run")
    def test_json_output(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout=json.dumps(SAMPLE_SEMGREP_JSON),
            returncode=0,
        )
        report = run_semgrep(Path("src/"), config="auto")
        assert isinstance(report, SastReport)
        assert len(report.findings) == 2

    @patch("open_workspace_builder.security.sast.subprocess.run")
    def test_sarif_output(self, mock_run: MagicMock) -> None:
        sarif_str = '{"version": "2.1.0", "runs": []}'
        mock_run.return_value = MagicMock(stdout=sarif_str, returncode=0)
        result = run_semgrep(Path("src/"), sarif=True)
        assert isinstance(result, str)
        assert "2.1.0" in result

    @patch("open_workspace_builder.security.sast.subprocess.run")
    def test_empty_stdout(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        report = run_semgrep(Path("src/"))
        assert isinstance(report, SastReport)
        assert len(report.findings) == 0


# ── CLI tests ────────────────────────────────────────────────────────────


class TestSastCli:
    @pytest.fixture()
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_sast_command_registered(self, runner: CliRunner) -> None:
        result = runner.invoke(owb, ["security", "--help"])
        assert result.exit_code == 0
        assert "sast" in result.output

    @patch("open_workspace_builder.security.sast.subprocess.run")
    def test_sast_text_output(self, mock_run: MagicMock, runner: CliRunner, tmp_path: Path) -> None:
        target = tmp_path / "code"
        target.mkdir()
        (target / "foo.py").write_text("x = 1\n")

        mock_run.return_value = MagicMock(
            stdout=json.dumps(SAMPLE_SEMGREP_JSON),
            returncode=0,
        )
        result = runner.invoke(owb, ["security", "sast", str(target)])
        assert "SAST Scan (Semgrep)" in result.output
        assert "exec-detected" in result.output

    @patch("open_workspace_builder.security.sast.subprocess.run")
    def test_sast_json_output(self, mock_run: MagicMock, runner: CliRunner, tmp_path: Path) -> None:
        target = tmp_path / "code"
        target.mkdir()
        (target / "foo.py").write_text("x = 1\n")

        mock_run.return_value = MagicMock(
            stdout=json.dumps(SAMPLE_EMPTY_JSON),
            returncode=0,
        )
        result = runner.invoke(owb, ["security", "sast", "--format", "json", str(target)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "findings" in data
        assert data["rules_run"] == 2

    @patch("open_workspace_builder.security.sast.subprocess.run")
    def test_sast_exit_code_on_error_findings(
        self, mock_run: MagicMock, runner: CliRunner, tmp_path: Path
    ) -> None:
        target = tmp_path / "code"
        target.mkdir()
        (target / "foo.py").write_text("x = 1\n")

        mock_run.return_value = MagicMock(
            stdout=json.dumps(SAMPLE_SEMGREP_JSON),
            returncode=0,
        )
        result = runner.invoke(owb, ["security", "sast", str(target)])
        assert result.exit_code == 2
