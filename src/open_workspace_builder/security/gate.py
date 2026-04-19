"""S090 — Programmatic pre-install SCA gate.

Runs a 5-check security battery against a package before installation:
1. pip-audit (known vulnerabilities)
2. GuardDog (malicious code heuristics)
3. OSS health (stub — manual review)
4. License compliance
5. Quarantine (publish-date freshness)

Each check wraps an existing OWB module. Missing tools are marked as
``passed=True, "skipped — ..."`` to avoid false negatives on machines
without optional tooling.

OWB-S142 — tool errors distinguished from tool-missing. An unexpected
exception from a wrapped tool (network blip, malformed output,
version mismatch) is a signal, not noise: an attacker who can induce
a crash would otherwise get a free pass. When ``fail_closed=True``
(default), the errored path returns ``passed=False`` with a
``"errored: <reason>"`` detail. When ``fail_closed=False``, the path
returns ``passed=True`` but still labels the detail as ``"errored
(fail_closed=false): ..."`` so the event stays visible to log grep.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

_LOG = logging.getLogger(__name__)


# ── Dataclasses ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GateCheck:
    """Result of a single gate check."""

    name: str  # "pip-audit", "guarddog", "oss-health", "license", "quarantine"
    passed: bool
    details: str


@dataclass(frozen=True)
class GateResult:
    """Consolidated result of all gate checks for a package."""

    package: str
    version: str | None
    checks: tuple[GateCheck, ...]
    passed: bool  # True only if every check passed


# ── Individual checks ───────────────────────────────────────────────────


def _errored_check(name: str, exc: BaseException, fail_closed: bool) -> GateCheck:
    """Shape a GateCheck result for the tool-errored path.

    OWB-S142 policy: unexpected exceptions from a wrapped tool are
    distinct from tool-not-installed. fail_closed=True (default)
    turns the error into a hard fail; fail_closed=False preserves
    the legacy pass-through but labels the detail with "errored" so
    log-grep still surfaces it.
    """
    reason = f"{type(exc).__name__}: {exc}"
    if fail_closed:
        return GateCheck(
            name=name,
            passed=False,
            details=f"errored: {reason}",
        )
    _LOG.warning(
        "security gate %s errored but fail_closed=false; passing through: %s",
        name,
        reason,
    )
    return GateCheck(
        name=name,
        passed=True,
        details=f"errored (fail_closed=false): {reason}",
    )


def _check_pip_audit(
    package: str,
    version: str | None,
    *,
    fail_closed: bool = True,
) -> GateCheck:
    """Check for known vulnerabilities via pip-audit.

    ImportError → skipped (tool not installed; not a security signal).
    Any other exception → respects ``fail_closed``.
    """
    try:
        from open_workspace_builder.security.dep_audit import _audit_single_vuln
    except ImportError:
        return GateCheck(
            name="pip-audit",
            passed=True,
            details="skipped — pip-audit not installed",
        )

    try:
        report = _audit_single_vuln(package, version)
    except Exception as exc:  # noqa: BLE001
        return _errored_check("pip-audit", exc, fail_closed)

    if report.findings:
        vuln_ids = ", ".join(f.vuln_id for f in report.findings)
        return GateCheck(
            name="pip-audit",
            passed=False,
            details=f"Known vulnerabilities: {vuln_ids}",
        )

    return GateCheck(
        name="pip-audit",
        passed=True,
        details="No known vulnerabilities",
    )


def _check_guarddog(package: str, *, fail_closed: bool = True) -> GateCheck:
    """Check for malicious code patterns via guarddog.

    ImportError / FileNotFoundError / RuntimeError → skipped
    (the dep_audit module treats these as "tool not installed" signals
    emitted when the guarddog binary is absent).
    Any other exception → respects ``fail_closed``.
    """
    try:
        from open_workspace_builder.security.dep_audit import audit_malicious_code
    except ImportError:
        return GateCheck(
            name="guarddog",
            passed=True,
            details="skipped — dep_audit module not available",
        )

    try:
        report = audit_malicious_code([package])
    except (RuntimeError, FileNotFoundError):
        return GateCheck(
            name="guarddog",
            passed=True,
            details="skipped — guarddog not installed",
        )
    except Exception as exc:  # noqa: BLE001
        return _errored_check("guarddog", exc, fail_closed)

    if report.flagged:
        rules = ", ".join(f.rule_name for f in report.flagged)
        return GateCheck(
            name="guarddog",
            passed=False,
            details=f"Malicious code indicators: {rules}",
        )

    return GateCheck(
        name="guarddog",
        passed=True,
        details="No malicious code detected",
    )


def _check_oss_health(package: str) -> GateCheck:
    """Stub for OSS health check.

    TODO: Wire to content/skills/oss-health-check/ when a programmatic
    interface is available. Currently returns a pass with a reminder to
    review manually.
    """
    return GateCheck(
        name="oss-health",
        passed=True,
        details="Stub — manual review recommended (run oss-health-check skill)",
    )


def _check_license(
    package: str,
    version: str | None,
    *,
    fail_closed: bool = True,
) -> GateCheck:
    """Check package license against the allowed-licenses policy.

    Missing module / missing policy file → skipped (legitimate
    unconfigured states). Audit exceptions (malformed policy,
    parse failure) → respects ``fail_closed``.
    """
    try:
        from open_workspace_builder.security.license_audit import (
            audit_licenses,
        )
    except ImportError:
        return GateCheck(
            name="license",
            passed=True,
            details="skipped — license_audit module not available",
        )

    policy_path = _find_license_policy()
    if policy_path is None:
        return GateCheck(
            name="license",
            passed=True,
            details="skipped — allowed-licenses.md not found",
        )

    # Build synthetic dep data for the single package
    dep_data = [
        {
            "Name": package,
            "Version": version or "unknown",
            "License": _lookup_package_license(package),
        }
    ]

    try:
        report = audit_licenses(policy_path, dep_data=dep_data)
    except (ValueError, RuntimeError) as exc:
        return _errored_check("license", exc, fail_closed)

    failures = [f for f in report.findings if f.status in ("fail", "unknown")]
    if failures:
        detail_parts = [f"{f.license_name} ({f.status})" for f in failures]
        return GateCheck(
            name="license",
            passed=False,
            details=f"License issues: {', '.join(detail_parts)}",
        )

    return GateCheck(
        name="license",
        passed=True,
        details="License allowed",
    )


def _check_quarantine(
    package: str,
    version: str | None,
    days: int,
    *,
    fail_closed: bool = True,
) -> GateCheck:
    """Check if the package version was published within the quarantine window.

    Uses the quarantine module from S089 when available.
    Module absent → skipped. Runtime exception (e.g. PyPI JSON
    unreachable) → respects ``fail_closed``.
    """
    try:
        from open_workspace_builder.security.quarantine import check_quarantine_age
    except (ImportError, AttributeError):
        # S089 quarantine module not yet merged, or `check_quarantine_age`
        # symbol absent under a future refactor — degrade to a "skipped"
        # rather than swallowing a real runtime failure below.
        return GateCheck(
            name="quarantine",
            passed=True,
            details=f"skipped — quarantine module not available (requires {days}-day check)",
        )

    try:
        result = check_quarantine_age(package, version, quarantine_days=days)
    except Exception as exc:  # noqa: BLE001
        return _errored_check("quarantine", exc, fail_closed)

    if result.get("quarantined", False):
        return GateCheck(
            name="quarantine",
            passed=False,
            details=f"Package published within {days}-day quarantine window",
        )
    return GateCheck(
        name="quarantine",
        passed=True,
        details=f"Published outside {days}-day quarantine window",
    )


# ── Skill quarantine (S107c) ────────────────────────────────────────────


def _check_skill_quarantine(
    workspace: Path,
    days: int = 7,
    *,
    fail_closed: bool = True,
) -> GateCheck:
    """Flag AI extensions added inside the last *days* days.

    OWB-S107c. Consults the SBOM ``added_at`` provenance field for every
    skill, agent, command, and MCP server in the workspace. Wired into
    the scanner pipeline behind ``--skill-quarantine`` (default off).

    Returns ``passed=True`` with a "skipped" detail when the workspace is
    not a directory or when the quarantine module is unavailable
    (legitimate unconfigured states — a misconfigured workspace should
    not turn the gate into a hard failure). Runtime exceptions during
    the check respect ``fail_closed``.
    """
    if not workspace.is_dir():
        return GateCheck(
            name="skill-quarantine",
            passed=True,
            details=f"skipped — workspace not found: {workspace}",
        )

    try:
        from open_workspace_builder.sbom.quarantine import check_workspace_quarantine
    except ImportError:
        return GateCheck(
            name="skill-quarantine",
            passed=True,
            details="skipped — sbom.quarantine module unavailable",
        )

    try:
        report = check_workspace_quarantine(workspace=workspace, days=days)
    except Exception as exc:  # noqa: BLE001
        return _errored_check("skill-quarantine", exc, fail_closed)

    if report.has_quarantined:
        names = ", ".join(q.name for q in report.quarantined[:5])
        more = "" if len(report.quarantined) <= 5 else f" (+{len(report.quarantined) - 5} more)"
        return GateCheck(
            name="skill-quarantine",
            passed=False,
            details=(
                f"{len(report.quarantined)} of {report.total_components} "
                f"AI extensions inside the {days}-day quarantine window: "
                f"{names}{more}"
            ),
        )

    return GateCheck(
        name="skill-quarantine",
        passed=True,
        details=(
            f"0 of {report.total_components} AI extensions inside the {days}-day quarantine window"
        ),
    )


# ── Helpers ─────────────────────────────────────────────────────────────


def _find_license_policy() -> Path | None:
    """Locate the allowed-licenses policy file."""
    candidates = [
        Path("content/policies/allowed-licenses.md"),
        Path("Obsidian/code/allowed-licenses.md"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _lookup_package_license(package: str) -> str:
    """Look up a package's license from installed metadata.

    Returns "Unknown" if the package is not installed or license is unset.
    """
    try:
        from importlib.metadata import metadata

        meta = metadata(package)
        license_val = meta.get("License", "")
        if license_val and license_val.lower() != "unknown":
            return license_val
        # Fall back to classifier-based license
        classifiers = meta.get_all("Classifier") or []
        for clf in classifiers:
            if clf.startswith("License ::"):
                parts = clf.split(" :: ")
                return parts[-1] if len(parts) > 1 else clf
        return "Unknown"
    except Exception:  # noqa: BLE001
        return "Unknown"


def _record_gate_failure(
    result: GateResult,
    ledger_path: Path | None,
) -> None:
    """Record failed gate checks in the reputation ledger."""
    from open_workspace_builder.security.reputation import FlagEvent, ReputationLedger

    path = ledger_path or Path("~/.owb/reputation-ledger.jsonl")
    ledger = ReputationLedger(path)

    failed_checks = [c for c in result.checks if not c.passed]
    details = "; ".join(f"{c.name}: {c.details}" for c in failed_checks)
    pkg_label = f"{result.package}=={result.version}" if result.version else result.package

    event = FlagEvent.now(
        source="sca-gate",
        file_path=pkg_label,
        flag_category="sca-gate-failure",
        severity="high",
        disposition="unreviewed",
        details=details,
    )
    ledger.record_event(event)


def _parse_direct_deps() -> list[str]:
    """Parse direct dependencies from pyproject.toml in the current directory.

    Returns a list of package names (without version specifiers).
    """
    pyproject = Path("pyproject.toml")
    if not pyproject.is_file():
        raise FileNotFoundError("pyproject.toml not found in current directory")

    content = pyproject.read_text(encoding="utf-8")

    # Extract the dependencies array from [project] section
    match = re.search(
        r"^\s*dependencies\s*=\s*\[(.*?)\]",
        content,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        return []

    raw = match.group(1)
    deps: list[str] = []
    for line in raw.splitlines():
        line = line.strip().strip(",").strip('"').strip("'").strip()
        if not line or line.startswith("#"):
            continue
        # Strip version specifier: "click>=8.0" → "click"
        name = re.split(r"[><=!~;\[]", line)[0].strip()
        if name:
            deps.append(name)

    return deps


# ── Public API ──────────────────────────────────────────────────────────


def run_gate(
    package: str,
    version: str | None = None,
    quarantine_days: int = 7,
    ledger_path: Path | None = None,
    *,
    fail_closed: bool = True,
) -> GateResult:
    """Run the full pre-install scan battery against a package.

    Parameters
    ----------
    package:
        PyPI package name.
    version:
        Optional version to check.
    quarantine_days:
        Number of days for the quarantine window (default 7).
    ledger_path:
        Optional path for the reputation ledger (for testing).
    fail_closed:
        OWB-S142. When True (default), an unexpected exception raised
        by a wrapped tool (pip-audit, guarddog, license audit,
        quarantine) produces a hard fail. When False, the errored
        path still passes but the detail string is labelled
        ``"errored (fail_closed=false): ..."``. Threaded from
        :class:`SecurityConfig.fail_closed` at the CLI layer.
    """
    checks = (
        _check_pip_audit(package, version, fail_closed=fail_closed),
        _check_guarddog(package, fail_closed=fail_closed),
        _check_oss_health(package),
        _check_license(package, version, fail_closed=fail_closed),
        _check_quarantine(package, version, quarantine_days, fail_closed=fail_closed),
    )

    all_passed = all(c.passed for c in checks)

    result = GateResult(
        package=package,
        version=version,
        checks=checks,
        passed=all_passed,
    )

    if not all_passed:
        _record_gate_failure(result, ledger_path)

    return result


def run_gate_batch(
    packages: list[str],
    *,
    fail_closed: bool = True,
) -> list[GateResult]:
    """Run gate checks for all packages in the list."""
    return [run_gate(pkg, fail_closed=fail_closed) for pkg in packages]
