"""Tests for package quarantine enforcement and pin advancement (OWB-S089)."""

from __future__ import annotations

import json
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from open_workspace_builder.security.quarantine import (
    PinStatus,
    QuarantineConfig,
    compute_exclude_newer,
    generate_uv_toml,
    check_pin_advancements,
    record_bypass,
)


# ── compute_exclude_newer ────────────────────────────────────────────────


class TestComputeExcludeNewer:
    def test_returns_date_7_days_ago(self) -> None:
        with patch("open_workspace_builder.security.quarantine.date") as mock_date:
            mock_date.today.return_value = date(2026, 4, 1)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = compute_exclude_newer(quarantine_days=7)
        assert result == "2026-03-25"

    def test_custom_quarantine_days(self) -> None:
        with patch("open_workspace_builder.security.quarantine.date") as mock_date:
            mock_date.today.return_value = date(2026, 4, 1)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = compute_exclude_newer(quarantine_days=14)
        assert result == "2026-03-18"

    def test_returns_iso_format(self) -> None:
        result = compute_exclude_newer()
        # Must be YYYY-MM-DD format
        parts = result.split("-")
        assert len(parts) == 3
        assert len(parts[0]) == 4
        assert len(parts[1]) == 2
        assert len(parts[2]) == 2


# ── generate_uv_toml ────────────────────────────────────────────────────


class TestGenerateUvToml:
    def test_returns_dict_with_exclude_newer(self) -> None:
        with patch("open_workspace_builder.security.quarantine.date") as mock_date:
            mock_date.today.return_value = date(2026, 4, 1)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = generate_uv_toml(quarantine_days=7)
        assert result == {"exclude-newer": "2026-03-25"}

    def test_dict_structure(self) -> None:
        result = generate_uv_toml()
        assert "exclude-newer" in result
        assert isinstance(result["exclude-newer"], str)


# ── check_pin_advancements ──────────────────────────────────────────────


SAMPLE_UV_LOCK = """\
version = 1
requires-python = ">=3.10"

[[package]]
name = "click"
version = "8.1.7"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "pyyaml"
version = "6.0.1"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "open-workspace-builder"
version = "1.0.0"
source = { editable = "." }
"""


def _make_pypi_response(upload_time: str) -> bytes:
    """Build a minimal PyPI JSON API response."""
    return json.dumps(
        {"info": {"version": "8.1.7"}, "urls": [{"upload_time_iso_8601": upload_time}]}
    ).encode()


def _make_pypi_latest_response(version: str, upload_time: str) -> bytes:
    """Build a minimal PyPI JSON API response for the latest version."""
    return json.dumps(
        {
            "info": {"version": version},
            "urls": [{"upload_time_iso_8601": upload_time}],
        }
    ).encode()


class TestCheckPinAdvancements:
    def test_parses_lock_and_queries_pypi(self, tmp_path: Path) -> None:
        lock_file = tmp_path / "uv.lock"
        lock_file.write_text(SAMPLE_UV_LOCK, encoding="utf-8")

        # click 8.1.7 was published 30 days ago; latest is 8.1.8 published 10 days ago
        # pyyaml 6.0.1 was published 30 days ago; latest is still 6.0.1 (no advancement)
        ref_date = date(2026, 4, 1)
        old_date = (ref_date - timedelta(days=30)).isoformat() + "T00:00:00Z"
        newer_date = (ref_date - timedelta(days=10)).isoformat() + "T00:00:00Z"

        def mock_urlopen(req: urllib.request.Request, **kwargs: object) -> MagicMock:
            url = req.full_url if hasattr(req, "full_url") else str(req)
            resp = MagicMock()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)

            if "/click/8.1.7/" in url:
                resp.read.return_value = _make_pypi_response(old_date)
            elif "/click/" in url and "/8.1.7/" not in url:
                # Latest click
                resp.read.return_value = _make_pypi_latest_response("8.1.8", newer_date)
            elif "/pyyaml/6.0.1/" in url:
                resp.read.return_value = _make_pypi_response(old_date)
            elif "/pyyaml/" in url:
                # Latest pyyaml is still 6.0.1
                resp.read.return_value = _make_pypi_latest_response("6.0.1", old_date)
            else:
                raise urllib.error.URLError(f"Unexpected URL: {url}")
            return resp

        with (
            patch("open_workspace_builder.security.quarantine.urlopen", side_effect=mock_urlopen),
            patch("open_workspace_builder.security.quarantine.date") as mock_date,
        ):
            mock_date.today.return_value = ref_date
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            results = check_pin_advancements(lock_file, quarantine_days=7)

        # Should have 2 results (skips editable packages)
        assert len(results) == 2

        click_result = next(r for r in results if r.package == "click")
        assert click_result.current_version == "8.1.7"
        assert click_result.candidate_version == "8.1.8"
        assert click_result.current_publish_date is not None

        pyyaml_result = next(r for r in results if r.package == "pyyaml")
        assert pyyaml_result.current_version == "6.0.1"
        assert pyyaml_result.candidate_version is None  # no newer version

    def test_skips_editable_packages(self, tmp_path: Path) -> None:
        lock_file = tmp_path / "uv.lock"
        lock_file.write_text(SAMPLE_UV_LOCK, encoding="utf-8")

        def mock_urlopen(req: urllib.request.Request, **kwargs: object) -> MagicMock:
            resp = MagicMock()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            resp.read.return_value = _make_pypi_response("2026-01-01T00:00:00Z")
            return resp

        with (
            patch("open_workspace_builder.security.quarantine.urlopen", side_effect=mock_urlopen),
            patch("open_workspace_builder.security.quarantine.date") as mock_date,
        ):
            mock_date.today.return_value = date(2026, 4, 1)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            results = check_pin_advancements(lock_file, quarantine_days=7)

        package_names = [r.package for r in results]
        assert "open-workspace-builder" not in package_names

    def test_handles_pypi_error_gracefully(self, tmp_path: Path) -> None:
        lock_file = tmp_path / "uv.lock"
        lock_file.write_text(SAMPLE_UV_LOCK, encoding="utf-8")

        def mock_urlopen(req: urllib.request.Request, **kwargs: object) -> MagicMock:
            raise urllib.error.URLError("Network error")

        with (
            patch("open_workspace_builder.security.quarantine.urlopen", side_effect=mock_urlopen),
            patch("open_workspace_builder.security.quarantine.date") as mock_date,
        ):
            mock_date.today.return_value = date(2026, 4, 1)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            results = check_pin_advancements(lock_file, quarantine_days=7)

        # Should still return results, but with None dates
        assert len(results) == 2
        for r in results:
            assert r.current_publish_date is None
            assert r.candidate_version is None


# ── record_bypass ────────────────────────────────────────────────────────


class TestRecordBypass:
    def test_creates_jsonl_file(self, tmp_path: Path) -> None:
        log_path = tmp_path / ".owb" / "quarantine-bypasses.jsonl"
        record_bypass("click", "8.1.7", "Urgent fix needed", log_path)

        assert log_path.exists()
        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["package"] == "click"
        assert record["version"] == "8.1.7"
        assert record["justification"] == "Urgent fix needed"
        assert "timestamp" in record

    def test_appends_to_existing_file(self, tmp_path: Path) -> None:
        log_path = tmp_path / ".owb" / "quarantine-bypasses.jsonl"
        record_bypass("click", "8.1.7", "First bypass", log_path)
        record_bypass("pyyaml", "6.0.1", "Second bypass", log_path)

        lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["package"] == "click"
        assert json.loads(lines[1])["package"] == "pyyaml"


# ── WorkspaceBuilder integration ─────────────────────────────────────────


class TestBuilderDeploysUvToml:
    def test_generates_uv_toml(self, tmp_path: Path, content_root: Path) -> None:
        from open_workspace_builder.config import Config
        from open_workspace_builder.engine.builder import WorkspaceBuilder

        target = tmp_path / "ws"
        config = Config()
        builder = WorkspaceBuilder(config, content_root)
        builder.build(target)

        uv_toml = target / "uv.toml"
        assert uv_toml.exists()
        content = uv_toml.read_text(encoding="utf-8")
        assert "exclude-newer" in content

    def test_skips_existing_uv_toml(self, tmp_path: Path, content_root: Path) -> None:
        from open_workspace_builder.config import Config
        from open_workspace_builder.engine.builder import WorkspaceBuilder

        target = tmp_path / "ws"
        target.mkdir(parents=True)
        # Pre-create uv.toml with custom content
        uv_toml = target / "uv.toml"
        uv_toml.write_text('exclude-newer = "2020-01-01"\n', encoding="utf-8")

        config = Config()
        builder = WorkspaceBuilder(config, content_root)
        builder.build(target)

        # Should not overwrite
        content = uv_toml.read_text(encoding="utf-8")
        assert "2020-01-01" in content


# ── CLI tests ────────────────────────────────────────────────────────────


class TestCLIPins:
    def test_pins_command_exists(self) -> None:
        from click.testing import CliRunner

        from open_workspace_builder.cli import owb

        runner = CliRunner()
        result = runner.invoke(owb, ["audit", "pins", "--help"])
        assert result.exit_code == 0
        assert "Check pinned dependencies" in result.output

    def test_pins_bypass_records_entry(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from open_workspace_builder.cli import owb

        runner = CliRunner()
        bypass_log = tmp_path / ".owb" / "quarantine-bypasses.jsonl"

        mock_config = QuarantineConfig(bypass_log_path=bypass_log)
        with patch(
            "open_workspace_builder.security.quarantine.QuarantineConfig",
            return_value=mock_config,
        ):
            result = runner.invoke(
                owb,
                ["audit", "pins", "--bypass", "click==8.1.7"],
                input="Urgent security fix\n",
            )
        assert result.exit_code == 0
        assert "Recorded bypass" in result.output
        assert bypass_log.exists()


# ── Frozen dataclass checks ─────────────────────────────────────────────


class TestDataclassImmutability:
    def test_quarantine_config_is_frozen(self) -> None:
        config = QuarantineConfig()
        with pytest.raises(AttributeError):
            config.quarantine_days = 14  # type: ignore[misc]

    def test_pypi_fetch_truncates_oversize(self) -> None:
        """OWB-S143. A compromised or spoofed PyPI endpoint cannot
        exhaust memory: _fetch_pypi_json reads at most max_bytes and
        returns None when the response exceeds the cap (logged as a
        FetchError-shaped short-circuit, consistent with the existing
        'any error returns None' contract)."""
        from open_workspace_builder.security.quarantine import (
            MAX_PYPI_BYTES,
            _fetch_pypi_json,
        )

        oversize = b"{" + (b"x" * (MAX_PYPI_BYTES + 10)) + b"}"

        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        # Emulate streaming: read(n) returns min(n, len(oversize)).
        mock_resp.read.side_effect = lambda n=-1: (oversize if n == -1 else oversize[:n])

        with patch(
            "open_workspace_builder.security.quarantine.urlopen",
            return_value=mock_resp,
        ):
            result = _fetch_pypi_json("click", "8.1.7")

        assert result is None
        # Assert we never read the full payload — the cap clamped us.
        # At least one read should have requested <= MAX_PYPI_BYTES+1 bytes.
        sizes = [c.args[0] for c in mock_resp.read.call_args_list if c.args]
        assert sizes, "expected read() called with a size argument"
        assert max(sizes) <= MAX_PYPI_BYTES + 1

    def test_pypi_fetch_accepts_small_payload(self) -> None:
        """Normal-sized PyPI payloads still parse correctly."""
        from open_workspace_builder.security.quarantine import _fetch_pypi_json

        payload = b'{"info": {"name": "click"}, "urls": []}'
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = payload

        with patch(
            "open_workspace_builder.security.quarantine.urlopen",
            return_value=mock_resp,
        ):
            result = _fetch_pypi_json("click", "8.1.7")

        assert result is not None
        assert result["info"]["name"] == "click"

    def test_pypi_fetch_honours_custom_cap(self) -> None:
        """Callers can override the default cap via max_bytes kwarg."""
        from open_workspace_builder.security.quarantine import _fetch_pypi_json

        payload = b'{"too":"big"}' + b"." * 500
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.side_effect = lambda n=-1: payload if n == -1 else payload[:n]

        with patch(
            "open_workspace_builder.security.quarantine.urlopen",
            return_value=mock_resp,
        ):
            # Cap of 50 bytes — payload is larger → None.
            result = _fetch_pypi_json("x", None, max_bytes=50)

        assert result is None

    def test_pin_status_is_frozen(self) -> None:
        status = PinStatus(
            package="click",
            current_version="8.1.7",
            current_publish_date=None,
            candidate_version=None,
            candidate_publish_date=None,
            scan_passed=None,
        )
        with pytest.raises(AttributeError):
            status.package = "other"  # type: ignore[misc]
