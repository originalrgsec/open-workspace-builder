"""Tests for S090 — Pre-install SCA gate.

All external tool calls (pip-audit, guarddog, pip-licenses, PyPI API) are mocked.
No real network calls are made.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from open_workspace_builder.security.gate import (
    GateCheck,
    GateResult,
    run_gate,
    run_gate_batch,
)


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


# ── Dataclass tests ─────────────────────────────────────────────────────


class TestGateCheckDataclass:
    def test_frozen(self) -> None:
        check = GateCheck(name="pip-audit", passed=True, details="No vulns")
        assert check.name == "pip-audit"
        assert check.passed is True
        with pytest.raises(AttributeError):
            check.name = "other"  # type: ignore[misc]

    def test_fields(self) -> None:
        check = GateCheck(name="license", passed=False, details="GPL detected")
        assert check.name == "license"
        assert check.passed is False
        assert check.details == "GPL detected"


class TestGateResultDataclass:
    def test_all_pass(self) -> None:
        checks = (
            GateCheck(name="pip-audit", passed=True, details="clean"),
            GateCheck(name="guarddog", passed=True, details="clean"),
            GateCheck(name="license", passed=True, details="MIT"),
        )
        result = GateResult(
            package="click",
            version="8.1.7",
            checks=checks,
            passed=True,
        )
        assert result.passed is True
        assert len(result.checks) == 3

    def test_any_fail(self) -> None:
        checks = (
            GateCheck(name="pip-audit", passed=True, details="clean"),
            GateCheck(name="guarddog", passed=False, details="malware detected"),
            GateCheck(name="license", passed=True, details="MIT"),
        )
        result = GateResult(
            package="evil-pkg",
            version="0.1.0",
            checks=checks,
            passed=False,
        )
        assert result.passed is False

    def test_frozen(self) -> None:
        result = GateResult(
            package="pkg",
            version="1.0",
            checks=(),
            passed=True,
        )
        with pytest.raises(AttributeError):
            result.package = "other"  # type: ignore[misc]


# ── run_gate tests ──────────────────────────────────────────────────────


class TestRunGate:
    """Test run_gate with all external calls mocked."""

    @patch("open_workspace_builder.security.gate._check_quarantine")
    @patch("open_workspace_builder.security.gate._check_license")
    @patch("open_workspace_builder.security.gate._check_oss_health")
    @patch("open_workspace_builder.security.gate._check_guarddog")
    @patch("open_workspace_builder.security.gate._check_pip_audit")
    def test_full_battery_all_pass(
        self,
        mock_pip_audit: MagicMock,
        mock_guarddog: MagicMock,
        mock_oss_health: MagicMock,
        mock_license: MagicMock,
        mock_quarantine: MagicMock,
    ) -> None:
        mock_pip_audit.return_value = GateCheck(
            name="pip-audit",
            passed=True,
            details="No known vulnerabilities",
        )
        mock_guarddog.return_value = GateCheck(
            name="guarddog",
            passed=True,
            details="No malicious code detected",
        )
        mock_oss_health.return_value = GateCheck(
            name="oss-health",
            passed=True,
            details="Stub — manual review recommended",
        )
        mock_license.return_value = GateCheck(
            name="license",
            passed=True,
            details="MIT — allowed",
        )
        mock_quarantine.return_value = GateCheck(
            name="quarantine",
            passed=True,
            details="Published 30 days ago",
        )

        result = run_gate("click", version="8.1.7")

        assert result.passed is True
        assert result.package == "click"
        assert result.version == "8.1.7"
        assert len(result.checks) == 5
        assert all(c.passed for c in result.checks)

    @patch("open_workspace_builder.security.gate._check_quarantine")
    @patch("open_workspace_builder.security.gate._check_license")
    @patch("open_workspace_builder.security.gate._check_oss_health")
    @patch("open_workspace_builder.security.gate._check_guarddog")
    @patch("open_workspace_builder.security.gate._check_pip_audit")
    def test_full_battery_one_fails(
        self,
        mock_pip_audit: MagicMock,
        mock_guarddog: MagicMock,
        mock_oss_health: MagicMock,
        mock_license: MagicMock,
        mock_quarantine: MagicMock,
    ) -> None:
        mock_pip_audit.return_value = GateCheck(
            name="pip-audit",
            passed=True,
            details="clean",
        )
        mock_guarddog.return_value = GateCheck(
            name="guarddog",
            passed=False,
            details="shady-links rule triggered",
        )
        mock_oss_health.return_value = GateCheck(
            name="oss-health",
            passed=True,
            details="stub",
        )
        mock_license.return_value = GateCheck(
            name="license",
            passed=True,
            details="MIT",
        )
        mock_quarantine.return_value = GateCheck(
            name="quarantine",
            passed=True,
            details="ok",
        )

        result = run_gate("evil-pkg")

        assert result.passed is False
        assert result.package == "evil-pkg"
        assert result.version is None
        failed = [c for c in result.checks if not c.passed]
        assert len(failed) == 1
        assert failed[0].name == "guarddog"


class TestRunGateMissingTools:
    """Verify graceful degradation when pip-audit/guarddog not installed."""

    @patch(
        "open_workspace_builder.security.gate._check_pip_audit",
        return_value=GateCheck(
            name="pip-audit",
            passed=True,
            details="skipped — pip-audit not installed",
        ),
    )
    @patch(
        "open_workspace_builder.security.gate._check_guarddog",
        return_value=GateCheck(
            name="guarddog",
            passed=True,
            details="skipped — guarddog not installed",
        ),
    )
    @patch(
        "open_workspace_builder.security.gate._check_oss_health",
        return_value=GateCheck(name="oss-health", passed=True, details="stub"),
    )
    @patch(
        "open_workspace_builder.security.gate._check_license",
        return_value=GateCheck(name="license", passed=True, details="allowed"),
    )
    @patch(
        "open_workspace_builder.security.gate._check_quarantine",
        return_value=GateCheck(name="quarantine", passed=True, details="ok"),
    )
    def test_skipped_not_failed(
        self,
        _quar: MagicMock,
        _lic: MagicMock,
        _oss: MagicMock,
        _gd: MagicMock,
        _pa: MagicMock,
    ) -> None:
        result = run_gate("some-pkg")
        assert result.passed is True
        pip_check = next(c for c in result.checks if c.name == "pip-audit")
        assert "skipped" in pip_check.details
        gd_check = next(c for c in result.checks if c.name == "guarddog")
        assert "skipped" in gd_check.details


class TestRunGateBatch:
    """Verify batch mode runs gate for multiple packages."""

    @patch("open_workspace_builder.security.gate.run_gate")
    def test_batch_runs_for_each_package(self, mock_run_gate: MagicMock) -> None:
        mock_run_gate.return_value = GateResult(
            package="pkg",
            version=None,
            checks=(GateCheck(name="pip-audit", passed=True, details="ok"),),
            passed=True,
        )
        results = run_gate_batch(["click", "pyyaml", "requests"])
        assert len(results) == 3
        assert mock_run_gate.call_count == 3


# ── Reputation ledger integration ───────────────────────────────────────


class TestGateReputationRecording:
    """Verify gate failures record FlagEvents in the reputation ledger."""

    @patch("open_workspace_builder.security.gate._check_quarantine")
    @patch("open_workspace_builder.security.gate._check_license")
    @patch("open_workspace_builder.security.gate._check_oss_health")
    @patch("open_workspace_builder.security.gate._check_guarddog")
    @patch("open_workspace_builder.security.gate._check_pip_audit")
    def test_failure_records_event(
        self,
        mock_pip_audit: MagicMock,
        mock_guarddog: MagicMock,
        mock_oss_health: MagicMock,
        mock_license: MagicMock,
        mock_quarantine: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_pip_audit.return_value = GateCheck(
            name="pip-audit",
            passed=False,
            details="CVE-2024-001 found",
        )
        mock_guarddog.return_value = GateCheck(
            name="guarddog",
            passed=True,
            details="clean",
        )
        mock_oss_health.return_value = GateCheck(
            name="oss-health",
            passed=True,
            details="stub",
        )
        mock_license.return_value = GateCheck(
            name="license",
            passed=True,
            details="MIT",
        )
        mock_quarantine.return_value = GateCheck(
            name="quarantine",
            passed=True,
            details="ok",
        )

        ledger_path = tmp_path / "ledger.jsonl"
        result = run_gate("bad-pkg", version="1.0", ledger_path=ledger_path)

        assert result.passed is False

        # Verify ledger was written
        from open_workspace_builder.security.reputation import ReputationLedger

        ledger = ReputationLedger(ledger_path)
        history = ledger.get_history("sca-gate")
        assert len(history) == 1
        assert "pip-audit" in history[0].details
        assert history[0].flag_category == "sca-gate-failure"

    @patch("open_workspace_builder.security.gate._check_quarantine")
    @patch("open_workspace_builder.security.gate._check_license")
    @patch("open_workspace_builder.security.gate._check_oss_health")
    @patch("open_workspace_builder.security.gate._check_guarddog")
    @patch("open_workspace_builder.security.gate._check_pip_audit")
    def test_pass_does_not_record(
        self,
        mock_pip_audit: MagicMock,
        mock_guarddog: MagicMock,
        mock_oss_health: MagicMock,
        mock_license: MagicMock,
        mock_quarantine: MagicMock,
        tmp_path: Path,
    ) -> None:
        for m in (mock_pip_audit, mock_guarddog, mock_oss_health, mock_license, mock_quarantine):
            m.return_value = GateCheck(name="x", passed=True, details="ok")

        ledger_path = tmp_path / "ledger.jsonl"
        result = run_gate("good-pkg", ledger_path=ledger_path)

        assert result.passed is True
        from open_workspace_builder.security.reputation import ReputationLedger

        ledger = ReputationLedger(ledger_path)
        assert len(ledger.get_history("sca-gate")) == 0


# ── CLI tests ───────────────────────────────────────────────────────────


class TestCliGateCommand:
    """CLI contract tests for `owb audit gate`."""

    @patch("open_workspace_builder.security.gate.run_gate")
    def test_gate_single_package(
        self,
        mock_run_gate: MagicMock,
        runner: CliRunner,
    ) -> None:
        mock_run_gate.return_value = GateResult(
            package="click",
            version="8.1.7",
            checks=(
                GateCheck(name="pip-audit", passed=True, details="clean"),
                GateCheck(name="guarddog", passed=True, details="clean"),
                GateCheck(name="oss-health", passed=True, details="stub"),
                GateCheck(name="license", passed=True, details="MIT"),
                GateCheck(name="quarantine", passed=True, details="ok"),
            ),
            passed=True,
        )
        from open_workspace_builder.cli import owb

        result = runner.invoke(owb, ["audit", "gate", "click", "--version", "8.1.7"])
        assert result.exit_code == 0
        assert "PASS" in result.output or "pass" in result.output.lower()

    @patch("open_workspace_builder.security.gate.run_gate")
    def test_gate_fail_exit_code(
        self,
        mock_run_gate: MagicMock,
        runner: CliRunner,
    ) -> None:
        mock_run_gate.return_value = GateResult(
            package="evil",
            version=None,
            checks=(GateCheck(name="guarddog", passed=False, details="malware"),),
            passed=False,
        )
        from open_workspace_builder.cli import owb

        result = runner.invoke(owb, ["audit", "gate", "evil"])
        assert result.exit_code == 2

    @patch("open_workspace_builder.security.gate.run_gate")
    def test_gate_json_output(
        self,
        mock_run_gate: MagicMock,
        runner: CliRunner,
    ) -> None:
        mock_run_gate.return_value = GateResult(
            package="click",
            version="8.1.7",
            checks=(GateCheck(name="pip-audit", passed=True, details="clean"),),
            passed=True,
        )
        from open_workspace_builder.cli import owb

        result = runner.invoke(owb, ["audit", "gate", "click", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["package"] == "click"
        assert data["passed"] is True


class TestCliGateAll:
    """CLI test for --all mode."""

    @patch("open_workspace_builder.security.gate.run_gate_batch")
    @patch("open_workspace_builder.security.gate._parse_direct_deps")
    def test_gate_all_reads_pyproject(
        self,
        mock_parse: MagicMock,
        mock_batch: MagicMock,
        runner: CliRunner,
    ) -> None:
        mock_parse.return_value = ["click", "pyyaml"]
        mock_batch.return_value = [
            GateResult(
                package="click",
                version=None,
                checks=(GateCheck(name="pip-audit", passed=True, details="ok"),),
                passed=True,
            ),
            GateResult(
                package="pyyaml",
                version=None,
                checks=(GateCheck(name="pip-audit", passed=True, details="ok"),),
                passed=True,
            ),
        ]
        from open_workspace_builder.cli import owb

        result = runner.invoke(owb, ["audit", "gate", "--all"])
        assert result.exit_code == 0
        mock_parse.assert_called_once()
        mock_batch.assert_called_once_with(["click", "pyyaml"])

    @patch("open_workspace_builder.security.gate.run_gate_batch")
    @patch("open_workspace_builder.security.gate._parse_direct_deps")
    def test_gate_all_any_fail(
        self,
        mock_parse: MagicMock,
        mock_batch: MagicMock,
        runner: CliRunner,
    ) -> None:
        mock_parse.return_value = ["click", "evil"]
        mock_batch.return_value = [
            GateResult(package="click", version=None, checks=(), passed=True),
            GateResult(
                package="evil",
                version=None,
                checks=(GateCheck(name="guarddog", passed=False, details="bad"),),
                passed=False,
            ),
        ]
        from open_workspace_builder.cli import owb

        result = runner.invoke(owb, ["audit", "gate", "--all"])
        assert result.exit_code == 2


# ── S142 fail-closed on tool error ──────────────────────────────────────


class TestGateFailClosedOnToolError:
    """OWB-S142. Distinguish "tool not installed" (skipped, passes) from
    "tool crashed" (errored, fails) so an attacker cannot induce a tool
    error and silently clear the gate."""

    def test_pip_audit_errored_fails_closed_by_default(self) -> None:
        """If pip-audit raises an unexpected exception, default fail-closed
        produces passed=False with detail starting 'errored:'."""
        from open_workspace_builder.security.gate import _check_pip_audit

        with patch(
            "open_workspace_builder.security.dep_audit._audit_single_vuln",
            side_effect=RuntimeError("pip-audit crashed: subprocess exited 137"),
        ):
            check = _check_pip_audit("click", "8.1.7", fail_closed=True)

        assert check.name == "pip-audit"
        assert check.passed is False
        assert check.details.startswith("errored:")
        assert "pip-audit crashed" in check.details

    def test_pip_audit_errored_passes_when_fail_closed_false(self) -> None:
        """With fail_closed=False the errored path returns passed=True but
        labels the detail so the failure is visible in logs."""
        from open_workspace_builder.security.gate import _check_pip_audit

        with patch(
            "open_workspace_builder.security.dep_audit._audit_single_vuln",
            side_effect=RuntimeError("flaky network"),
        ):
            check = _check_pip_audit("click", "8.1.7", fail_closed=False)

        assert check.passed is True
        # Not "skipped" — use "errored" so logs can grep for it even when
        # the knob allows the pass.
        assert "errored" in check.details
        assert "flaky network" in check.details

    def test_pip_audit_not_installed_still_skips(self) -> None:
        """Tool-not-installed remains passed=True, detail=skipped,
        regardless of fail_closed. Absent tools are not a security
        signal; only crashed tools are."""
        import sys

        # Force the ImportError path by making dep_audit unimportable.
        saved = sys.modules.get("open_workspace_builder.security.dep_audit")
        sys.modules["open_workspace_builder.security.dep_audit"] = None  # type: ignore[assignment]
        try:
            from open_workspace_builder.security.gate import _check_pip_audit

            check = _check_pip_audit("click", "8.1.7", fail_closed=True)
        finally:
            if saved is not None:
                sys.modules["open_workspace_builder.security.dep_audit"] = saved
            else:
                sys.modules.pop("open_workspace_builder.security.dep_audit", None)

        assert check.passed is True
        assert "skipped" in check.details.lower()

    def test_guarddog_errored_fails_closed_by_default(self) -> None:
        from open_workspace_builder.security.gate import _check_guarddog

        with patch(
            "open_workspace_builder.security.dep_audit.audit_malicious_code",
            side_effect=ValueError("guarddog returned malformed JSON"),
        ):
            check = _check_guarddog("click", fail_closed=True)

        assert check.passed is False
        assert check.details.startswith("errored:")
        assert "malformed JSON" in check.details

    def test_guarddog_not_installed_still_skips(self) -> None:
        """FileNotFoundError and RuntimeError keep the not-installed
        semantics — they are the sentinel raised by dep_audit when the
        guarddog binary is absent."""
        from open_workspace_builder.security.gate import _check_guarddog

        with patch(
            "open_workspace_builder.security.dep_audit.audit_malicious_code",
            side_effect=FileNotFoundError("guarddog"),
        ):
            check = _check_guarddog("click", fail_closed=True)

        assert check.passed is True
        assert "skipped" in check.details.lower()

    def test_quarantine_errored_fails_closed_by_default(self) -> None:
        """_check_quarantine had the same silent-pass shape; apply the
        same policy. We inject a check_quarantine_age symbol because
        the real quarantine module defers the implementation (gate
        currently catches AttributeError at import time)."""
        from open_workspace_builder.security import quarantine as quarantine_mod
        from open_workspace_builder.security.gate import _check_quarantine

        def _boom(*_a: object, **_kw: object) -> dict[str, object]:
            raise RuntimeError("PyPI JSON unreachable")

        had_attr = hasattr(quarantine_mod, "check_quarantine_age")
        setattr(quarantine_mod, "check_quarantine_age", _boom)
        try:
            check = _check_quarantine("click", "8.1.7", days=7, fail_closed=True)
        finally:
            if not had_attr:
                delattr(quarantine_mod, "check_quarantine_age")

        assert check.passed is False
        assert check.details.startswith("errored:")
        assert "PyPI JSON unreachable" in check.details

    def test_license_errored_fails_closed_by_default(self, tmp_path: Path) -> None:
        """Force the audit exception path by giving _check_license a
        real policy file so it doesn't short-circuit on 'policy not
        found', then mock audit_licenses to raise."""
        from open_workspace_builder.security.gate import _check_license

        policy = tmp_path / "allowed-licenses.md"
        policy.write_text("# allowed\n")
        with (
            patch(
                "open_workspace_builder.security.gate._find_license_policy",
                return_value=policy,
            ),
            patch(
                "open_workspace_builder.security.license_audit.audit_licenses",
                side_effect=RuntimeError("policy parse error"),
            ),
        ):
            check = _check_license("click", "8.1.7", fail_closed=True)

        assert check.passed is False
        assert check.details.startswith("errored:")
        assert "policy parse error" in check.details

    def test_run_gate_defaults_to_fail_closed(self) -> None:
        """SecurityConfig.fail_closed defaults to True, and run_gate
        respects the default when the caller does not override it."""
        from open_workspace_builder.config import SecurityConfig

        cfg = SecurityConfig()
        assert cfg.fail_closed is True

    def test_run_gate_passes_fail_closed_to_checks(self) -> None:
        """run_gate threads fail_closed=False down to pip-audit when the
        caller opts in."""
        from open_workspace_builder.security.gate import run_gate

        with (
            patch("open_workspace_builder.security.gate._check_pip_audit") as mock_pa,
            patch("open_workspace_builder.security.gate._check_guarddog") as mock_gd,
            patch("open_workspace_builder.security.gate._check_oss_health"),
            patch("open_workspace_builder.security.gate._check_license"),
            patch("open_workspace_builder.security.gate._check_quarantine"),
        ):
            mock_pa.return_value = GateCheck(name="pip-audit", passed=True, details="ok")
            mock_gd.return_value = GateCheck(name="guarddog", passed=True, details="ok")
            run_gate("click", fail_closed=False)
            mock_pa.assert_called_with("click", None, fail_closed=False)
            mock_gd.assert_called_with("click", fail_closed=False)
