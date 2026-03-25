"""Dependency supply-chain scanner: known-vuln audit (pip-audit) + malicious-code detection (guarddog).

Layer A uses the pip-audit Python API to check installed packages against the OSV database.
Layer B shells out to ``uvx guarddog`` (isolated tool, not imported) and parses JSON stdout.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


# ── Dataclasses ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class VulnFinding:
    """A single known-vulnerability finding from pip-audit."""

    package: str
    installed_version: str
    vuln_id: str
    fix_version: str | None
    description: str


@dataclass(frozen=True)
class AuditReport:
    """Aggregated pip-audit results."""

    findings: tuple[VulnFinding, ...]
    skipped: tuple[str, ...]
    fix_suggestions: tuple[str, ...]


@dataclass(frozen=True)
class GuardDogFinding:
    """A single malicious-code finding from guarddog."""

    package: str
    rule_name: str
    severity: str
    file_path: str
    evidence: str


@dataclass(frozen=True)
class GuardDogReport:
    """Aggregated guarddog results."""

    flagged: tuple[GuardDogFinding, ...]
    clean: tuple[str, ...]


@dataclass(frozen=True)
class FullAuditReport:
    """Combined pip-audit + guarddog report."""

    vuln_report: AuditReport
    guarddog_report: GuardDogReport


# ── Suppressions ─────────────────────────────────────────────────────────


def _load_suppressions(path: Path | None) -> dict[str, list[str]]:
    """Load guarddog suppressions YAML.

    Returns mapping of ``{package_name: [rule_name, ...]}``.
    """
    if path is None or not path.is_file():
        return {}

    import yaml

    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        return {}

    result: dict[str, list[str]] = {}
    for entry in data.get("suppressions", []):
        if not isinstance(entry, dict):
            continue
        pkg = entry.get("package", "")
        rule = entry.get("rule", "")
        if pkg and rule:
            result.setdefault(pkg, []).append(rule)
    return result


def _default_suppressions_path() -> Path:
    """Return the path to the bundled suppressions YAML."""
    return Path(__file__).parent / "data" / "dep_audit_suppressions.yaml"


# ── Layer A: pip-audit (Python API) ──────────────────────────────────────


def audit_known_vulns(fix: bool = False) -> AuditReport:
    """Scan installed packages for known vulnerabilities via pip-audit.

    Uses the pip-audit Python API (``pip_audit._service``,
    ``pip_audit._dependency_source``) against the OSV database.

    Parameters
    ----------
    fix:
        When *True*, include fix-version suggestions in the report.
    """
    try:
        from pip_audit._dependency_source.pip import PipSource
        from pip_audit._service.interface import ResolvedDependency, SkippedDependency
        from pip_audit._service.osv import OsvService
    except ImportError as exc:
        raise ImportError(
            "pip-audit is required for vulnerability scanning. "
            "Install it with: uv pip install pip-audit"
        ) from exc

    source = PipSource()
    service = OsvService()

    findings: list[VulnFinding] = []
    skipped: list[str] = []
    fix_suggestions: list[str] = []

    for dep in source.collect():
        if isinstance(dep, SkippedDependency):
            skipped.append(dep.name)
            continue

        if not isinstance(dep, ResolvedDependency):
            continue

        dep_name = dep.name
        dep_version = str(dep.version)
        try:
            _resolved, vulns = service.query(dep)
            for vuln in vulns:
                fix_ver = str(vuln.fix_versions[0]) if vuln.fix_versions else None
                findings.append(
                    VulnFinding(
                        package=dep_name,
                        installed_version=dep_version,
                        vuln_id=str(vuln.id),
                        fix_version=fix_ver,
                        description=vuln.description,
                    )
                )
                if fix and fix_ver:
                    fix_suggestions.append(f"{dep_name}=={fix_ver}")
        except Exception:  # noqa: BLE001
            skipped.append(dep_name)

    return AuditReport(
        findings=tuple(findings),
        skipped=tuple(skipped),
        fix_suggestions=tuple(fix_suggestions),
    )


# ── Layer B: guarddog (subprocess) ───────────────────────────────────────


def _run_guarddog(package: str) -> dict:
    """Shell out to ``uvx guarddog pypi scan <package>`` and return parsed JSON."""
    env = {**os.environ, "SEMGREP_SEND_METRICS": "off"}
    try:
        proc = subprocess.run(
            ["uvx", "guarddog", "pypi", "scan", package],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "guarddog requires uvx. Install uv first: https://docs.astral.sh/uv/"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"guarddog timed out scanning {package}") from exc

    stdout = proc.stdout.strip()
    if not stdout:
        if proc.returncode != 0:
            raise RuntimeError(
                f"guarddog failed for {package} (exit {proc.returncode}): "
                f"{proc.stderr.strip()}"
            )
        return {}

    try:
        return json.loads(stdout)  # type: ignore[no-any-return]
    except json.JSONDecodeError:
        raise RuntimeError(
            f"guarddog returned non-JSON for {package}: {stdout[:200]}"
        ) from None


def _parse_guarddog_output(
    package: str,
    raw: dict,
    suppressions: dict[str, list[str]],
) -> list[GuardDogFinding]:
    """Parse guarddog JSON output into findings, applying suppressions."""
    suppressed_rules = suppressions.get(package, [])
    results: list[GuardDogFinding] = []

    for rule_name, rule_data in raw.items():
        if rule_name in ("errors", "metadata"):
            continue
        if rule_name in suppressed_rules:
            continue
        if not isinstance(rule_data, dict):
            continue

        rule_results = rule_data.get("results", [])
        if not rule_results:
            continue

        severity = _guarddog_severity(rule_data.get("score", 0))
        for hit in rule_results:
            if isinstance(hit, dict):
                file_path = hit.get("location", hit.get("file", ""))
                evidence = hit.get("code", hit.get("message", ""))
            else:
                file_path = ""
                evidence = str(hit)

            results.append(
                GuardDogFinding(
                    package=package,
                    rule_name=rule_name,
                    severity=severity,
                    file_path=str(file_path),
                    evidence=str(evidence)[:500],
                )
            )

    return results


def _guarddog_severity(score: float | int) -> str:
    """Map guarddog numeric score to severity label."""
    if score >= 0.7:
        return "critical"
    if score >= 0.4:
        return "high"
    if score >= 0.2:
        return "medium"
    return "low"


def audit_malicious_code(
    packages: list[str],
    suppressions_file: Path | None = None,
) -> GuardDogReport:
    """Scan packages for malicious code patterns using guarddog.

    Shells out to ``uvx guarddog pypi scan <package>`` for each package and
    parses the JSON output.

    Parameters
    ----------
    packages:
        Package names to scan.
    suppressions_file:
        Path to suppressions YAML for acknowledged false positives.
        Defaults to the bundled ``dep_audit_suppressions.yaml``.
    """
    effective_path = suppressions_file if suppressions_file is not None else _default_suppressions_path()
    suppressions = _load_suppressions(effective_path)
    all_flagged: list[GuardDogFinding] = []
    clean: list[str] = []

    for pkg in packages:
        raw = _run_guarddog(pkg)
        pkg_findings = _parse_guarddog_output(pkg, raw, suppressions)
        if pkg_findings:
            all_flagged.extend(pkg_findings)
        else:
            clean.append(pkg)

    return GuardDogReport(flagged=tuple(all_flagged), clean=tuple(clean))


# ── Combined scanning ────────────────────────────────────────────────────


def audit_single_package(
    name: str,
    version: str | None = None,
) -> FullAuditReport:
    """Pre-addition scan of a single package (both layers).

    Parameters
    ----------
    name:
        Package name (PyPI).
    version:
        Optional version constraint for context (guarddog scans latest from PyPI).
    """
    vuln_report = _audit_single_vuln(name, version)
    guarddog_report = audit_malicious_code([name])
    return FullAuditReport(vuln_report=vuln_report, guarddog_report=guarddog_report)


def _audit_single_vuln(name: str, version: str | None) -> AuditReport:
    """Run pip-audit filtering results for a single package."""
    try:
        full = audit_known_vulns(fix=False)
    except ImportError:
        return AuditReport(findings=(), skipped=(name,), fix_suggestions=())

    matching = tuple(f for f in full.findings if f.package.lower() == name.lower())
    return AuditReport(
        findings=matching,
        skipped=full.skipped,
        fix_suggestions=full.fix_suggestions,
    )


def run_full_audit(
    deep: bool = False,
    fix: bool = False,
    suppressions_file: Path | None = None,
) -> FullAuditReport:
    """Run both Layer A (pip-audit) and optionally Layer B (guarddog).

    Parameters
    ----------
    deep:
        When *True*, also runs guarddog on all installed packages (slow).
        When *False*, only runs pip-audit.
    fix:
        Passed through to pip-audit to include fix suggestions.
    suppressions_file:
        Path to guarddog suppressions YAML.
    """
    vuln_report = audit_known_vulns(fix=fix)

    if deep:
        packages = _installed_package_names()
        guarddog_report = audit_malicious_code(packages, suppressions_file=suppressions_file)
    else:
        guarddog_report = GuardDogReport(flagged=(), clean=())

    return FullAuditReport(vuln_report=vuln_report, guarddog_report=guarddog_report)


def _installed_package_names() -> list[str]:
    """Get list of installed package names via importlib.metadata."""
    from importlib.metadata import distributions

    return sorted(
        {dist.metadata["Name"] for dist in distributions() if dist.metadata["Name"]}
    )
