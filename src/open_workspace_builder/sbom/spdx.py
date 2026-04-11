"""OWB-S107c — Hand-rolled SPDX 2.3 JSON emitter.

Maps internal :class:`~open_workspace_builder.sbom.discover.Component`
records to a SPDX 2.3 JSON document. No new third-party dependency:
adding ``spdx-tools`` would trigger the license / OSS health / 7-day
supply-chain gates for marginal benefit (we only need write-side support
and only the ``packages`` slice of the spec).

SPDX 2.3 spec: https://spdx.github.io/spdx-spec/v2.3/

Field mapping (from the S107c story):

| OWB internal           | SPDX 2.3 field                              |
|------------------------|---------------------------------------------|
| Component.name         | packages[].name                             |
| Component.version      | packages[].versionInfo                      |
| Component.bom_ref      | packages[].SPDXID  (sanitized to SPDXRef-*) |
| Component.content_hash | packages[].checksums[] (algorithm SHA256)   |
| license.spdx_id        | packages[].licenseConcluded                 |
| license.custom_name    | packages[].licenseDeclared (LicenseRef-*)   |
| Provenance.source      | packages[].downloadLocation                 |
| Provenance.commit      | packages[].sourceInfo  (commit:<sha>)       |
| Capability.*           | packages[].annotations[]                    |

Round-trip is **not** required. SPDX is a write-only output format here.
CycloneDX 1.6 remains the canonical internal format.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Iterable

from open_workspace_builder.sbom.capability import Capability
from open_workspace_builder.sbom.discover import Component
from open_workspace_builder.sbom.license import LicenseEntry
from open_workspace_builder.sbom.provenance import Provenance

SPDX_VERSION = "SPDX-2.3"
SPDX_DATA_LICENSE = "CC0-1.0"
SPDX_DOCUMENT_ID = "SPDXRef-DOCUMENT"
SPDX_DOCUMENT_NAMESPACE_PREFIX = "https://owb.dev/sbom/spdx/"

_SPDX_ID_BAD_CHARS = re.compile(r"[^A-Za-z0-9.\-]+")


def serialize_spdx(
    components: Iterable[Component],
    *,
    document_name: str = "owb-workspace-sbom",
    serial: str | None = None,
    timestamp: str | None = None,
) -> str:
    """Render an iterable of internal Components as an SPDX 2.3 JSON string.

    Args:
        components: Discovered components from
            :func:`open_workspace_builder.sbom.discover.discover_components`.
        document_name: Document-level name. Defaults to a generic value.
        serial: Optional fixed namespace suffix for byte-stable output.
            If omitted, a UTC timestamp is used.
        timestamp: Optional fixed creation timestamp for byte-stable
            output. ISO 8601, e.g. ``2026-04-11T00:00:00Z``.

    Returns:
        A JSON string formatted with two-space indent and stable key order.
    """
    document = build_spdx_document(
        components,
        document_name=document_name,
        serial=serial,
        timestamp=timestamp,
    )
    return json.dumps(document, indent=2, sort_keys=True)


def build_spdx_document(
    components: Iterable[Component],
    *,
    document_name: str = "owb-workspace-sbom",
    serial: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build the SPDX 2.3 dict before serialization.

    Exposed separately so tests can introspect the structure without
    having to parse a JSON round-trip.
    """
    created = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    namespace_suffix = serial or created
    document_namespace = f"{SPDX_DOCUMENT_NAMESPACE_PREFIX}{namespace_suffix}"

    packages = [_component_to_spdx_package(c, created=created) for c in components]

    return {
        "spdxVersion": SPDX_VERSION,
        "dataLicense": SPDX_DATA_LICENSE,
        "SPDXID": SPDX_DOCUMENT_ID,
        "name": document_name,
        "documentNamespace": document_namespace,
        "creationInfo": {
            "created": created,
            "creators": ["Tool: open-workspace-builder"],
        },
        "packages": packages,
    }


# ---------------------------------------------------------------------------
# Per-component mapping
# ---------------------------------------------------------------------------


def _component_to_spdx_package(component: Component, *, created: str) -> dict[str, Any]:
    spdx_id = sanitize_spdx_id(component.bom_ref)
    package: dict[str, Any] = {
        "SPDXID": spdx_id,
        "name": component.name,
        "versionInfo": component.version,
        "downloadLocation": _download_location(component.provenance),
        "filesAnalyzed": False,
        "checksums": [
            {
                "algorithm": "SHA256",
                "checksumValue": _hash_hex(component.content_hash),
            }
        ],
    }

    license_concluded, license_declared = _spdx_license_fields(component.license)
    package["licenseConcluded"] = license_concluded
    package["licenseDeclared"] = license_declared

    source_info = _source_info(component.provenance)
    if source_info is not None:
        package["sourceInfo"] = source_info

    annotations = _capability_annotations(component.capabilities, created=created)
    if annotations:
        package["annotations"] = annotations

    return package


_SPDX_ID_HYPHEN_RUN = re.compile(r"-{2,}")


def sanitize_spdx_id(bom_ref: str) -> str:
    """Convert a free-form bom-ref to a valid SPDX identifier.

    SPDX IDs must match ``SPDXRef-[A-Za-z0-9.\\-]+``. We map any other
    character (``:`` ``/`` ``@`` ``+``) to ``-``, collapse runs of
    consecutive hyphens, strip leading / trailing hyphens, and prefix
    with ``SPDXRef-``.
    """
    if not bom_ref:
        return "SPDXRef-unknown"
    cleaned = _SPDX_ID_BAD_CHARS.sub("-", bom_ref)
    cleaned = _SPDX_ID_HYPHEN_RUN.sub("-", cleaned)
    cleaned = cleaned.strip("-") or "unknown"
    return f"SPDXRef-{cleaned}"


def _hash_hex(content_hash: str) -> str:
    """Strip the ``sha256-norm1:`` prefix from an OWB content hash."""
    return content_hash.rsplit(":", 1)[-1]


def _download_location(provenance: Provenance | None) -> str:
    """Map provenance source to SPDX downloadLocation.

    SPDX requires this field; ``NOASSERTION`` is the spec-blessed value
    when unknown.
    """
    if provenance is None or not provenance.source or provenance.source == "local-git":
        return "NOASSERTION"
    return provenance.source


def _source_info(provenance: Provenance | None) -> str | None:
    """Encode commit SHA into the optional sourceInfo field."""
    if provenance is None:
        return None
    parts: list[str] = []
    if provenance.commit:
        parts.append(f"commit:{provenance.commit}")
    if provenance.added_at:
        parts.append(f"added-at:{provenance.added_at}")
    if not parts:
        return None
    return " ".join(parts)


def _spdx_license_fields(entry: LicenseEntry | None) -> tuple[str, str]:
    """Return ``(licenseConcluded, licenseDeclared)`` for a component.

    SPDX requires both fields. Use ``NOASSERTION`` when nothing is known.
    Custom (non-SPDX) licenses are encoded as ``LicenseRef-OWB-Custom``.
    """
    if entry is None:
        return ("NOASSERTION", "NOASSERTION")
    if entry.spdx_id is not None:
        return (entry.spdx_id, entry.spdx_id)
    if entry.custom_name is not None:
        ref = "LicenseRef-OWB-Custom"
        return (ref, ref)
    return ("NOASSERTION", "NOASSERTION")


def _capability_annotations(
    capabilities: tuple[Capability, ...], *, created: str
) -> list[dict[str, str]]:
    """Render declared capabilities as SPDX annotations.

    Annotations are the spec-blessed extension surface for tool-emitted
    metadata. Each declared capability becomes one annotation with a
    fixed annotator and a structured comment.

    The annotation date is taken from the document's resolved ``created``
    field so that two SBOM emissions with the same ``timestamp=`` argument
    are byte-stable end-to-end (including the annotations block).
    """
    out: list[dict[str, str]] = []
    for cap in capabilities:
        out.append(
            {
                "annotator": "Tool: open-workspace-builder",
                "annotationDate": created,
                "annotationType": "OTHER",
                "comment": f"owb:capability:{cap.kind.value}:{cap.value}",
            }
        )
    return out
