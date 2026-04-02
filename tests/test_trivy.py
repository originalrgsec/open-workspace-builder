"""Tests for Trivy scanner integration (OWB-S091).

Covers version safety checks, JSON parsing, scan flow, CLI commands,
and graceful handling of missing binary. All subprocess calls are mocked.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from open_workspace_builder.cli import owb
from open_workspace_builder.security.trivy import (
    COMPROMISED_VERSIONS,
    SAFE_VERSION,
    TrivyFinding,
    TrivyScanResult,
    check_version_safety,
    get_version,
    is_available,
    parse_trivy_json,
    scan_filesystem,
)

# ── Fixtures ────────────────────────────────────────────────────────────

SAMPLE_TRIVY_JSON: dict = {
    "Results": [
        {
            "Target": "package-lock.json",
            "Type": "npm",
            "Vulnerabilities": [
                {
                    "VulnerabilityID": "CVE-2024-12345",
                    "PkgName": "lodash",
                    "InstalledVersion": "4.17.20",
                    "FixedVersion": "4.17.21",
                    "Severity": "HIGH",
                    "Title": "Prototype Pollution in lodash",
                }
            ],
        },
        {
            "Target": "requirements.txt",
            "Type": "pip",
            "Vulnerabilities": [
                {
                    "VulnerabilityID": "CVE-2024-99999",
                    "PkgName": "requests",
                    "InstalledVersion": "2.28.0",
                    "FixedVersion": "",
                    "Severity": "CRITICAL",
                    "Title": "SSRF in requests",
                },
                {
                    "VulnerabilityID": "CVE-2024-11111",
                    "PkgName": "flask",
                    "InstalledVersion": "2.2.0",
                    "FixedVersion": "2.2.5",
                    "Severity": "MEDIUM",
                    "Title": "Open redirect in Flask",
                },
            ],
        },
    ]
}

SAMPLE_TRIVY_EMPTY: dict = {"Results": []}

SAMPLE_TRIVY_NO_VULNS: dict = {
    "Results": [
        {
            "Target": "package-lock.json",
            "Type": "npm",
            "Vulnerabilities": None,
        }
    ]
}


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


# ── Version safety ──────────────────────────────────────────────────────


class TestVersionSafety:
    """AC-2: Version check blocks compromised versions."""

    def test_safe_version_check(self) -> None:
        is_safe, msg = check_version_safety(SAFE_VERSION)
        assert is_safe is True
        assert "safe" in msg.lower() or "ok" in msg.lower()

    @pytest.mark.parametrize("version", list(COMPROMISED_VERSIONS))
    def test_compromised_version_check(self, version: str) -> None:
        is_safe, msg = check_version_safety(version)
        assert is_safe is False
        assert "compromised" in msg.lower() or "blocked" in msg.lower()

    def test_future_version_check(self) -> None:
        """Versions above the compromised range should pass."""
        is_safe, msg = check_version_safety("0.70.0")
        assert is_safe is True

    def test_older_version_check(self) -> None:
        is_safe, msg = check_version_safety("0.68.0")
        assert is_safe is True


# ── Availability ────────────────────────────────────────────────────────


class TestAvailability:
    def test_trivy_not_available(self) -> None:
        with patch("shutil.which", return_value=None):
            assert is_available() is False

    def test_trivy_available(self) -> None:
        with patch("shutil.which", return_value="/usr/local/bin/trivy"):
            assert is_available() is True

    def test_get_version_returns_string(self) -> None:
        mock_result = type("Result", (), {"stdout": "Version: 0.69.3\n", "returncode": 0})()
        with patch("subprocess.run", return_value=mock_result):
            ver = get_version()
            assert ver == "0.69.3"

    def test_get_version_not_installed(self) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError):
            ver = get_version()
            assert ver is None


# ── JSON parsing ────────────────────────────────────────────────────────


class TestParseTrivyJson:
    def test_parse_trivy_json(self) -> None:
        findings = parse_trivy_json(SAMPLE_TRIVY_JSON)
        assert len(findings) == 3
        # First finding from npm target
        assert findings[0].vulnerability_id == "CVE-2024-12345"
        assert findings[0].package_name == "lodash"
        assert findings[0].installed_version == "4.17.20"
        assert findings[0].fixed_version == "4.17.21"
        assert findings[0].severity == "HIGH"
        assert findings[0].ecosystem == "npm"
        # Second finding from pip target
        assert findings[1].vulnerability_id == "CVE-2024-99999"
        assert findings[1].ecosystem == "pip"
        assert findings[1].severity == "CRITICAL"
        assert findings[1].fixed_version is None  # empty string → None

    def test_parse_trivy_json_empty(self) -> None:
        findings = parse_trivy_json(SAMPLE_TRIVY_EMPTY)
        assert findings == ()

    def test_parse_trivy_json_no_vulns(self) -> None:
        """Targets with Vulnerabilities: null should parse cleanly."""
        findings = parse_trivy_json(SAMPLE_TRIVY_NO_VULNS)
        assert findings == ()


# ── Dataclass immutability ──────────────────────────────────────────────


class TestDataclasses:
    def test_finding_dataclass_frozen(self) -> None:
        finding = TrivyFinding(
            vulnerability_id="CVE-2024-12345",
            package_name="lodash",
            installed_version="4.17.20",
            fixed_version="4.17.21",
            severity="HIGH",
            title="Prototype Pollution",
            ecosystem="npm",
        )
        with pytest.raises(AttributeError):
            finding.severity = "LOW"  # type: ignore[misc]

    def test_scan_result_frozen(self) -> None:
        result = TrivyScanResult(
            findings=(),
            target=".",
            trivy_version="0.69.3",
            ecosystems_scanned=(),
        )
        with pytest.raises(AttributeError):
            result.target = "/other"  # type: ignore[misc]


# ── scan_filesystem ─────────────────────────────────────────────────────


class TestScanFilesystem:
    def test_scan_filesystem_mocked(self, tmp_path: Path) -> None:
        """AC-1: Full scan flow with mocked subprocess."""
        mock_result = type(
            "Result", (), {"stdout": json.dumps(SAMPLE_TRIVY_JSON), "returncode": 0}
        )()
        with (
            patch("shutil.which", return_value="/usr/local/bin/trivy"),
            patch(
                "open_workspace_builder.security.trivy.get_version",
                return_value="0.69.3",
            ),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            result = scan_filesystem(tmp_path)
            assert len(result.findings) == 3
            assert result.trivy_version == "0.69.3"
            assert "npm" in result.ecosystems_scanned
            assert "pip" in result.ecosystems_scanned
            # Verify subprocess was called with correct args
            call_args = mock_run.call_args[0][0]
            assert "trivy" in call_args
            assert "fs" in call_args
            assert "--format" in call_args
            assert "json" in call_args

    def test_scan_blocks_compromised(self, tmp_path: Path) -> None:
        """AC-2: Scan refuses to run with compromised version."""
        with (
            patch("shutil.which", return_value="/usr/local/bin/trivy"),
            patch(
                "open_workspace_builder.security.trivy.get_version",
                return_value="0.69.5",
            ),
        ):
            with pytest.raises(RuntimeError, match="[Cc]ompromised"):
                scan_filesystem(tmp_path)

    def test_scan_trivy_not_available(self, tmp_path: Path) -> None:
        with patch("shutil.which", return_value=None):
            with pytest.raises(ImportError, match="[Tt]rivy"):
                scan_filesystem(tmp_path)

    def test_scan_custom_severity(self, tmp_path: Path) -> None:
        mock_result = type(
            "Result", (), {"stdout": json.dumps(SAMPLE_TRIVY_EMPTY), "returncode": 0}
        )()
        with (
            patch("shutil.which", return_value="/usr/local/bin/trivy"),
            patch(
                "open_workspace_builder.security.trivy.get_version",
                return_value="0.69.3",
            ),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            scan_filesystem(tmp_path, severity_filter="CRITICAL")
            call_args = mock_run.call_args[0][0]
            assert "CRITICAL" in call_args


# ── CLI contract ────────────────────────────────────────────────────────


class TestTrivyCli:
    """CLI contract tests for trivy commands."""

    def test_trivy_command_help(self, runner: CliRunner) -> None:
        result = runner.invoke(owb, ["security", "trivy", "--help"])
        assert result.exit_code == 0
        assert "trivy" in result.output.lower() or "Trivy" in result.output

    def test_scan_trivy_flag_help(self, runner: CliRunner) -> None:
        """AC-3: --trivy flag exists on the scan command."""
        result = runner.invoke(owb, ["security", "scan", "--help"])
        assert result.exit_code == 0
        assert "--trivy" in result.output

    def test_trivy_command_not_installed(self, runner: CliRunner) -> None:
        with (
            patch("shutil.which", return_value=None),
            patch(
                "open_workspace_builder.security.trivy.is_available",
                return_value=False,
            ),
        ):
            result = runner.invoke(owb, ["security", "trivy", "."])
            assert result.exit_code == 1
            assert "not installed" in result.output.lower() or "not found" in result.output.lower()

    def test_trivy_command_compromised_version(self, runner: CliRunner) -> None:
        with (
            patch(
                "open_workspace_builder.security.trivy.is_available",
                return_value=True,
            ),
            patch(
                "open_workspace_builder.security.trivy.get_version",
                return_value="0.69.5",
            ),
        ):
            result = runner.invoke(owb, ["security", "trivy", "."])
            assert result.exit_code == 1
            assert "compromised" in result.output.lower() or "blocked" in result.output.lower()

    def test_trivy_command_clean_scan(self, runner: CliRunner) -> None:
        clean_result = TrivyScanResult(
            findings=(),
            target=".",
            trivy_version="0.69.3",
            ecosystems_scanned=(),
        )
        with patch(
            "open_workspace_builder.security.trivy.scan_filesystem",
            return_value=clean_result,
        ), patch(
            "open_workspace_builder.security.trivy.is_available",
            return_value=True,
        ), patch(
            "open_workspace_builder.security.trivy.get_version",
            return_value="0.69.3",
        ), patch(
            "open_workspace_builder.security.trivy.check_version_safety",
            return_value=(True, "OK"),
        ):
            result = runner.invoke(owb, ["security", "trivy", "."])
            assert result.exit_code == 0

    def test_trivy_command_findings_exit_code(self, runner: CliRunner) -> None:
        finding = TrivyFinding(
            vulnerability_id="CVE-2024-12345",
            package_name="lodash",
            installed_version="4.17.20",
            fixed_version="4.17.21",
            severity="HIGH",
            title="Prototype Pollution",
            ecosystem="npm",
        )
        scan_result = TrivyScanResult(
            findings=(finding,),
            target=".",
            trivy_version="0.69.3",
            ecosystems_scanned=("npm",),
        )
        with patch(
            "open_workspace_builder.security.trivy.scan_filesystem",
            return_value=scan_result,
        ), patch(
            "open_workspace_builder.security.trivy.is_available",
            return_value=True,
        ), patch(
            "open_workspace_builder.security.trivy.get_version",
            return_value="0.69.3",
        ), patch(
            "open_workspace_builder.security.trivy.check_version_safety",
            return_value=(True, "OK"),
        ):
            result = runner.invoke(owb, ["security", "trivy", "."])
            assert result.exit_code == 2

    def test_trivy_json_output(self, runner: CliRunner) -> None:
        clean_result = TrivyScanResult(
            findings=(),
            target=".",
            trivy_version="0.69.3",
            ecosystems_scanned=(),
        )
        with patch(
            "open_workspace_builder.security.trivy.scan_filesystem",
            return_value=clean_result,
        ), patch(
            "open_workspace_builder.security.trivy.is_available",
            return_value=True,
        ), patch(
            "open_workspace_builder.security.trivy.get_version",
            return_value="0.69.3",
        ), patch(
            "open_workspace_builder.security.trivy.check_version_safety",
            return_value=(True, "OK"),
        ):
            result = runner.invoke(owb, ["security", "trivy", "--json", "."])
            assert result.exit_code == 0
            parsed = json.loads(result.output)
            assert "findings" in parsed
