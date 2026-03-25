"""Tests for dependency supply-chain scanning (OWB-S053).

All external calls (pip-audit API, guarddog subprocess) are mocked.
No real network calls are made.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from open_workspace_builder.cli import owb
from open_workspace_builder.security.dep_audit import (
    AuditReport,
    FullAuditReport,
    GuardDogFinding,
    GuardDogReport,
    VulnFinding,
    _guarddog_severity,
    _load_suppressions,
    _parse_guarddog_output,
    audit_known_vulns,
    audit_malicious_code,
    audit_single_package,
    run_full_audit,
)


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def suppressions_file(tmp_path: Path) -> Path:
    content = (
        "suppressions:\n"
        "  - package: fakepkg\n"
        "    rule: shady-links\n"
        '    reason: "Known false positive"\n'
        "  - package: fakepkg\n"
        "    rule: dll-hijacking\n"
        '    reason: "Legitimate glibc detection"\n'
    )
    p = tmp_path / "suppressions.yaml"
    p.write_text(content, encoding="utf-8")
    return p


# ── Dataclass tests ──────────────────────────────────────────────────────


class TestDataclasses:
    def test_vuln_finding_frozen(self) -> None:
        f = VulnFinding("pkg", "1.0", "CVE-2024-001", "1.1", "desc")
        assert f.package == "pkg"
        with pytest.raises(AttributeError):
            f.package = "other"  # type: ignore[misc]

    def test_audit_report_frozen(self) -> None:
        r = AuditReport(findings=(), skipped=(), fix_suggestions=())
        assert r.findings == ()

    def test_guarddog_finding_frozen(self) -> None:
        f = GuardDogFinding("pkg", "rule", "high", "/path", "evidence")
        assert f.rule_name == "rule"

    def test_full_audit_report_combines(self) -> None:
        vuln = AuditReport(findings=(), skipped=(), fix_suggestions=())
        gd = GuardDogReport(flagged=(), clean=("pkg",))
        full = FullAuditReport(vuln_report=vuln, guarddog_report=gd)
        assert full.guarddog_report.clean == ("pkg",)


# ── Suppressions ─────────────────────────────────────────────────────────


class TestSuppressions:
    def test_load_valid_file(self, suppressions_file: Path) -> None:
        result = _load_suppressions(suppressions_file)
        assert "fakepkg" in result
        assert "shady-links" in result["fakepkg"]
        assert "dll-hijacking" in result["fakepkg"]

    def test_load_none_path(self) -> None:
        assert _load_suppressions(None) == {}

    def test_load_missing_file(self, tmp_path: Path) -> None:
        assert _load_suppressions(tmp_path / "nonexistent.yaml") == {}

    def test_load_invalid_yaml(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.yaml"
        p.write_text("not_a_dict_with_suppressions: true", encoding="utf-8")
        assert _load_suppressions(p) == {}


# ── Guarddog severity ────────────────────────────────────────────────────


class TestGuardDogSeverity:
    def test_critical(self) -> None:
        assert _guarddog_severity(0.8) == "critical"

    def test_high(self) -> None:
        assert _guarddog_severity(0.5) == "high"

    def test_medium(self) -> None:
        assert _guarddog_severity(0.3) == "medium"

    def test_low(self) -> None:
        assert _guarddog_severity(0.1) == "low"


# ── Guarddog output parsing ──────────────────────────────────────────────


class TestParseGuardDogOutput:
    def test_empty_output(self) -> None:
        assert _parse_guarddog_output("pkg", {}, {}) == []

    def test_findings_parsed(self) -> None:
        raw = {
            "code-execution": {
                "score": 0.8,
                "results": [
                    {"location": "setup.py", "code": "eval(bad_stuff)"},
                ],
            }
        }
        findings = _parse_guarddog_output("pkg", raw, {})
        assert len(findings) == 1
        assert findings[0].rule_name == "code-execution"
        assert findings[0].severity == "critical"
        assert findings[0].file_path == "setup.py"

    def test_suppressions_applied(self) -> None:
        raw = {
            "shady-links": {
                "score": 0.3,
                "results": [{"location": "foo.py", "code": "http://evil.tk"}],
            }
        }
        findings = _parse_guarddog_output("fakepkg", raw, {"fakepkg": ["shady-links"]})
        assert findings == []

    def test_metadata_and_errors_skipped(self) -> None:
        raw = {"metadata": {"version": "1.0"}, "errors": ["some error"]}
        assert _parse_guarddog_output("pkg", raw, {}) == []

    def test_no_results_key_skipped(self) -> None:
        raw = {"some-rule": {"score": 0.5}}
        assert _parse_guarddog_output("pkg", raw, {}) == []

    def test_non_dict_hit(self) -> None:
        raw = {"rule-x": {"score": 0.5, "results": ["plain string evidence"]}}
        findings = _parse_guarddog_output("pkg", raw, {})
        assert len(findings) == 1
        assert findings[0].evidence == "plain string evidence"
        assert findings[0].file_path == ""


# ── Layer A: pip-audit (mocked) ──────────────────────────────────────────


def _make_mock_dep(name: str, version: str) -> MagicMock:
    dep = MagicMock()
    dep.name = name
    dep.version = MagicMock()
    dep.version.__str__ = lambda self: version
    return dep


def _make_mock_vuln(vuln_id: str, desc: str, fix_ver: str | None = None) -> MagicMock:
    vuln = MagicMock()
    vuln.id = vuln_id
    vuln.description = desc
    if fix_ver:
        fix_v = MagicMock()
        fix_v.__str__ = lambda self: fix_ver
        vuln.fix_versions = [fix_v]
    else:
        vuln.fix_versions = []
    return vuln


class TestAuditKnownVulns:
    @patch("open_workspace_builder.security.dep_audit.PipSource", create=True)
    @patch("open_workspace_builder.security.dep_audit.OsvService", create=True)
    def test_clean_scan(self, mock_osv_cls: MagicMock, mock_pip_cls: MagicMock) -> None:
        dep = _make_mock_dep("click", "8.1.0")
        mock_pip_cls.return_value.collect.return_value = [dep]
        mock_osv_cls.return_value.query.return_value = (dep, [])

        with patch.dict(
            "sys.modules",
            {
                "pip_audit": MagicMock(),
                "pip_audit._dependency_source": MagicMock(),
                "pip_audit._dependency_source.pip": MagicMock(PipSource=mock_pip_cls),
                "pip_audit._service": MagicMock(),
                "pip_audit._service.osv": MagicMock(OsvService=mock_osv_cls),
                "pip_audit._service.interface": MagicMock(
                    ResolvedDependency=type(dep),
                    SkippedDependency=type(None),
                ),
            },
        ):
            report = audit_known_vulns()
            assert report.findings == ()
            assert report.skipped == ()

    @patch("open_workspace_builder.security.dep_audit.PipSource", create=True)
    @patch("open_workspace_builder.security.dep_audit.OsvService", create=True)
    def test_vuln_detected(self, mock_osv_cls: MagicMock, mock_pip_cls: MagicMock) -> None:
        dep = _make_mock_dep("litellm", "1.82.6")
        vuln = _make_mock_vuln("CVE-2026-9999", "Supply chain compromise", "1.82.9")
        mock_pip_cls.return_value.collect.return_value = [dep]
        mock_osv_cls.return_value.query.return_value = (dep, [vuln])

        with patch.dict(
            "sys.modules",
            {
                "pip_audit": MagicMock(),
                "pip_audit._dependency_source": MagicMock(),
                "pip_audit._dependency_source.pip": MagicMock(PipSource=mock_pip_cls),
                "pip_audit._service": MagicMock(),
                "pip_audit._service.osv": MagicMock(OsvService=mock_osv_cls),
                "pip_audit._service.interface": MagicMock(
                    ResolvedDependency=type(dep),
                    SkippedDependency=type(None),
                ),
            },
        ):
            report = audit_known_vulns()
            assert len(report.findings) == 1
            assert report.findings[0].vuln_id == "CVE-2026-9999"
            assert report.findings[0].fix_version == "1.82.9"

    @patch("open_workspace_builder.security.dep_audit.PipSource", create=True)
    @patch("open_workspace_builder.security.dep_audit.OsvService", create=True)
    def test_fix_suggestions(self, mock_osv_cls: MagicMock, mock_pip_cls: MagicMock) -> None:
        dep = _make_mock_dep("pkg", "1.0")
        vuln = _make_mock_vuln("CVE-2026-0001", "Bad", "1.1")
        mock_pip_cls.return_value.collect.return_value = [dep]
        mock_osv_cls.return_value.query.return_value = (dep, [vuln])

        with patch.dict(
            "sys.modules",
            {
                "pip_audit": MagicMock(),
                "pip_audit._dependency_source": MagicMock(),
                "pip_audit._dependency_source.pip": MagicMock(PipSource=mock_pip_cls),
                "pip_audit._service": MagicMock(),
                "pip_audit._service.osv": MagicMock(OsvService=mock_osv_cls),
                "pip_audit._service.interface": MagicMock(
                    ResolvedDependency=type(dep),
                    SkippedDependency=type(None),
                ),
            },
        ):
            report = audit_known_vulns(fix=True)
            assert "pkg==1.1" in report.fix_suggestions

    def test_pip_audit_not_installed(self) -> None:
        with patch.dict("sys.modules", {"pip_audit": None}):
            with pytest.raises(ImportError, match="pip-audit is required"):
                audit_known_vulns()

    @patch("open_workspace_builder.security.dep_audit.PipSource", create=True)
    @patch("open_workspace_builder.security.dep_audit.OsvService", create=True)
    def test_query_error_skips_package(
        self, mock_osv_cls: MagicMock, mock_pip_cls: MagicMock
    ) -> None:
        dep = _make_mock_dep("broken", "1.0")
        mock_pip_cls.return_value.collect.return_value = [dep]
        mock_osv_cls.return_value.query.side_effect = ConnectionError("offline")

        with patch.dict(
            "sys.modules",
            {
                "pip_audit": MagicMock(),
                "pip_audit._dependency_source": MagicMock(),
                "pip_audit._dependency_source.pip": MagicMock(PipSource=mock_pip_cls),
                "pip_audit._service": MagicMock(),
                "pip_audit._service.osv": MagicMock(OsvService=mock_osv_cls),
                "pip_audit._service.interface": MagicMock(
                    ResolvedDependency=type(dep),
                    SkippedDependency=type(None),
                ),
            },
        ):
            report = audit_known_vulns()
            assert "broken" in report.skipped


# ── Layer B: guarddog (mocked subprocess) ────────────────────────────────


class TestAuditMaliciousCode:
    @patch("open_workspace_builder.security.dep_audit._run_guarddog")
    def test_clean_package(self, mock_run: MagicMock) -> None:
        mock_run.return_value = {}
        report = audit_malicious_code(["safe-pkg"])
        assert report.flagged == ()
        assert "safe-pkg" in report.clean

    @patch("open_workspace_builder.security.dep_audit._run_guarddog")
    def test_flagged_package(self, mock_run: MagicMock) -> None:
        mock_run.return_value = {
            "code-execution": {
                "score": 0.9,
                "results": [{"location": "setup.py", "code": "os.system('curl ...')"}],
            }
        }
        report = audit_malicious_code(["evil-pkg"])
        assert len(report.flagged) == 1
        assert report.flagged[0].package == "evil-pkg"
        assert report.flagged[0].rule_name == "code-execution"

    @patch("open_workspace_builder.security.dep_audit._run_guarddog")
    def test_suppressions_filter(
        self, mock_run: MagicMock, suppressions_file: Path
    ) -> None:
        mock_run.return_value = {
            "shady-links": {
                "score": 0.3,
                "results": [{"location": "foo.py", "code": "http://evil.tk"}],
            }
        }
        report = audit_malicious_code(["fakepkg"], suppressions_file=suppressions_file)
        assert report.flagged == ()
        assert "fakepkg" in report.clean

    @patch("open_workspace_builder.security.dep_audit.subprocess.run")
    def test_guarddog_not_installed(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError("uvx not found")
        with pytest.raises(RuntimeError, match="guarddog requires uvx"):
            audit_malicious_code(["pkg"])

    @patch("open_workspace_builder.security.dep_audit.subprocess.run")
    def test_guarddog_timeout(self, mock_run: MagicMock) -> None:
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="uvx", timeout=120)
        with pytest.raises(RuntimeError, match="timed out"):
            audit_malicious_code(["pkg"])

    @patch("open_workspace_builder.security.dep_audit.subprocess.run")
    def test_guarddog_non_json_output(self, mock_run: MagicMock) -> None:
        proc = MagicMock()
        proc.stdout = "not json at all"
        proc.stderr = ""
        proc.returncode = 0
        mock_run.return_value = proc
        with pytest.raises(RuntimeError, match="non-JSON"):
            audit_malicious_code(["pkg"])

    @patch("open_workspace_builder.security.dep_audit.subprocess.run")
    def test_guarddog_nonzero_exit_empty_stdout(self, mock_run: MagicMock) -> None:
        proc = MagicMock()
        proc.stdout = ""
        proc.stderr = "some error"
        proc.returncode = 1
        mock_run.return_value = proc
        with pytest.raises(RuntimeError, match="guarddog failed"):
            audit_malicious_code(["pkg"])


# ── Combined scanning ────────────────────────────────────────────────────


class TestRunFullAudit:
    @patch("open_workspace_builder.security.dep_audit.audit_known_vulns")
    def test_shallow_audit(self, mock_vulns: MagicMock) -> None:
        mock_vulns.return_value = AuditReport(findings=(), skipped=(), fix_suggestions=())
        report = run_full_audit(deep=False)
        assert report.vuln_report.findings == ()
        assert report.guarddog_report.flagged == ()
        assert report.guarddog_report.clean == ()

    @patch("open_workspace_builder.security.dep_audit.audit_malicious_code")
    @patch("open_workspace_builder.security.dep_audit._installed_package_names")
    @patch("open_workspace_builder.security.dep_audit.audit_known_vulns")
    def test_deep_audit_calls_guarddog(
        self, mock_vulns: MagicMock, mock_names: MagicMock, mock_gd: MagicMock
    ) -> None:
        mock_vulns.return_value = AuditReport(findings=(), skipped=(), fix_suggestions=())
        mock_names.return_value = ["click", "pyyaml"]
        mock_gd.return_value = GuardDogReport(flagged=(), clean=("click", "pyyaml"))
        report = run_full_audit(deep=True)
        mock_gd.assert_called_once()
        assert report.guarddog_report.clean == ("click", "pyyaml")


class TestAuditSinglePackage:
    @patch("open_workspace_builder.security.dep_audit.audit_malicious_code")
    @patch("open_workspace_builder.security.dep_audit.audit_known_vulns")
    def test_single_package(self, mock_vulns: MagicMock, mock_gd: MagicMock) -> None:
        mock_vulns.return_value = AuditReport(findings=(), skipped=(), fix_suggestions=())
        mock_gd.return_value = GuardDogReport(flagged=(), clean=("click",))
        report = audit_single_package("click", version="8.1.0")
        assert report.guarddog_report.clean == ("click",)

    @patch("open_workspace_builder.security.dep_audit.audit_malicious_code")
    def test_single_package_pip_audit_missing(self, mock_gd: MagicMock) -> None:
        mock_gd.return_value = GuardDogReport(flagged=(), clean=("newpkg",))
        with patch(
            "open_workspace_builder.security.dep_audit.audit_known_vulns",
            side_effect=ImportError("no pip-audit"),
        ):
            report = audit_single_package("newpkg")
            assert "newpkg" in report.vuln_report.skipped


# ── CLI integration ──────────────────────────────────────────────────────


class TestCLIAuditDeps:
    @patch("open_workspace_builder.security.dep_audit.audit_known_vulns")
    def test_clean_exit_0(self, mock_vulns: MagicMock, runner: CliRunner) -> None:
        mock_vulns.return_value = AuditReport(findings=(), skipped=(), fix_suggestions=())
        result = runner.invoke(owb, ["audit", "deps"])
        assert result.exit_code == 0
        assert "No known vulnerabilities" in result.output

    @patch("open_workspace_builder.security.dep_audit.audit_known_vulns")
    def test_vuln_exit_2(self, mock_vulns: MagicMock, runner: CliRunner) -> None:
        finding = VulnFinding("bad", "1.0", "CVE-2026-0001", "1.1", "Bad vulnerability")
        mock_vulns.return_value = AuditReport(
            findings=(finding,), skipped=(), fix_suggestions=()
        )
        result = runner.invoke(owb, ["audit", "deps"])
        assert result.exit_code == 2
        assert "CVE-2026-0001" in result.output

    @patch("open_workspace_builder.security.dep_audit.audit_known_vulns")
    def test_json_format(self, mock_vulns: MagicMock, runner: CliRunner) -> None:
        mock_vulns.return_value = AuditReport(findings=(), skipped=(), fix_suggestions=())
        result = runner.invoke(owb, ["audit", "deps", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "vulnerabilities" in data
        assert "guarddog_flagged" in data

    @patch("open_workspace_builder.security.dep_audit.audit_known_vulns")
    def test_fix_flag(self, mock_vulns: MagicMock, runner: CliRunner) -> None:
        finding = VulnFinding("pkg", "1.0", "CVE-X", "1.1", "desc")
        mock_vulns.return_value = AuditReport(
            findings=(finding,), skipped=(), fix_suggestions=("pkg==1.1",)
        )
        result = runner.invoke(owb, ["audit", "deps", "--fix"])
        assert result.exit_code == 2
        assert "pkg==1.1" in result.output

    @patch("open_workspace_builder.security.dep_audit.audit_known_vulns")
    def test_output_file(
        self, mock_vulns: MagicMock, runner: CliRunner, tmp_path: Path
    ) -> None:
        mock_vulns.return_value = AuditReport(findings=(), skipped=(), fix_suggestions=())
        out = tmp_path / "report.json"
        result = runner.invoke(owb, ["audit", "deps", "--output", str(out)])
        assert result.exit_code == 0
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "vulnerabilities" in data


class TestCLIAuditPackage:
    @patch("open_workspace_builder.security.dep_audit.audit_malicious_code")
    @patch("open_workspace_builder.security.dep_audit.audit_known_vulns")
    def test_clean_package(
        self, mock_vulns: MagicMock, mock_gd: MagicMock, runner: CliRunner
    ) -> None:
        mock_vulns.return_value = AuditReport(findings=(), skipped=(), fix_suggestions=())
        mock_gd.return_value = GuardDogReport(flagged=(), clean=("click",))
        result = runner.invoke(owb, ["audit", "package", "click"])
        assert result.exit_code == 0
        assert "All checks passed" in result.output

    @patch("open_workspace_builder.security.dep_audit.audit_malicious_code")
    @patch("open_workspace_builder.security.dep_audit.audit_known_vulns")
    def test_package_json_output(
        self, mock_vulns: MagicMock, mock_gd: MagicMock, runner: CliRunner
    ) -> None:
        mock_vulns.return_value = AuditReport(findings=(), skipped=(), fix_suggestions=())
        mock_gd.return_value = GuardDogReport(flagged=(), clean=("click",))
        result = runner.invoke(owb, ["audit", "package", "click", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["guarddog_clean"] == ["click"]

    @patch("open_workspace_builder.security.dep_audit.audit_malicious_code")
    @patch("open_workspace_builder.security.dep_audit.audit_known_vulns")
    def test_package_with_version(
        self, mock_vulns: MagicMock, mock_gd: MagicMock, runner: CliRunner
    ) -> None:
        mock_vulns.return_value = AuditReport(findings=(), skipped=(), fix_suggestions=())
        mock_gd.return_value = GuardDogReport(flagged=(), clean=("litellm",))
        result = runner.invoke(
            owb, ["audit", "package", "litellm", "--version", "1.82.6"]
        )
        assert result.exit_code == 0
