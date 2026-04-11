"""OWB-S107c — AI extension quarantine via SBOM ``added_at`` field.

The S089 quarantine module guards Python *packages* by publish date.
S107c extends the same supply-chain hygiene to AI extensions: skills,
agents, slash commands, and MCP servers. A component is "quarantined" if
its provenance ``added_at`` falls within the last N days (default 7).

This module is consumed by:

- ``owb sbom quarantine`` CLI subcommand (operator-facing)
- ``security/gate.py`` ``_check_skill_quarantine`` (scanner pipeline,
  opt-in via ``--skill-quarantine`` flag, default off until a future
  deprecation cycle).

The window check is intentionally separate from the SBOM build so callers
that already have an SBOM (e.g. CI artifacts) can pass it in directly
without re-walking the workspace.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping

from open_workspace_builder.sbom.builder import build_bom, serialize_bom
from open_workspace_builder.sbom.discover import discover_components

DEFAULT_QUARANTINE_DAYS = 7


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QuarantinedComponent:
    """One AI extension flagged for being inside the quarantine window."""

    bom_ref: str
    kind: str
    name: str
    added_at: str
    age_days: int
    provenance_source: str | None


@dataclass(frozen=True)
class QuarantineReport:
    """Result of a quarantine window check."""

    days: int
    today: str
    quarantined: tuple[QuarantinedComponent, ...]
    total_components: int

    @property
    def has_quarantined(self) -> bool:
        return bool(self.quarantined)


# ---------------------------------------------------------------------------
# Window check
# ---------------------------------------------------------------------------


def check_quarantine(
    bom: Mapping[str, Any],
    *,
    days: int = DEFAULT_QUARANTINE_DAYS,
    today: date | None = None,
) -> QuarantineReport:
    """Walk an SBOM dict and report components inside the quarantine window.

    Args:
        bom: A parsed CycloneDX 1.6 SBOM dict.
        days: Quarantine window length in days. Must be >= 0.
        today: Reference date for "now" — overridable for tests.

    Returns:
        A :class:`QuarantineReport` with one entry per offending component.
    """
    if days < 0:
        raise ValueError(f"days must be >= 0 (got {days})")

    ref_today = today or date.today()
    cutoff = ref_today - timedelta(days=days)

    raw_components = bom.get("components") or []
    if not isinstance(raw_components, list):
        raw_components = []

    quarantined: list[QuarantinedComponent] = []
    total = 0
    for raw in raw_components:
        if not isinstance(raw, dict):
            continue
        total += 1

        properties = raw.get("properties") or []
        added_at = _property_value(properties, "owb:provenance:added-at")
        if added_at is None:
            continue

        added_date = _parse_iso_date(added_at)
        if added_date is None:
            continue
        if added_date < cutoff:
            continue
        if added_date > ref_today:
            # Future date — skip rather than warn (clock skew, fixture date).
            continue

        age = (ref_today - added_date).days
        quarantined.append(
            QuarantinedComponent(
                bom_ref=str(raw.get("bom-ref") or ""),
                kind=_property_value(properties, "owb:kind") or "",
                name=str(raw.get("name") or ""),
                added_at=added_at,
                age_days=age,
                provenance_source=_property_value(properties, "owb:provenance:source"),
            )
        )

    return QuarantineReport(
        days=days,
        today=ref_today.isoformat(),
        quarantined=tuple(quarantined),
        total_components=total,
    )


def check_workspace_quarantine(
    *,
    workspace: Path,
    days: int = DEFAULT_QUARANTINE_DAYS,
    today: date | None = None,
) -> QuarantineReport:
    """Generate an SBOM for a workspace in-memory and run the window check.

    Convenience wrapper used by the CLI when no pre-built SBOM is supplied.
    """
    if not workspace.is_dir():
        raise FileNotFoundError(f"Workspace not found: {workspace}")

    components = discover_components(workspace)
    bom_obj = build_bom(components)
    bom_json = serialize_bom(bom_obj)
    bom = json.loads(bom_json)
    return check_quarantine(bom, days=days, today=today)


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def render_report_text(report: QuarantineReport) -> str:
    """Render a QuarantineReport as a human-readable text block."""
    if not report.quarantined:
        return (
            f"OK — 0 of {report.total_components} components inside the "
            f"{report.days}-day quarantine window (as of {report.today})."
        )
    lines = [
        f"WARNING — {len(report.quarantined)} of {report.total_components} "
        f"components inside the {report.days}-day quarantine window "
        f"(as of {report.today}):",
        "",
    ]
    for q in report.quarantined:
        source = q.provenance_source or "—"
        lines.append(
            f"  [{q.kind}] {q.name}  (age {q.age_days}d, added {q.added_at})\n"
            f"    bom-ref: {q.bom_ref}\n"
            f"    source:  {source}"
        )
    return "\n".join(lines)


def render_report_json(report: QuarantineReport) -> str:
    """Render a QuarantineReport as a stable JSON document."""
    payload = {
        "days": report.days,
        "today": report.today,
        "total_components": report.total_components,
        "quarantined": [
            {
                "bom-ref": q.bom_ref,
                "kind": q.kind,
                "name": q.name,
                "added_at": q.added_at,
                "age_days": q.age_days,
                "provenance_source": q.provenance_source,
            }
            for q in report.quarantined
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _property_value(properties: Iterable[Any], key: str) -> str | None:
    for prop in properties:
        if isinstance(prop, dict) and prop.get("name") == key:
            value = prop.get("value")
            if isinstance(value, str):
                return value
    return None


def _parse_iso_date(text: str) -> date | None:
    """Parse a YYYY-MM-DD prefix; tolerant of full ISO 8601 inputs."""
    if not text or len(text) < 10:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
