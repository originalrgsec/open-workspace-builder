"""Tests for secrets scanning module (OWB-S086).

Covers: GitleaksBackend, GgshieldBackend, factory function,
config defaults, CLI command, and scan integration.
All subprocess calls are mocked — no real scanner binaries needed.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from open_workspace_builder.cli import owb
from open_workspace_builder.config import SecurityConfig
from open_workspace_builder.security.secrets_scanner import (
    GgshieldBackend,
    GitleaksBackend,
    SecretFinding,
    get_secrets_backend,
)


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


SAMPLE_GITLEAKS_JSON = json.dumps([
    {
        "Description": "AWS Access Key",
        "File": "config.py",
        "StartLine": 10,
        "RuleID": "aws-access-key-id",
        "Match": "AKIA...[REDACTED]",
    },
    {
        "Description": "Generic API Key",
        "File": "app.py",
        "StartLine": 42,
        "RuleID": "generic-api-key",
        "Match": "sk_live_...[REDACTED]",
    },
])


SAMPLE_GGSHIELD_JSON = json.dumps({
    "scans": [
        {
            "policy_break_count": 1,
            "policy_breaks": [
                {
                    "break_type": "AWS Keys",
                    "matches": [
                        {
                            "match": "AKIA...[REDACTED]",
                            "type": "apikey",
                            "line_start": 5,
                        }
                    ],
                }
            ],
            "id": "secrets.py",
        }
    ]
})


# ── GitleaksBackend ─────────────────────────────────────────────────────


class TestGitleaksBackendScanClean:
    """AC-1: Clean scan returns empty findings."""

    def test_clean_scan_returns_empty_findings(self) -> None:
        backend = GitleaksBackend()
        with patch("open_workspace_builder.security.secrets_scanner.subprocess.run") as mock_run:
            mock_run.return_value = type(
                "Result", (), {"returncode": 0, "stdout": "[]", "stderr": ""}
            )()
            findings, exit_code = backend.scan_path(Path("/tmp/clean"))
        assert findings == []
        assert exit_code == 0

    def test_clean_scan_calls_gitleaks_correctly(self) -> None:
        backend = GitleaksBackend()
        with patch("open_workspace_builder.security.secrets_scanner.subprocess.run") as mock_run:
            mock_run.return_value = type(
                "Result", (), {"returncode": 0, "stdout": "[]", "stderr": ""}
            )()
            backend.scan_path(Path("/tmp/project"))
        cmd = mock_run.call_args[0][0]
        assert "gitleaks" in cmd
        assert "--no-git" in cmd
        assert "--source" in cmd


class TestGitleaksBackendScanFindings:
    """AC-1: Scan with findings parses JSON correctly."""

    def test_findings_parsed_from_json(self) -> None:
        backend = GitleaksBackend()
        with patch("open_workspace_builder.security.secrets_scanner.subprocess.run") as mock_run:
            mock_run.return_value = type(
                "Result", (), {"returncode": 1, "stdout": SAMPLE_GITLEAKS_JSON, "stderr": ""}
            )()
            findings, exit_code = backend.scan_path(Path("/tmp/dirty"))
        assert exit_code == 1
        assert len(findings) == 2
        assert isinstance(findings[0], SecretFinding)
        assert findings[0].file == "config.py"
        assert findings[0].line == 10
        assert findings[0].rule_id == "aws-access-key-id"
        assert findings[1].rule_id == "generic-api-key"


class TestGitleaksBackendNotAvailable:
    """Graceful handling when gitleaks is not installed."""

    def test_is_available_returns_false_when_missing(self) -> None:
        with patch("open_workspace_builder.security.secrets_scanner.shutil.which", return_value=None):
            backend = GitleaksBackend()
            assert backend.is_available() is False

    def test_is_available_returns_true_when_present(self) -> None:
        with patch(
            "open_workspace_builder.security.secrets_scanner.shutil.which",
            return_value="/usr/local/bin/gitleaks",
        ):
            backend = GitleaksBackend()
            assert backend.is_available() is True

    def test_version_returns_none_when_missing(self) -> None:
        with patch("open_workspace_builder.security.secrets_scanner.shutil.which", return_value=None):
            backend = GitleaksBackend()
            assert backend.version() is None

    def test_version_returns_string_when_present(self) -> None:
        with patch(
            "open_workspace_builder.security.secrets_scanner.shutil.which",
            return_value="/usr/local/bin/gitleaks",
        ):
            with patch("open_workspace_builder.security.secrets_scanner.subprocess.run") as mock_run:
                mock_run.return_value = type(
                    "Result", (), {"returncode": 0, "stdout": "v8.18.0\n", "stderr": ""}
                )()
                backend = GitleaksBackend()
                assert backend.version() == "v8.18.0"


# ── GgshieldBackend ─────────────────────────────────────────────────────


class TestGgshieldBackendRequiresApiKey:
    """AC-3: ggshield requires GITGUARDIAN_API_KEY."""

    def test_not_available_without_api_key(self) -> None:
        with (
            patch(
                "open_workspace_builder.security.secrets_scanner.shutil.which",
                return_value="/usr/local/bin/ggshield",
            ),
            patch.dict("os.environ", {}, clear=True),
        ):
            backend = GgshieldBackend()
            assert backend.is_available() is False

    def test_available_with_binary_and_api_key(self) -> None:
        with (
            patch(
                "open_workspace_builder.security.secrets_scanner.shutil.which",
                return_value="/usr/local/bin/ggshield",
            ),
            patch.dict("os.environ", {"GITGUARDIAN_API_KEY": "test-key"}),
        ):
            backend = GgshieldBackend()
            assert backend.is_available() is True

    def test_not_available_without_binary(self) -> None:
        with (
            patch("open_workspace_builder.security.secrets_scanner.shutil.which", return_value=None),
            patch.dict("os.environ", {"GITGUARDIAN_API_KEY": "test-key"}),
        ):
            backend = GgshieldBackend()
            assert backend.is_available() is False

    def test_scan_parses_ggshield_json(self) -> None:
        backend = GgshieldBackend()
        with patch("open_workspace_builder.security.secrets_scanner.subprocess.run") as mock_run:
            mock_run.return_value = type(
                "Result", (), {"returncode": 1, "stdout": SAMPLE_GGSHIELD_JSON, "stderr": ""}
            )()
            findings, exit_code = backend.scan_path(Path("/tmp/dirty"))
        assert exit_code == 1
        assert len(findings) == 1
        assert findings[0].rule_id == "AWS Keys"


# ── Factory ─────────────────────────────────────────────────────────────


class TestGetSecretsBackendFactory:
    """AC-3: Factory returns correct backend type."""

    def test_default_returns_gitleaks(self) -> None:
        backend = get_secrets_backend()
        assert isinstance(backend, GitleaksBackend)

    def test_gitleaks_explicit(self) -> None:
        backend = get_secrets_backend("gitleaks")
        assert isinstance(backend, GitleaksBackend)

    def test_ggshield_explicit(self) -> None:
        backend = get_secrets_backend("ggshield")
        assert isinstance(backend, GgshieldBackend)

    def test_unknown_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown secrets scanner"):
            get_secrets_backend("unknown-tool")


# ── Config ──────────────────────────────────────────────────────────────


class TestSecretsConfigDefaults:
    """AC-3: SecurityConfig has secrets fields with correct defaults."""

    def test_secrets_scanner_default(self) -> None:
        cfg = SecurityConfig()
        assert cfg.secrets_scanner == "gitleaks"

    def test_secrets_enabled_default_false(self) -> None:
        cfg = SecurityConfig()
        assert cfg.secrets_enabled is False


# ── CLI: secrets command ────────────────────────────────────────────────


class TestCliSecretsCommand:
    """AC-1: CLI command exists and responds."""

    def test_secrets_help(self, runner: CliRunner) -> None:
        result = runner.invoke(owb, ["security", "secrets", "--help"])
        assert result.exit_code == 0
        assert "secrets" in result.output.lower()

    def test_secrets_scan_clean(self, runner: CliRunner, tmp_path: Path) -> None:
        with (
            patch("open_workspace_builder.security.secrets_scanner.shutil.which", return_value="/usr/bin/gitleaks"),
            patch("open_workspace_builder.security.secrets_scanner.subprocess.run") as mock_run,
        ):
            mock_run.return_value = type(
                "Result", (), {"returncode": 0, "stdout": "[]", "stderr": ""}
            )()
            result = runner.invoke(owb, ["security", "secrets", str(tmp_path)])
        assert result.exit_code == 0

    def test_secrets_scan_findings_exit_2(self, runner: CliRunner, tmp_path: Path) -> None:
        with (
            patch("open_workspace_builder.security.secrets_scanner.shutil.which", return_value="/usr/bin/gitleaks"),
            patch("open_workspace_builder.security.secrets_scanner.subprocess.run") as mock_run,
        ):
            mock_run.return_value = type(
                "Result", (), {"returncode": 1, "stdout": SAMPLE_GITLEAKS_JSON, "stderr": ""}
            )()
            result = runner.invoke(owb, ["security", "secrets", str(tmp_path)])
        assert result.exit_code == 2

    def test_secrets_scanner_flag(self, runner: CliRunner) -> None:
        """The --scanner option accepts gitleaks and ggshield."""
        result = runner.invoke(owb, ["security", "secrets", "--help"])
        assert "gitleaks" in result.output
        assert "ggshield" in result.output

    def test_secrets_format_flag(self, runner: CliRunner) -> None:
        """The --format option accepts text and json."""
        result = runner.invoke(owb, ["security", "secrets", "--help"])
        assert "text" in result.output
        assert "json" in result.output


# ── CLI: scan --secrets flag ────────────────────────────────────────────


class TestScanSecretsFlag:
    """AC-4: --secrets flag on scan command."""

    def test_secrets_flag_exists(self, runner: CliRunner) -> None:
        result = runner.invoke(owb, ["security", "scan", "--help"])
        assert "--secrets" in result.output

    def test_all_flag_exists(self, runner: CliRunner) -> None:
        result = runner.invoke(owb, ["security", "scan", "--help"])
        assert "--all" in result.output
