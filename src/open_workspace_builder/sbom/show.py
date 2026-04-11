"""OWB-S107c — Pretty-print an SBOM file.

Read-only inspector for the CycloneDX 1.6 JSON SBOMs produced by
``owb sbom generate``. Two modes:

- Default: one-line-per-component summary with name, version, kind,
  license, provenance type/confidence, and capability count.
- ``--component <bom-ref>``: full property and license dump for one
  component.

Two output formats: ``text`` (default) and ``json``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ComponentSummary:
    """One row of the default summary view."""

    bom_ref: str
    name: str
    version: str
    kind: str
    license: str
    provenance_type: str
    provenance_confidence: str
    capability_count: int


@dataclass(frozen=True)
class ComponentDetail:
    """The full enrichment view for a single component."""

    bom_ref: str
    name: str
    version: str
    kind: str
    content_hash: str
    licenses: tuple[str, ...]
    capabilities: tuple[str, ...]
    properties: tuple[tuple[str, str], ...]


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def summarize(bom: Mapping[str, Any]) -> tuple[ComponentSummary, ...]:
    """Build a one-row-per-component summary from a parsed SBOM."""
    rows: list[ComponentSummary] = []
    components = bom.get("components") or []
    if not isinstance(components, list):
        return ()
    for raw in components:
        if not isinstance(raw, dict):
            continue
        rows.append(_summarize_one(raw))
    return tuple(rows)


def _summarize_one(raw: Mapping[str, Any]) -> ComponentSummary:
    properties = raw.get("properties") or []
    return ComponentSummary(
        bom_ref=str(raw.get("bom-ref") or ""),
        name=str(raw.get("name") or ""),
        version=str(raw.get("version") or ""),
        kind=_property_value(properties, "owb:kind") or "",
        license=_summary_license(raw.get("licenses") or []),
        provenance_type=_property_value(properties, "owb:provenance:type") or "",
        provenance_confidence=_property_value(properties, "owb:provenance:confidence") or "",
        capability_count=_count_capabilities(properties),
    )


def _summary_license(licenses: list[Any]) -> str:
    for entry in licenses:
        if not isinstance(entry, dict):
            continue
        lic = entry.get("license")
        if not isinstance(lic, dict):
            continue
        if isinstance(lic.get("id"), str):
            return lic["id"]
        if isinstance(lic.get("name"), str):
            return lic["name"]
    return "—"


def _count_capabilities(properties: list[Any]) -> int:
    count = 0
    for prop in properties:
        if not isinstance(prop, dict):
            continue
        name = prop.get("name")
        if (
            isinstance(name, str)
            and name.startswith("owb:capability:")
            and name != "owb:capability:warning"
        ):
            count += 1
    return count


def _property_value(properties: list[Any], key: str) -> str | None:
    for prop in properties:
        if isinstance(prop, dict) and prop.get("name") == key:
            value = prop.get("value")
            if isinstance(value, str):
                return value
    return None


def render_summary_text(rows: tuple[ComponentSummary, ...]) -> str:
    """Render the summary view as a fixed-column human-readable table."""
    if not rows:
        return "(no components)"
    headers = ("KIND", "NAME", "VERSION", "LICENSE", "PROV", "CAPS", "BOM-REF")
    matrix = [headers] + [
        (
            row.kind,
            row.name,
            row.version,
            row.license,
            f"{row.provenance_type}/{row.provenance_confidence}".strip("/"),
            str(row.capability_count),
            row.bom_ref,
        )
        for row in rows
    ]
    widths = [max(len(r[i]) for r in matrix) for i in range(len(headers))]
    lines = ["  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)) for row in matrix]
    return "\n".join(lines)


def render_summary_json(rows: tuple[ComponentSummary, ...]) -> str:
    payload = [
        {
            "bom-ref": r.bom_ref,
            "name": r.name,
            "version": r.version,
            "kind": r.kind,
            "license": r.license,
            "provenance": {
                "type": r.provenance_type,
                "confidence": r.provenance_confidence,
            },
            "capability_count": r.capability_count,
        }
        for r in rows
    ]
    return json.dumps(payload, indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# Component detail
# ---------------------------------------------------------------------------


def find_component(bom: Mapping[str, Any], bom_ref: str) -> ComponentDetail | None:
    """Look up one component by bom-ref and return its full enrichment view."""
    components = bom.get("components") or []
    if not isinstance(components, list):
        return None
    for raw in components:
        if isinstance(raw, dict) and str(raw.get("bom-ref") or "") == bom_ref:
            return _detail_one(raw)
    return None


def _detail_one(raw: Mapping[str, Any]) -> ComponentDetail:
    properties = raw.get("properties") or []
    licenses = []
    for entry in raw.get("licenses") or []:
        if not isinstance(entry, dict):
            continue
        lic = entry.get("license")
        if isinstance(lic, dict):
            if isinstance(lic.get("id"), str):
                licenses.append(lic["id"])
            elif isinstance(lic.get("name"), str):
                licenses.append(f"name:{lic['name']}")
    capabilities = [
        str(prop.get("name"))
        for prop in properties
        if isinstance(prop, dict)
        and isinstance(prop.get("name"), str)
        and str(prop["name"]).startswith("owb:capability:")
        and str(prop["name"]) != "owb:capability:warning"
    ]
    prop_pairs: list[tuple[str, str]] = []
    for prop in properties:
        if not isinstance(prop, dict):
            continue
        name = prop.get("name")
        value = prop.get("value")
        if isinstance(name, str) and isinstance(value, str):
            prop_pairs.append((name, value))

    content_hash = ""
    for h in raw.get("hashes") or []:
        if isinstance(h, dict) and isinstance(h.get("content"), str):
            content_hash = h["content"]
            break

    return ComponentDetail(
        bom_ref=str(raw.get("bom-ref") or ""),
        name=str(raw.get("name") or ""),
        version=str(raw.get("version") or ""),
        kind=_property_value(properties, "owb:kind") or "",
        content_hash=content_hash,
        licenses=tuple(licenses),
        capabilities=tuple(capabilities),
        properties=tuple(prop_pairs),
    )


def render_detail_text(detail: ComponentDetail) -> str:
    lines = [
        f"bom-ref:    {detail.bom_ref}",
        f"name:       {detail.name}",
        f"version:    {detail.version}",
        f"kind:       {detail.kind}",
        f"hash:       {detail.content_hash}",
        f"licenses:   {', '.join(detail.licenses) if detail.licenses else '—'}",
        f"capabilities ({len(detail.capabilities)}):",
    ]
    for cap in detail.capabilities:
        lines.append(f"  - {cap}")
    lines.append("properties:")
    for name, value in detail.properties:
        lines.append(f"  {name} = {value}")
    return "\n".join(lines)


def render_detail_json(detail: ComponentDetail) -> str:
    payload = {
        "bom-ref": detail.bom_ref,
        "name": detail.name,
        "version": detail.version,
        "kind": detail.kind,
        "content_hash": detail.content_hash,
        "licenses": list(detail.licenses),
        "capabilities": list(detail.capabilities),
        "properties": [{"name": n, "value": v} for n, v in detail.properties],
    }
    return json.dumps(payload, indent=2, sort_keys=True)
