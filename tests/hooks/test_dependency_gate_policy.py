"""Policy tests for the dependency-gate hook: license, quarantine, npm, first-party.

Registry access is stubbed via ``_fetch_json`` so these tests never touch
the network.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

HOOK_PATH = (
    Path(__file__).parent.parent.parent
    / "src"
    / "open_workspace_builder"
    / "vendor"
    / "ecc"
    / "hooks"
    / "dependency-gate.py"
)


@pytest.fixture(scope="module")
def gate():
    spec = importlib.util.spec_from_file_location("dependency_gate_policy", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dependency_gate_policy"] = mod
    spec.loader.exec_module(mod)
    return mod


def _iso(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


# --- License evaluation ---


@pytest.mark.parametrize(
    "expression",
    [
        "MIT",
        "Apache-2.0",
        "MIT OR Apache-2.0",
        "(MIT OR GPL-3.0-only)",
        "BSD License",
        "ISC License (ISCL)",
    ],
)
def test_license_allowed(gate, expression: str) -> None:
    assert gate.evaluate_license(expression) == (True, False)


@pytest.mark.parametrize(
    "expression",
    [
        "",
        None,
        "UNKNOWN",
        "a",
        "m",
        "GPL-3.0-only",
        "AGPL-3.0",
        "MIT AND GPL-3.0-only",
        "Proprietary; see misc",
    ],
)
def test_license_rejected(gate, expression: str | None) -> None:
    """Empty, unknown, substring-only and copyleft licenses never pass."""
    assert gate.evaluate_license(expression)[0] is False


def test_license_conditional(gate) -> None:
    assert gate.evaluate_license("MPL-2.0") == (True, True)
    assert gate.evaluate_license("MPL-2.0 OR MIT") == (True, False)


def test_pypi_license_prefers_expression_then_classifiers(gate) -> None:
    assert gate._pypi_license({"license_expression": "MIT", "license": "GPL"}) == "MIT"
    info = {"license": "", "classifiers": ["License :: OSI Approved :: MIT License"]}
    assert gate._pypi_license(info) == "MIT License"
    assert gate._pypi_license({"license": "MIT License\n\nCopyright (c) someone"}) == "MIT License"


# --- PyPI quarantine ---


def _pypi(version: str, uploaded: list[str], license_expression: str = "MIT") -> dict:
    return {
        "info": {"version": version, "license_expression": license_expression},
        "releases": {version: [{"upload_time_iso_8601": t} for t in uploaded]},
    }


def test_pypi_old_release_passes(gate, monkeypatch) -> None:
    monkeypatch.setattr(gate, "_fetch_json", lambda url: _pypi("1.0", [_iso(30)]))
    assert gate._result_issue(gate.check_pypi("pkg")) is None


def test_pypi_fresh_release_blocked(gate, monkeypatch) -> None:
    monkeypatch.setattr(gate, "_fetch_json", lambda url: _pypi("1.0", [_iso(2)]))
    assert "quarantine" in gate._result_issue(gate.check_pypi("pkg"))


def test_pypi_file_added_to_old_release_restarts_clock(gate, monkeypatch) -> None:
    monkeypatch.setattr(gate, "_fetch_json", lambda url: _pypi("1.0", [_iso(90), _iso(1)]))
    assert gate.check_pypi("pkg")["quarantine_ok"] is False


def test_pypi_missing_upload_time_fails_closed(gate, monkeypatch) -> None:
    monkeypatch.setattr(gate, "_fetch_json", lambda url: _pypi("1.0", []))
    assert gate._result_issue(gate.check_pypi("pkg")) is not None


def test_pypi_empty_license_blocked(gate, monkeypatch) -> None:
    monkeypatch.setattr(
        gate, "_fetch_json", lambda url: _pypi("1.0", [_iso(30)], license_expression="")
    )
    assert "License" in gate._result_issue(gate.check_pypi("pkg"))


# --- npm ---


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("left-pad", ("left-pad", None)),
        ("left-pad@1.3.0", ("left-pad", "1.3.0")),
        ("@scope/pkg", ("@scope/pkg", None)),
        ("@scope/pkg@^2.0.0", ("@scope/pkg", "^2.0.0")),
        ("react@next", ("react", "next")),
        ("github:user/repo", None),
        ("user/repo", None),
        ("npm:alias@1.0.0", None),
    ],
)
def test_parse_npm_spec(gate, token: str, expected) -> None:
    assert gate._parse_npm_spec(token) == expected


def test_scoped_npm_packages_are_extracted(gate) -> None:
    specs = gate.extract_packages("npm install -D @types/node@20.1.0 zod")
    assert [(s.ecosystem, s.name, s.pinned_version) for s in specs] == [
        ("node", "@types/node", "20.1.0"),
        ("node", "zod", None),
    ]


@pytest.mark.parametrize(
    "command",
    ["uv tool install ruff", "pipx install ruff", "npm add zod"],
)
def test_tool_installers_are_gated(gate, command: str) -> None:
    assert len(gate.extract_packages(command)) == 1


def _npm(latest: str, published: dict[str, str], license_value="MIT") -> dict:
    return {
        "dist-tags": {"latest": latest, "next": "2.0.0-rc.1"},
        "versions": {v: {"license": license_value} for v in published},
        "time": published,
    }


def test_npm_fresh_latest_blocked(gate, monkeypatch) -> None:
    doc = _npm("1.1.0", {"1.0.0": _iso(60), "1.1.0": _iso(1), "2.0.0-rc.1": _iso(1)})
    monkeypatch.setattr(gate, "_fetch_json", lambda url: doc)
    assert gate.check_npm("pkg")["quarantine_ok"] is False
    assert gate._result_issue(gate.check_npm("pkg", "1.0.0")) is None
    assert gate.check_npm("pkg", "next")["checked_version"] == "2.0.0-rc.1"


def test_npm_license_object_and_missing(gate, monkeypatch) -> None:
    doc = _npm("1.0.0", {"1.0.0": _iso(60)}, license_value={"type": "MIT"})
    monkeypatch.setattr(gate, "_fetch_json", lambda url: doc)
    assert gate.check_npm("pkg")["license_allowed"] is True
    doc = _npm("1.0.0", {"1.0.0": _iso(60)}, license_value=None)
    monkeypatch.setattr(gate, "_fetch_json", lambda url: doc)
    assert gate.check_npm("pkg")["license_allowed"] is False


def test_npm_unknown_exact_version_errors(gate, monkeypatch) -> None:
    monkeypatch.setattr(gate, "_fetch_json", lambda url: _npm("1.0.0", {"1.0.0": _iso(60)}))
    assert gate.check_npm("pkg", "9.9.9")["error"]


# --- First-party exemption ---


def test_first_party_is_exact_name_only(gate, monkeypatch) -> None:
    monkeypatch.setattr(gate, "FIRST_PARTY_PACKAGES", frozenset({"my_pkg"}))
    assert gate.is_first_party("My.Pkg", "python") is True
    assert gate.is_first_party("my-pkg-evil", "python") is False
    assert gate.is_first_party("other", "python") is False


# --- TLS ---


def test_ssl_context_always_verifies(gate) -> None:
    import ssl

    ctx = gate._ssl_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True
