"""OWB-S107c — Structural diff between two CycloneDX 1.6 SBOMs.

Joins components by ``bom-ref`` and compares the fields the OWB SBOM cares
about: content hash, license, capability set, and provenance source/commit.
The output is a stable JSON shape (or a human-readable text summary) so
``owb sbom diff`` is suitable for both CI gating and operator inspection.

Exit-code semantics (mirrored by the CLI wrapper):

- ``0`` — no differences (both BOMs equivalent on the compared fields)
- ``1`` — read or parse error (raised as exceptions, mapped to 1 by the CLI)
- ``2`` — differences present
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldChange:
    """One field-level delta on a single component."""

    field: str
    old: Any
    new: Any


@dataclass(frozen=True)
class ChangedComponent:
    """A component present in both BOMs but with at least one differing field."""

    bom_ref: str
    changes: tuple[FieldChange, ...]


@dataclass(frozen=True)
class DiffResult:
    """The full diff between two SBOMs.

    ``unchanged_count`` is reported but unchanged components are never
    enumerated by default to keep diffs scannable on real workspaces.
    """

    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    changed: tuple[ChangedComponent, ...] = ()
    unchanged_count: int = 0

    @property
    def has_differences(self) -> bool:
        return bool(self.added or self.removed or self.changed)


# ---------------------------------------------------------------------------
# Comparable component view
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ComparableComponent:
    """Subset of a CycloneDX component used for diffing.

    Anything not in this view is intentionally invisible to ``owb sbom diff``
    so that fields like serial-number, timestamp, and tool versions never
    show up as drift.
    """

    bom_ref: str
    content_hash: str | None
    licenses: tuple[str, ...]
    capabilities: tuple[str, ...]
    provenance_source: str | None
    provenance_commit: str | None
    name: str | None
    version: str | None
    kind: str | None

    @classmethod
    def from_cdx_component(cls, raw: Mapping[str, Any]) -> "_ComparableComponent":
        bom_ref = str(raw.get("bom-ref") or "")
        content_hash = _first_hash_content(raw.get("hashes") or [])
        licenses = tuple(sorted(_extract_license_ids(raw.get("licenses") or [])))
        capabilities = tuple(sorted(_extract_capability_keys(raw.get("properties") or [])))
        provenance_source = _property_value(raw.get("properties") or [], "owb:provenance:source")
        provenance_commit = _property_value(raw.get("properties") or [], "owb:provenance:commit")
        name = raw.get("name")
        version = raw.get("version")
        kind = _property_value(raw.get("properties") or [], "owb:kind")
        return cls(
            bom_ref=bom_ref,
            content_hash=content_hash,
            licenses=licenses,
            capabilities=capabilities,
            provenance_source=provenance_source,
            provenance_commit=provenance_commit,
            name=name if isinstance(name, str) else None,
            version=version if isinstance(version, str) else None,
            kind=kind,
        )


def _first_hash_content(hashes: list[Any]) -> str | None:
    for h in hashes:
        if isinstance(h, dict):
            content = h.get("content")
            if isinstance(content, str):
                return content
    return None


def _extract_license_ids(licenses: list[Any]) -> list[str]:
    out: list[str] = []
    for entry in licenses:
        if not isinstance(entry, dict):
            continue
        lic = entry.get("license")
        if not isinstance(lic, dict):
            continue
        if "id" in lic and isinstance(lic["id"], str):
            out.append(lic["id"])
        elif "name" in lic and isinstance(lic["name"], str):
            out.append(f"name:{lic['name']}")
    return out


def _extract_capability_keys(properties: list[Any]) -> list[str]:
    out: list[str] = []
    for prop in properties:
        if not isinstance(prop, dict):
            continue
        name = prop.get("name")
        if (
            isinstance(name, str)
            and name.startswith("owb:capability:")
            and name != "owb:capability:warning"
        ):
            out.append(name)
    return out


def _property_value(properties: list[Any], key: str) -> str | None:
    for prop in properties:
        if isinstance(prop, dict) and prop.get("name") == key:
            value = prop.get("value")
            return value if isinstance(value, str) else None
    return None


# ---------------------------------------------------------------------------
# Top-level diff
# ---------------------------------------------------------------------------


def load_bom(path: Path) -> dict[str, Any]:
    """Load a CycloneDX 1.6 JSON SBOM from disk.

    Raises:
        FileNotFoundError: if the file does not exist.
        ValueError: if the file is not parseable JSON or not a dict at root.
    """
    if not path.is_file():
        raise FileNotFoundError(f"SBOM file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"SBOM file is not valid JSON: {path} ({exc})") from exc
    if not isinstance(data, dict):
        raise ValueError(f"SBOM root must be a JSON object: {path}")
    return data


def diff_boms(old: Mapping[str, Any], new: Mapping[str, Any]) -> DiffResult:
    """Compute a structural diff between two parsed CycloneDX SBOMs.

    Components are joined by ``bom-ref``. Differences in any of the
    comparable fields produce a ``ChangedComponent`` entry.
    """
    old_components = _index_components(old)
    new_components = _index_components(new)

    old_refs = set(old_components)
    new_refs = set(new_components)

    added = tuple(sorted(new_refs - old_refs))
    removed = tuple(sorted(old_refs - new_refs))

    changed: list[ChangedComponent] = []
    unchanged = 0
    for ref in sorted(old_refs & new_refs):
        deltas = _component_deltas(old_components[ref], new_components[ref])
        if deltas:
            changed.append(ChangedComponent(bom_ref=ref, changes=tuple(deltas)))
        else:
            unchanged += 1

    return DiffResult(
        added=added,
        removed=removed,
        changed=tuple(changed),
        unchanged_count=unchanged,
    )


def _index_components(bom: Mapping[str, Any]) -> dict[str, _ComparableComponent]:
    raw_components = bom.get("components") or []
    if not isinstance(raw_components, list):
        return {}
    out: dict[str, _ComparableComponent] = {}
    for raw in raw_components:
        if not isinstance(raw, dict):
            continue
        comparable = _ComparableComponent.from_cdx_component(raw)
        if comparable.bom_ref:
            out[comparable.bom_ref] = comparable
    return out


def _component_deltas(old: _ComparableComponent, new: _ComparableComponent) -> list[FieldChange]:
    """Compare every comparable field and return per-field deltas."""
    deltas: list[FieldChange] = []
    for field_name in (
        "content_hash",
        "licenses",
        "capabilities",
        "provenance_source",
        "provenance_commit",
    ):
        old_val = getattr(old, field_name)
        new_val = getattr(new, field_name)
        if old_val != new_val:
            deltas.append(FieldChange(field=field_name, old=old_val, new=new_val))
    return deltas


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def render_json(result: DiffResult) -> str:
    """Render a DiffResult as a stable, deterministic JSON string."""
    payload = {
        "added": list(result.added),
        "removed": list(result.removed),
        "changed": [
            {
                "bom-ref": c.bom_ref,
                "changes": [
                    {"field": ch.field, "old": _jsonable(ch.old), "new": _jsonable(ch.new)}
                    for ch in c.changes
                ],
            }
            for c in result.changed
        ],
        "unchanged_count": result.unchanged_count,
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def render_text(result: DiffResult) -> str:
    """Render a DiffResult as a one-line-per-change human summary."""
    lines: list[str] = []
    for ref in result.added:
        lines.append(f"+ added    {ref}")
    for ref in result.removed:
        lines.append(f"- removed  {ref}")
    for c in result.changed:
        for ch in c.changes:
            lines.append(
                f"~ changed  {c.bom_ref}  [{ch.field}] {_jsonable(ch.old)} -> {_jsonable(ch.new)}"
            )
    summary = (
        f"summary: +{len(result.added)} -{len(result.removed)} "
        f"~{len(result.changed)} ={result.unchanged_count}"
    )
    if lines:
        return "\n".join(lines) + "\n" + summary
    return summary


def _jsonable(value: Any) -> Any:
    if isinstance(value, tuple):
        return list(value)
    return value
