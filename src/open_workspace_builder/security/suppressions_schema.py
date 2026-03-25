"""CVE suppression registry schema and loader."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Suppression:
    """A single CVE suppression entry."""

    cve: str
    package: str
    suppressed_date: str
    reason: str
    pinned_version: str | None = None
    osv_id: str | None = None
    ci_flag: str | None = None


def _default_registry_path() -> Path:
    """Return the path to the bundled suppressions YAML."""
    return Path(__file__).parent / "data" / "suppressions.yaml"


def load_suppressions(path: Path | None = None) -> list[Suppression]:
    """Load and validate the suppression registry.

    Parameters
    ----------
    path:
        Path to the suppressions YAML file. Defaults to the bundled
        ``security/data/suppressions.yaml``.

    Returns
    -------
    list[Suppression]
        Validated suppression entries.

    Raises
    ------
    FileNotFoundError
        If the registry file does not exist.
    ValueError
        If a required field is missing from an entry.
    """
    effective_path = path if path is not None else _default_registry_path()
    if not effective_path.is_file():
        raise FileNotFoundError(f"Suppression registry not found: {effective_path}")

    text = effective_path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        return []

    entries = data.get("suppressions", [])
    if not isinstance(entries, list):
        return []

    result: list[Suppression] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        cve = entry.get("cve")
        package = entry.get("package")
        suppressed_date = entry.get("suppressed_date")
        reason = entry.get("reason")
        if not all([cve, package, suppressed_date, reason]):
            raise ValueError(
                f"Suppression entry missing required fields: {entry}"
            )
        result.append(
            Suppression(
                cve=str(cve),
                package=str(package),
                suppressed_date=str(suppressed_date),
                reason=str(reason),
                pinned_version=entry.get("pinned_version"),
                osv_id=entry.get("osv_id"),
                ci_flag=entry.get("ci_flag"),
            )
        )

    return result
