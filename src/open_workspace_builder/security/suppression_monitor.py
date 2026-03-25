"""CVE suppression monitoring via OSV API.

Checks whether upstream fixes have landed for suppressed CVEs so the
suppression can be lifted and the dependency upgraded.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from open_workspace_builder.security.suppressions_schema import (
    Suppression,
    load_suppressions,
)


@dataclass(frozen=True)
class SuppressionStatus:
    """Result of checking a single suppression against OSV."""

    suppression: Suppression
    fix_available: bool
    fixed_version: str | None
    current_version: str | None
    days_suppressed: int
    error: str | None = None


def _get_current_version(package: str) -> str | None:
    """Get the currently installed version of a package."""
    try:
        from importlib.metadata import version

        return version(package)
    except Exception:  # noqa: BLE001
        return None


def _query_osv(cve: str) -> dict:
    """Query the OSV API for a specific vulnerability.

    Raises
    ------
    urllib.error.URLError
        On network failure.
    json.JSONDecodeError
        On malformed response.
    """
    url = f"https://api.osv.dev/v1/vulns/{cve}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _find_fix_version(osv_data: dict, package: str) -> str | None:
    """Extract the fixed version from an OSV response for a specific PyPI package."""
    for affected in osv_data.get("affected", []):
        pkg = affected.get("package", {})
        if pkg.get("ecosystem", "").lower() != "pypi":
            continue
        if pkg.get("name", "").lower() != package.lower():
            continue

        for rng in affected.get("ranges", []):
            for event in rng.get("events", []):
                fixed = event.get("fixed")
                if fixed:
                    return str(fixed)

    return None


def _days_since(date_str: str) -> int:
    """Calculate days between a date string (YYYY-MM-DD) and today."""
    try:
        suppressed = date.fromisoformat(date_str)
        return (date.today() - suppressed).days
    except (ValueError, TypeError):
        return 0


def check_suppression(suppression: Suppression) -> SuppressionStatus:
    """Query OSV API for a single CVE and determine if a fix is available."""
    current_version = _get_current_version(suppression.package)
    days = _days_since(suppression.suppressed_date)

    try:
        osv_data = _query_osv(suppression.cve)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return SuppressionStatus(
                suppression=suppression,
                fix_available=False,
                fixed_version=None,
                current_version=current_version,
                days_suppressed=days,
                error=f"CVE {suppression.cve} not found in OSV database",
            )
        return SuppressionStatus(
            suppression=suppression,
            fix_available=False,
            fixed_version=None,
            current_version=current_version,
            days_suppressed=days,
            error=f"HTTP {exc.code}: {exc.reason}",
        )
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        return SuppressionStatus(
            suppression=suppression,
            fix_available=False,
            fixed_version=None,
            current_version=current_version,
            days_suppressed=days,
            error=str(exc),
        )

    fixed_version = _find_fix_version(osv_data, suppression.package)

    return SuppressionStatus(
        suppression=suppression,
        fix_available=fixed_version is not None,
        fixed_version=fixed_version,
        current_version=current_version,
        days_suppressed=days,
    )


def check_all_suppressions(path: Path | None = None) -> list[SuppressionStatus]:
    """Load the suppression registry and check each entry against OSV."""
    suppressions = load_suppressions(path)
    return [check_suppression(s) for s in suppressions]
