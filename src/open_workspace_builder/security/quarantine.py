"""Package quarantine enforcement and pin advancement checking.

Implements a 7-day quarantine window for newly published packages via uv's
``exclude-newer`` directive. Provides tools to check pinned dependency versions
against PyPI publish dates and identify safe advancement candidates.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class QuarantineConfig:
    """Configuration for the quarantine enforcement system."""

    quarantine_days: int = 7
    bypass_log_path: Path = field(default_factory=lambda: Path(".owb/quarantine-bypasses.jsonl"))


@dataclass(frozen=True)
class PinStatus:
    """Status of a single pinned package regarding quarantine advancement."""

    package: str
    current_version: str
    current_publish_date: str | None
    candidate_version: str | None
    candidate_publish_date: str | None
    scan_passed: bool | None  # None = not yet scanned


def compute_exclude_newer(quarantine_days: int = 7) -> str:
    """Return ISO 8601 date string for today minus *quarantine_days*."""
    cutoff = date.today() - timedelta(days=quarantine_days)
    return cutoff.isoformat()


def generate_uv_toml(quarantine_days: int = 7) -> dict[str, str]:
    """Return uv.toml content as a dict with ``exclude-newer`` set."""
    return {"exclude-newer": compute_exclude_newer(quarantine_days)}


def render_uv_toml(quarantine_days: int = 7) -> str:
    """Return uv.toml content as a TOML-formatted string."""
    config = generate_uv_toml(quarantine_days)
    return f'exclude-newer = "{config["exclude-newer"]}"\n'


# ── Lock file parsing ────────────────────────────────────────────────────


_PACKAGE_RE = re.compile(r"^\[\[package\]\]", re.MULTILINE)
_NAME_RE = re.compile(r'^name\s*=\s*"([^"]+)"', re.MULTILINE)
_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)
_SOURCE_RE = re.compile(r"^source\s*=\s*\{([^}]+)\}", re.MULTILINE)


@dataclass(frozen=True)
class _LockEntry:
    """A single package entry parsed from uv.lock."""

    name: str
    version: str
    editable: bool


def _parse_lock(lock_text: str) -> list[_LockEntry]:
    """Parse a uv.lock file and extract package entries."""
    entries: list[_LockEntry] = []
    sections = _PACKAGE_RE.split(lock_text)

    for section in sections[1:]:  # skip preamble before first [[package]]
        name_m = _NAME_RE.search(section)
        version_m = _VERSION_RE.search(section)
        source_m = _SOURCE_RE.search(section)

        if not name_m or not version_m:
            continue

        editable = False
        if source_m and "editable" in source_m.group(1):
            editable = True

        entries.append(
            _LockEntry(
                name=name_m.group(1),
                version=version_m.group(1),
                editable=editable,
            )
        )

    return entries


# ── PyPI queries ─────────────────────────────────────────────────────────


def _fetch_pypi_json(package: str, version: str | None = None) -> dict[str, Any] | None:
    """Fetch package metadata from PyPI JSON API.

    Returns None on any network or parse error.
    """
    if version:
        url = f"https://pypi.org/pypi/{package}/{version}/json"
    else:
        url = f"https://pypi.org/pypi/{package}/json"

    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return data
    except (URLError, json.JSONDecodeError, OSError):
        return None


def _extract_publish_date(pypi_data: dict[str, Any]) -> str | None:
    """Extract the upload timestamp from a PyPI JSON response."""
    urls = pypi_data.get("urls", [])
    if urls:
        return urls[0].get("upload_time_iso_8601")
    return None


def _is_older_than(iso_timestamp: str, cutoff_date: date) -> bool:
    """Return True if the given ISO timestamp is on or before *cutoff_date*."""
    try:
        # Use datetime.date directly to avoid issues with mocked date class
        publish_date = _parse_date(iso_timestamp[:10])
        return publish_date <= cutoff_date
    except (ValueError, TypeError):
        return False


def _parse_date(iso_str: str) -> date:
    """Parse an ISO date string into a date object."""
    parts = iso_str.split("-")
    return date(int(parts[0]), int(parts[1]), int(parts[2]))


# ── Pin advancement logic ────────────────────────────────────────────────


def check_pin_advancements(
    lock_path: Path,
    quarantine_days: int = 7,
) -> list[PinStatus]:
    """Parse uv.lock and check PyPI for advancement candidates.

    A package can be safely advanced when:
    1. Its current pinned version was published more than *quarantine_days* ago.
    2. A newer version exists that was also published more than *quarantine_days* ago.
    """
    lock_text = lock_path.read_text(encoding="utf-8")
    entries = _parse_lock(lock_text)
    cutoff = date.today() - timedelta(days=quarantine_days)

    results: list[PinStatus] = []

    for entry in entries:
        if entry.editable:
            continue

        # Fetch current version info
        current_data = _fetch_pypi_json(entry.name, entry.version)
        current_publish_date = _extract_publish_date(current_data) if current_data else None

        # Fetch latest version info
        latest_data = _fetch_pypi_json(entry.name)
        candidate_version: str | None = None
        candidate_publish_date: str | None = None

        if latest_data:
            latest_version = latest_data.get("info", {}).get("version")
            if latest_version and latest_version != entry.version:
                latest_pub_date = _extract_publish_date(latest_data)
                if latest_pub_date and _is_older_than(latest_pub_date, cutoff):
                    candidate_version = latest_version
                    candidate_publish_date = latest_pub_date

        results.append(
            PinStatus(
                package=entry.name,
                current_version=entry.version,
                current_publish_date=current_publish_date,
                candidate_version=candidate_version,
                candidate_publish_date=candidate_publish_date,
                scan_passed=None,
            )
        )

    return results


# ── Bypass recording ─────────────────────────────────────────────────────


def record_bypass(
    package: str,
    version: str,
    justification: str,
    log_path: Path,
) -> None:
    """Append a quarantine bypass record to the JSONL audit log."""
    log_path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": date.today().isoformat(),
        "package": package,
        "version": version,
        "justification": justification,
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def record_cve_bypass(
    package: str,
    version: str,
    cve_ids: list[str],
    previous_exclude_newer: str,
    new_exclude_newer: str,
    log_path: Path,
) -> None:
    """Record a quarantine bypass for a CVE-motivated upgrade.

    CVE-closing updates are exempt from the quarantine policy. This function
    logs the exemption with full audit context: which CVEs drove the upgrade,
    what the quarantine date was before and after, and when it happened.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": date.today().isoformat(),
        "package": package,
        "version": version,
        "reason": "cve_exemption",
        "cve_ids": cve_ids,
        "justification": (
            f"CVE exemption: {len(cve_ids)} CVE(s) in {package} fixed in {version}. "
            f"Quarantine advanced from {previous_exclude_newer} to {new_exclude_newer}."
        ),
        "previous_exclude_newer": previous_exclude_newer,
        "new_exclude_newer": new_exclude_newer,
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


# ── CVE exemption for CI ────────────────────────────────────────────────


@dataclass(frozen=True)
class CveAuditFinding:
    """A single CVE finding from pip-audit with fix information."""

    package: str
    version: str
    vuln_id: str
    fix_version: str | None


def parse_pip_audit_json(audit_json: str) -> list[CveAuditFinding]:
    """Parse pip-audit JSON output into structured findings.

    Expected format: ``{"dependencies": [{"name": ..., "version": ...,
    "vulns": [{"id": ..., "fix_versions": [...]}]}]}``.
    """
    try:
        data = json.loads(audit_json)
    except json.JSONDecodeError:
        return []

    findings: list[CveAuditFinding] = []
    for dep in data.get("dependencies", []):
        for vuln in dep.get("vulns", []):
            fix_versions = vuln.get("fix_versions", [])
            findings.append(
                CveAuditFinding(
                    package=dep.get("name", ""),
                    version=dep.get("version", ""),
                    vuln_id=vuln.get("id", ""),
                    fix_version=fix_versions[0] if fix_versions else None,
                )
            )

    return findings


def collect_cve_exemptions(findings: list[CveAuditFinding]) -> list[str]:
    """Return vuln IDs that qualify for CVE exemption (have a fix version)."""
    return [f.vuln_id for f in findings if f.fix_version is not None]
