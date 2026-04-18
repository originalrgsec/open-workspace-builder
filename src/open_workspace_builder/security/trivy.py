"""Trivy multi-ecosystem vulnerability scanner integration (OWB-S091).

Shells out to the ``trivy`` CLI binary. Trivy is a Go binary installed
separately (e.g. ``brew install trivy``), NOT a Python package.

Version 0.69.3 is the last known-safe release. Versions 0.69.4 through
0.69.6 are compromised and will be blocked.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

SAFE_VERSION = "0.69.3"
COMPROMISED_VERSIONS = ("0.69.4", "0.69.5", "0.69.6")

_VERSION_PATTERN = re.compile(r"(\d+\.\d+\.\d+)")


@dataclass(frozen=True)
class TrivyFinding:
    """A single vulnerability finding from Trivy."""

    vulnerability_id: str
    package_name: str
    installed_version: str
    fixed_version: str | None
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW, UNKNOWN
    title: str
    ecosystem: str  # npm, pip, gomod, cargo, etc.


@dataclass(frozen=True)
class TrivyScanResult:
    """Aggregated Trivy scan results."""

    findings: tuple[TrivyFinding, ...]
    target: str
    trivy_version: str
    ecosystems_scanned: tuple[str, ...]


def is_available() -> bool:
    """Check if the trivy binary exists on PATH."""
    return shutil.which("trivy") is not None


def get_version() -> str | None:
    """Get the installed trivy version string, or None if not installed."""
    try:
        result = subprocess.run(
            ["trivy", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    match = _VERSION_PATTERN.search(result.stdout)
    return match.group(1) if match else None


def check_version_safety(version: str) -> tuple[bool, str]:
    """Return (is_safe, message). Blocks compromised versions.

    Versions 0.69.4 through 0.69.6 contained a supply-chain compromise.
    All other versions (older or newer) are considered safe.
    """
    if version in COMPROMISED_VERSIONS:
        return (
            False,
            f"Trivy {version} is compromised (CVE in versions "
            f"{', '.join(COMPROMISED_VERSIONS)}). "
            f"Blocked for safety. Downgrade to {SAFE_VERSION} or upgrade "
            f"past {COMPROMISED_VERSIONS[-1]}. "
            f"See: https://github.com/aquasecurity/trivy/security/advisories",
        )
    return (True, f"Trivy {version} OK — not in compromised range.")


def scan_filesystem(
    path: Path,
    *,
    severity_filter: str = "CRITICAL,HIGH",
    timeout: int = 300,
) -> TrivyScanResult:
    """Run ``trivy fs --scanners vuln`` on a path and return parsed results.

    Raises
    ------
    ImportError
        If the trivy binary is not installed.
    RuntimeError
        If the installed version is compromised or the scan fails.
    """
    if not is_available():
        raise ImportError("Trivy is not installed. Install it with: brew install trivy")

    version = get_version()
    if version is None:
        raise RuntimeError("Could not determine Trivy version.")

    is_safe, msg = check_version_safety(version)
    if not is_safe:
        raise RuntimeError(msg)

    cmd = [
        "trivy",
        "fs",
        "--scanners",
        "vuln",
        "--format",
        "json",
        "--severity",
        severity_filter,
        str(path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Trivy scan timed out after {timeout}s") from exc

    raw = json.loads(result.stdout) if result.stdout else {}
    findings = parse_trivy_json(raw)
    ecosystems = _extract_ecosystems(raw)

    return TrivyScanResult(
        findings=findings,
        target=str(path),
        trivy_version=version,
        ecosystems_scanned=ecosystems,
    )


def parse_trivy_json(raw: dict) -> tuple[TrivyFinding, ...]:
    """Parse Trivy JSON output into a tuple of findings."""
    findings: list[TrivyFinding] = []
    for target_result in raw.get("Results", []):
        ecosystem = target_result.get("Type", "unknown")
        vulns = target_result.get("Vulnerabilities") or []
        for vuln in vulns:
            fixed = vuln.get("FixedVersion", "") or ""
            findings.append(
                TrivyFinding(
                    vulnerability_id=vuln.get("VulnerabilityID", "UNKNOWN"),
                    package_name=vuln.get("PkgName", "unknown"),
                    installed_version=vuln.get("InstalledVersion", "unknown"),
                    fixed_version=fixed if fixed else None,
                    severity=vuln.get("Severity", "UNKNOWN").upper(),
                    title=vuln.get("Title", ""),
                    ecosystem=ecosystem,
                )
            )
    return tuple(findings)


def _extract_ecosystems(raw: dict) -> tuple[str, ...]:
    """Extract unique ecosystem types from Trivy JSON output."""
    ecosystems: set[str] = set()
    for target_result in raw.get("Results", []):
        eco = target_result.get("Type")
        if eco:
            ecosystems.add(eco)
    return tuple(sorted(ecosystems))
