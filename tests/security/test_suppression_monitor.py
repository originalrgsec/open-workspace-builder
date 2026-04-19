"""Tests for CVE suppression monitoring (OWB-S059).

All HTTP calls are mocked. No real network calls are made.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from open_workspace_builder.cli import owb
from open_workspace_builder.security.suppression_monitor import (
    SuppressionStatus,
    _days_since,
    _find_fix_version,
    check_suppression,
)
from open_workspace_builder.security.suppressions_schema import (
    Suppression,
    load_suppressions,
)


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def sample_suppression() -> Suppression:
    return Suppression(
        cve="CVE-2026-4539",
        package="pygments",
        suppressed_date="2026-03-24",
        reason="ReDoS in AdlLexer",
        pinned_version="2.19.2",
        ci_flag="--ignore-vuln CVE-2026-4539",
    )


@pytest.fixture()
def valid_registry(tmp_path: Path) -> Path:
    p = tmp_path / "suppressions.yaml"
    p.write_text(
        "suppressions:\n"
        "  - cve: CVE-2026-4539\n"
        "    package: pygments\n"
        '    pinned_version: "2.19.2"\n'
        "    suppressed_date: '2026-03-24'\n"
        '    reason: "ReDoS test"\n'
        '    ci_flag: "--ignore-vuln CVE-2026-4539"\n',
        encoding="utf-8",
    )
    return p


# ── Registry loading ─────────────────────────────────────────────────────


class TestLoadSuppressions:
    def test_valid_yaml(self, valid_registry: Path) -> None:
        result = load_suppressions(valid_registry)
        assert len(result) == 1
        assert result[0].cve == "CVE-2026-4539"
        assert result[0].package == "pygments"
        assert result[0].pinned_version == "2.19.2"

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_suppressions(tmp_path / "nonexistent.yaml")

    def test_empty_file(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.yaml"
        p.write_text("", encoding="utf-8")
        assert load_suppressions(p) == []

    def test_missing_required_fields(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.yaml"
        p.write_text(
            "suppressions:\n  - cve: CVE-2026-0001\n    package: foo\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="missing required fields"):
            load_suppressions(p)

    def test_default_path_exists(self) -> None:
        """The bundled suppressions.yaml should load without errors."""
        result = load_suppressions()
        assert len(result) >= 1
        assert result[0].cve == "CVE-2026-4539"


# ── OSV response parsing ─────────────────────────────────────────────────


class TestFindFixVersion:
    def test_with_fixed_version(self) -> None:
        osv = {
            "affected": [
                {
                    "package": {"name": "pygments", "ecosystem": "PyPI"},
                    "ranges": [
                        {
                            "type": "ECOSYSTEM",
                            "events": [
                                {"introduced": "0"},
                                {"fixed": "2.20.0"},
                            ],
                        }
                    ],
                }
            ]
        }
        assert _find_fix_version(osv, "pygments") == "2.20.0"

    def test_without_fixed_version(self) -> None:
        osv = {
            "affected": [
                {
                    "package": {"name": "pygments", "ecosystem": "PyPI"},
                    "ranges": [
                        {
                            "type": "ECOSYSTEM",
                            "events": [{"introduced": "0"}],
                        }
                    ],
                }
            ]
        }
        assert _find_fix_version(osv, "pygments") is None

    def test_wrong_ecosystem(self) -> None:
        osv = {
            "affected": [
                {
                    "package": {"name": "pygments", "ecosystem": "npm"},
                    "ranges": [
                        {
                            "type": "ECOSYSTEM",
                            "events": [{"fixed": "2.20.0"}],
                        }
                    ],
                }
            ]
        }
        assert _find_fix_version(osv, "pygments") is None

    def test_wrong_package_name(self) -> None:
        osv = {
            "affected": [
                {
                    "package": {"name": "other-pkg", "ecosystem": "PyPI"},
                    "ranges": [
                        {
                            "type": "ECOSYSTEM",
                            "events": [{"fixed": "1.0.0"}],
                        }
                    ],
                }
            ]
        }
        assert _find_fix_version(osv, "pygments") is None

    def test_multiple_ranges(self) -> None:
        osv = {
            "affected": [
                {
                    "package": {"name": "pygments", "ecosystem": "PyPI"},
                    "ranges": [
                        {
                            "type": "ECOSYSTEM",
                            "events": [{"introduced": "2.0"}],
                        },
                        {
                            "type": "ECOSYSTEM",
                            "events": [
                                {"introduced": "2.15"},
                                {"fixed": "2.20.0"},
                            ],
                        },
                    ],
                }
            ]
        }
        assert _find_fix_version(osv, "pygments") == "2.20.0"


# ── Network error handling ────────────────────────────────────────────────


class TestCheckSuppressionErrors:
    @patch("open_workspace_builder.security.suppression_monitor._query_osv")
    @patch("open_workspace_builder.security.suppression_monitor._get_current_version")
    def test_network_timeout(
        self, mock_ver: MagicMock, mock_osv: MagicMock, sample_suppression: Suppression
    ) -> None:
        mock_ver.return_value = "2.19.2"
        import urllib.error

        mock_osv.side_effect = urllib.error.URLError("timed out")
        status = check_suppression(sample_suppression)
        assert status.fix_available is False
        assert status.error is not None
        assert "timed out" in status.error

    @patch("open_workspace_builder.security.suppression_monitor._query_osv")
    @patch("open_workspace_builder.security.suppression_monitor._get_current_version")
    def test_404_response(
        self, mock_ver: MagicMock, mock_osv: MagicMock, sample_suppression: Suppression
    ) -> None:
        mock_ver.return_value = "2.19.2"
        import urllib.error

        mock_osv.side_effect = urllib.error.HTTPError(
            url="",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,  # type: ignore[arg-type]
        )
        status = check_suppression(sample_suppression)
        assert status.fix_available is False
        assert "not found in OSV" in (status.error or "")

    @patch("open_workspace_builder.security.suppression_monitor._query_osv")
    @patch("open_workspace_builder.security.suppression_monitor._get_current_version")
    def test_fix_available(
        self, mock_ver: MagicMock, mock_osv: MagicMock, sample_suppression: Suppression
    ) -> None:
        mock_ver.return_value = "2.19.2"
        mock_osv.return_value = {
            "affected": [
                {
                    "package": {"name": "pygments", "ecosystem": "PyPI"},
                    "ranges": [
                        {
                            "type": "ECOSYSTEM",
                            "events": [
                                {"introduced": "0"},
                                {"fixed": "2.20.0"},
                            ],
                        }
                    ],
                }
            ]
        }
        status = check_suppression(sample_suppression)
        assert status.fix_available is True
        assert status.fixed_version == "2.20.0"
        assert status.current_version == "2.19.2"

    @patch("open_workspace_builder.security.suppression_monitor._query_osv")
    @patch("open_workspace_builder.security.suppression_monitor._get_current_version")
    def test_no_fix_available(
        self, mock_ver: MagicMock, mock_osv: MagicMock, sample_suppression: Suppression
    ) -> None:
        mock_ver.return_value = "2.19.2"
        mock_osv.return_value = {
            "affected": [
                {
                    "package": {"name": "pygments", "ecosystem": "PyPI"},
                    "ranges": [
                        {
                            "type": "ECOSYSTEM",
                            "events": [{"introduced": "0"}],
                        }
                    ],
                }
            ]
        }
        status = check_suppression(sample_suppression)
        assert status.fix_available is False
        assert status.fixed_version is None


# ── Days-since calculation ────────────────────────────────────────────────


class TestDaysSince:
    def test_valid_date(self) -> None:
        from datetime import date as dt_date

        today = dt_date.today().isoformat()
        assert _days_since(today) == 0

    def test_invalid_date(self) -> None:
        assert _days_since("not-a-date") == 0


# ── CLI integration ──────────────────────────────────────────────────────


class TestCLICheckSuppressions:
    @patch("open_workspace_builder.security.suppression_monitor.check_all_suppressions")
    def test_text_output_no_fix(self, mock_check: MagicMock, runner: CliRunner) -> None:
        mock_check.return_value = [
            SuppressionStatus(
                suppression=Suppression(
                    cve="CVE-2026-4539",
                    package="pygments",
                    suppressed_date="2026-03-24",
                    reason="test",
                    pinned_version="2.19.2",
                    ci_flag="--ignore-vuln CVE-2026-4539",
                ),
                fix_available=False,
                fixed_version=None,
                current_version="2.19.2",
                days_suppressed=1,
            )
        ]
        result = runner.invoke(owb, ["audit", "check-suppressions"])
        assert result.exit_code == 0
        assert "NO FIX" in result.output
        assert "1 suppression(s), 0 fix(es)" in result.output

    @patch("open_workspace_builder.security.suppression_monitor.check_all_suppressions")
    def test_text_output_fix_available(self, mock_check: MagicMock, runner: CliRunner) -> None:
        mock_check.return_value = [
            SuppressionStatus(
                suppression=Suppression(
                    cve="CVE-2026-4539",
                    package="pygments",
                    suppressed_date="2026-03-24",
                    reason="test",
                    pinned_version="2.19.2",
                    ci_flag="--ignore-vuln CVE-2026-4539",
                ),
                fix_available=True,
                fixed_version="2.20.0",
                current_version="2.19.2",
                days_suppressed=30,
            )
        ]
        result = runner.invoke(owb, ["audit", "check-suppressions"])
        assert result.exit_code == 1
        assert "FIX AVAILABLE: 2.20.0" in result.output
        assert "Action: upgrade" in result.output

    @patch("open_workspace_builder.security.suppression_monitor.check_all_suppressions")
    def test_json_output(self, mock_check: MagicMock, runner: CliRunner) -> None:
        mock_check.return_value = [
            SuppressionStatus(
                suppression=Suppression(
                    cve="CVE-2026-4539",
                    package="pygments",
                    suppressed_date="2026-03-24",
                    reason="test",
                    pinned_version="2.19.2",
                ),
                fix_available=False,
                fixed_version=None,
                current_version="2.19.2",
                days_suppressed=1,
            )
        ]
        result = runner.invoke(owb, ["audit", "check-suppressions", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["cve"] == "CVE-2026-4539"
        assert data[0]["fix_available"] is False

    def test_missing_registry(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(
            owb,
            ["audit", "check-suppressions", "--registry", str(tmp_path / "nope.yaml")],
        )
        assert result.exit_code != 0


# ── S143 HTTP read size cap ─────────────────────────────────────────────


class TestOsvQueryHttpCap:
    """OWB-S143. _query_osv must cap response reads so a compromised
    or spoofed OSV endpoint cannot exhaust memory."""

    def test_oversize_raises_fetch_error(self) -> None:
        from open_workspace_builder.security.suppression_monitor import (
            MAX_OSV_BYTES,
            FetchError,
            _query_osv,
        )

        oversize = b"{" + (b"x" * (MAX_OSV_BYTES + 10)) + b"}"
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.side_effect = lambda n=-1: oversize if n == -1 else oversize[:n]

        with patch(
            "open_workspace_builder.security.suppression_monitor.urllib.request.urlopen",
            return_value=mock_resp,
        ):
            with pytest.raises(FetchError) as excinfo:
                _query_osv("CVE-2024-0001")

        assert "1048576" in str(excinfo.value) or str(MAX_OSV_BYTES) in str(excinfo.value)
        assert "CVE-2024-0001" in str(excinfo.value) or "osv.dev" in str(excinfo.value)

    def test_small_payload_parses(self) -> None:
        from open_workspace_builder.security.suppression_monitor import _query_osv

        payload = json.dumps({"id": "CVE-2024-0001", "affected": []}).encode()
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = payload

        with patch(
            "open_workspace_builder.security.suppression_monitor.urllib.request.urlopen",
            return_value=mock_resp,
        ):
            result = _query_osv("CVE-2024-0001")

        assert result["id"] == "CVE-2024-0001"

    def test_custom_cap_honoured(self) -> None:
        from open_workspace_builder.security.suppression_monitor import (
            FetchError,
            _query_osv,
        )

        payload = json.dumps({"id": "X", "junk": "x" * 200}).encode()
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.side_effect = lambda n=-1: payload if n == -1 else payload[:n]

        with patch(
            "open_workspace_builder.security.suppression_monitor.urllib.request.urlopen",
            return_value=mock_resp,
        ):
            with pytest.raises(FetchError):
                _query_osv("X", max_bytes=50)
