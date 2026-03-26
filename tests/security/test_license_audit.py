"""Tests for license compliance audit (Story S068)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from open_workspace_builder.security.license_audit import (
    LicensePolicy,
    audit_licenses,
    format_license_report,
    parse_license_policy,
)


@pytest.fixture
def policy_path(content_root: Path) -> Path:
    """Return the real allowed-licenses.md policy file path."""
    return content_root / "content" / "policies" / "allowed-licenses.md"


@pytest.fixture
def policy(policy_path: Path) -> LicensePolicy:
    """Parse the real policy file."""
    return parse_license_policy(policy_path)


@pytest.fixture
def sample_deps() -> list[dict[str, str]]:
    """Sample pip-licenses output for testing."""
    return [
        {"Name": "requests", "Version": "2.31.0", "License": "Apache 2.0"},
        {"Name": "click", "Version": "8.1.7", "License": "BSD 3-Clause"},
        {"Name": "some-gpl-pkg", "Version": "1.0.0", "License": "GPL v3"},
        {"Name": "mystery-pkg", "Version": "0.1.0", "License": "Weird Custom License"},
        {"Name": "mpl-pkg", "Version": "3.0.0", "License": "MPL 2.0"},
    ]


# ── Policy Parsing Tests ────────────────────────────────────────────────


class TestPolicyParsing:
    """Test that the policy file is correctly parsed into three categories."""

    def test_allowed_licenses_extracted(self, policy: LicensePolicy) -> None:
        names = [c.name for c in policy.allowed]
        assert "MIT" in names
        assert "Apache 2.0" in names
        assert "BSD 2-Clause" in names
        assert "BSD 3-Clause" in names
        assert "ISC" in names
        assert "0BSD" in names

    def test_conditional_licenses_extracted(self, policy: LicensePolicy) -> None:
        names = [c.name for c in policy.conditional]
        assert any("MPL" in n for n in names)
        assert any("BSL" in n for n in names)

    def test_disallowed_licenses_extracted(self, policy: LicensePolicy) -> None:
        names = [c.name for c in policy.disallowed]
        assert any("GPL" in n for n in names)
        assert any("AGPL" in n for n in names)
        assert any("LGPL" in n for n in names)
        assert any("SSPL" in n for n in names)

    def test_conditional_has_condition_text(self, policy: LicensePolicy) -> None:
        for cat in policy.conditional:
            assert cat.condition, f"{cat.name} should have condition text"

    def test_missing_policy_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="not found"):
            parse_license_policy(tmp_path / "nonexistent.md")

    def test_unparseable_policy_raises(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad-policy.md"
        bad_file.write_text("# Nothing useful here\n\nJust text.\n", encoding="utf-8")
        with pytest.raises(ValueError, match="Could not parse"):
            parse_license_policy(bad_file)

    def test_cc0_and_public_domain_parsed(self, policy: LicensePolicy) -> None:
        # "CC0 / Public Domain / Unlicense" should produce patterns covering all three
        all_patterns = []
        for cat in policy.allowed:
            all_patterns.extend(cat.patterns)
        assert any("cc0" in p for p in all_patterns)
        assert any("public domain" in p for p in all_patterns)
        assert any("unlicense" in p for p in all_patterns)


# ── License Matching Tests ───────────────────────────────────────────────


class TestLicenseMatching:
    """Test license classification against policy."""

    def test_exact_match_mit(self, policy_path: Path) -> None:
        deps = [{"Name": "pkg", "Version": "1.0", "License": "MIT"}]
        report = audit_licenses(policy_path, dep_data=deps)
        assert report.findings[0].status == "pass"

    def test_case_insensitive_match(self, policy_path: Path) -> None:
        deps = [{"Name": "pkg", "Version": "1.0", "License": "mit license"}]
        report = audit_licenses(policy_path, dep_data=deps)
        assert report.findings[0].status == "pass"

    def test_apache_variations(self, policy_path: Path) -> None:
        for variant in ["Apache 2.0", "Apache-2.0", "apache 2.0", "Apache 2.0 License"]:
            deps = [{"Name": "pkg", "Version": "1.0", "License": variant}]
            report = audit_licenses(policy_path, dep_data=deps)
            assert report.findings[0].status == "pass", f"Failed for: {variant}"

    def test_bsd_variations(self, policy_path: Path) -> None:
        for variant in ["BSD 3-Clause", "BSD-3-Clause", "bsd 3-clause", "BSD 2-Clause"]:
            deps = [{"Name": "pkg", "Version": "1.0", "License": variant}]
            report = audit_licenses(policy_path, dep_data=deps)
            assert report.findings[0].status == "pass", f"Failed for: {variant}"

    def test_gpl_flagged_as_fail(self, policy_path: Path) -> None:
        deps = [{"Name": "pkg", "Version": "1.0", "License": "GPL v3"}]
        report = audit_licenses(policy_path, dep_data=deps)
        assert report.findings[0].status == "fail"

    def test_agpl_flagged_as_fail(self, policy_path: Path) -> None:
        deps = [{"Name": "pkg", "Version": "1.0", "License": "AGPL v3"}]
        report = audit_licenses(policy_path, dep_data=deps)
        assert report.findings[0].status == "fail"

    def test_lgpl_flagged_as_fail(self, policy_path: Path) -> None:
        deps = [{"Name": "pkg", "Version": "1.0", "License": "LGPL v3"}]
        report = audit_licenses(policy_path, dep_data=deps)
        assert report.findings[0].status == "fail"

    def test_mpl_flagged_as_conditional(self, policy_path: Path) -> None:
        deps = [{"Name": "pkg", "Version": "1.0", "License": "MPL 2.0"}]
        report = audit_licenses(policy_path, dep_data=deps)
        assert report.findings[0].status == "conditional"
        assert report.findings[0].policy_note  # Should have condition text

    def test_unknown_license_flagged(self, policy_path: Path) -> None:
        deps = [{"Name": "pkg", "Version": "1.0", "License": "Proprietary Weird License"}]
        report = audit_licenses(policy_path, dep_data=deps)
        assert report.findings[0].status == "unknown"
        assert "manual review" in report.findings[0].policy_note.lower()

    def test_empty_license_flagged_unknown(self, policy_path: Path) -> None:
        deps = [{"Name": "pkg", "Version": "1.0", "License": ""}]
        report = audit_licenses(policy_path, dep_data=deps)
        assert report.findings[0].status == "unknown"

    def test_isc_license_pass(self, policy_path: Path) -> None:
        deps = [{"Name": "pkg", "Version": "1.0", "License": "ISC"}]
        report = audit_licenses(policy_path, dep_data=deps)
        assert report.findings[0].status == "pass"

    def test_cc0_license_pass(self, policy_path: Path) -> None:
        deps = [{"Name": "pkg", "Version": "1.0", "License": "CC0"}]
        report = audit_licenses(policy_path, dep_data=deps)
        assert report.findings[0].status == "pass"

    def test_public_domain_pass(self, policy_path: Path) -> None:
        deps = [{"Name": "pkg", "Version": "1.0", "License": "Public Domain"}]
        report = audit_licenses(policy_path, dep_data=deps)
        assert report.findings[0].status == "pass"


# ── Full Audit Tests ────────────────────────────────────────────────────


class TestFullAudit:
    """Test the full audit pipeline."""

    def test_mixed_results(
        self, policy_path: Path, sample_deps: list[dict[str, str]]
    ) -> None:
        report = audit_licenses(policy_path, dep_data=sample_deps)
        statuses = {f.package: f.status for f in report.findings}
        assert statuses["requests"] == "pass"
        assert statuses["click"] == "pass"
        assert statuses["some-gpl-pkg"] == "fail"
        assert statuses["mystery-pkg"] == "unknown"
        assert statuses["mpl-pkg"] == "conditional"

    def test_empty_deps_clean_pass(self, policy_path: Path) -> None:
        report = audit_licenses(policy_path, dep_data=[])
        assert len(report.findings) == 0

    def test_report_ecosystem_is_python(self, policy_path: Path) -> None:
        report = audit_licenses(policy_path, dep_data=[])
        assert report.ecosystem == "python"

    def test_report_includes_policy_path(self, policy_path: Path) -> None:
        report = audit_licenses(policy_path, dep_data=[])
        assert str(policy_path) in report.policy_file


# ── JSON Output Tests ────────────────────────────────────────────────────


class TestJsonOutput:
    """Test JSON serialization of audit reports."""

    def test_valid_json_structure(
        self, policy_path: Path, sample_deps: list[dict[str, str]]
    ) -> None:
        report = audit_licenses(policy_path, dep_data=sample_deps)
        data = format_license_report(report)
        # Should be valid JSON
        json_str = json.dumps(data)
        parsed = json.loads(json_str)
        assert parsed["type"] == "license_audit"
        assert "summary" in parsed
        assert "findings" in parsed

    def test_json_summary_counts(
        self, policy_path: Path, sample_deps: list[dict[str, str]]
    ) -> None:
        report = audit_licenses(policy_path, dep_data=sample_deps)
        data = format_license_report(report)
        summary = data["summary"]
        assert summary["total"] == 5
        assert summary["pass"] == 2
        assert summary["fail"] == 1
        assert summary["unknown"] == 1
        assert summary["conditional"] == 1

    def test_json_finding_structure(self, policy_path: Path) -> None:
        deps = [{"Name": "pkg", "Version": "1.0", "License": "MIT"}]
        report = audit_licenses(policy_path, dep_data=deps)
        data = format_license_report(report)
        finding = data["findings"][0]
        assert "package" in finding
        assert "version" in finding
        assert "license" in finding
        assert "status" in finding
        assert "note" in finding


# ── Subprocess / pip-licenses Tests ──────────────────────────────────────


class TestPipLicensesIntegration:
    """Test pip-licenses subprocess handling."""

    def test_pip_licenses_not_found_error(self, policy_path: Path) -> None:
        with patch(
            "open_workspace_builder.security.license_audit.subprocess.run",
            side_effect=FileNotFoundError("uvx not found"),
        ):
            with pytest.raises(RuntimeError, match="Could not run pip-licenses"):
                audit_licenses(policy_path)

    def test_pip_licenses_mocked_success(self, policy_path: Path) -> None:
        mock_output = json.dumps([
            {"Name": "click", "Version": "8.1.7", "License": "BSD License"},
        ])
        mock_proc = type("Proc", (), {"returncode": 0, "stdout": mock_output, "stderr": ""})()
        with patch(
            "open_workspace_builder.security.license_audit.subprocess.run",
            return_value=mock_proc,
        ):
            report = audit_licenses(policy_path)
            assert len(report.findings) == 1
            assert report.findings[0].package == "click"


# ── CLI Tests ────────────────────────────────────────────────────────────


class TestCLI:
    """Test the CLI integration for audit licenses."""

    def test_audit_licenses_command_exists(self) -> None:
        from click.testing import CliRunner

        from open_workspace_builder.cli import owb

        runner = CliRunner()
        result = runner.invoke(owb, ["audit", "licenses", "--help"])
        assert result.exit_code == 0
        assert "allowed-licenses" in result.output.lower() or "policy" in result.output.lower()

    def test_audit_licenses_json_flag(self, policy_path: Path) -> None:
        from click.testing import CliRunner

        from open_workspace_builder.cli import owb

        mock_output = json.dumps([
            {"Name": "requests", "Version": "2.31.0", "License": "Apache 2.0"},
        ])
        mock_proc = type("Proc", (), {"returncode": 0, "stdout": mock_output, "stderr": ""})()
        runner = CliRunner()
        with patch(
            "open_workspace_builder.security.license_audit.subprocess.run",
            return_value=mock_proc,
        ):
            result = runner.invoke(
                owb, ["audit", "licenses", "--policy", str(policy_path), "--format", "json"]
            )
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["type"] == "license_audit"

    def test_audit_deps_licenses_flag_exists(self) -> None:
        from click.testing import CliRunner

        from open_workspace_builder.cli import owb

        runner = CliRunner()
        result = runner.invoke(owb, ["audit", "deps", "--help"])
        assert result.exit_code == 0
        assert "--licenses" in result.output
