"""OWB-S107a — Build and serialize CycloneDX 1.6 SBOMs from Component records.

The standard ``hashes`` field carries the raw SHA-256 hex of the normalized
content (algorithm ``SHA-256``) so downstream SSCA tools see a clean hash.
The full tagged string ``sha256-norm1:<hex>`` plus the normalization version
is encoded in per-component properties so the SBOM is self-describing and
future-proof against normalization algorithm upgrades.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from cyclonedx.model import HashAlgorithm, HashType, Property
from cyclonedx.model.bom import Bom
from cyclonedx.model.bom_ref import BomRef
from cyclonedx.model.component import Component as CdxComponent
from cyclonedx.model.component import ComponentType
from cyclonedx.output.json import JsonV1Dot6

from open_workspace_builder.sbom.discover import Component, ComponentKind
from open_workspace_builder.sbom.normalize import NORM_VERSION

_KIND_TO_CDX_TYPE: dict[ComponentKind, ComponentType] = {
    ComponentKind.SKILL: ComponentType.LIBRARY,
    ComponentKind.AGENT: ComponentType.LIBRARY,
    ComponentKind.COMMAND: ComponentType.LIBRARY,
    ComponentKind.MCP_SERVER: ComponentType.APPLICATION,
}


@dataclass(frozen=True)
class BomOptions:
    """Deterministic overrides for BOM serialization.

    Used by tests and by the example-fixture regeneration path so that
    byte-stable output is possible. In normal CLI use, leave both ``None``
    and the CycloneDX library will pick a fresh UUID serial and the current
    timestamp.
    """

    serial: str | None = None
    timestamp: str | None = None


def build_bom(
    components: Iterable[Component],
    *,
    options: BomOptions | None = None,
) -> Bom:
    """Build a CycloneDX Bom object from our internal Component records.

    Args:
        components: The components discovered by :func:`discover_components`.
        options: Optional deterministic overrides for serial and timestamp.

    Returns:
        A :class:`cyclonedx.model.bom.Bom` populated with one CdxComponent
        per input component. Use :func:`serialize_bom` to render to JSON.
    """
    bom = Bom()
    if options is not None and options.serial is not None:
        bom.serial_number = _parse_serial(options.serial)

    for c in components:
        bom.components.add(_to_cdx_component(c))

    # Stash deterministic overrides on the bom object for serialize_bom to pick
    # up. We do this because the CycloneDX library generates the timestamp at
    # serialization time, not at Bom() construction time.
    if options is not None:
        bom._owb_options = options  # type: ignore[attr-defined]

    return bom


def serialize_bom(bom: Bom) -> str:
    """Serialize a Bom to a CycloneDX 1.6 JSON string.

    If the Bom was built with :class:`BomOptions` containing a fixed
    timestamp, the output JSON has ``metadata.timestamp`` patched to that
    value so downstream diffs are byte-stable.
    """
    import json as _json

    output = JsonV1Dot6(bom)
    json_str = output.output_as_string(indent=2)

    opts: BomOptions | None = getattr(bom, "_owb_options", None)
    if opts is None or opts.timestamp is None:
        return json_str

    data = _json.loads(json_str)
    data.setdefault("metadata", {})
    data["metadata"]["timestamp"] = opts.timestamp
    return _json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_cdx_component(c: Component) -> CdxComponent:
    """Map an internal Component to a CycloneDX Component."""
    hex_part = _extract_hex(c.content_hash)

    # cyclonedx-python-lib 9.1.0 does not expose `evidence.occurrences`, so
    # we carry the path as a property. S107b/c will migrate to the spec-native
    # location when the library is upgraded past 11.x.
    properties = [
        Property(name="owb:normalization", value=NORM_VERSION),
        Property(name="owb:kind", value=c.kind.value),
        Property(name="owb:source", value=c.source),
        Property(name="owb:content-hash", value=c.content_hash),
        Property(name="owb:evidence-path", value=c.evidence_path),
    ]

    return CdxComponent(
        type=_KIND_TO_CDX_TYPE[c.kind],
        name=c.name,
        version=c.version,
        bom_ref=BomRef(value=c.bom_ref),
        hashes=[HashType(alg=HashAlgorithm.SHA_256, content=hex_part)],
        properties=properties,
    )


def _extract_hex(tagged_hash: str) -> str:
    """Pull the raw hex portion out of a ``sha256-norm1:<hex>`` string."""
    return tagged_hash.rsplit(":", 1)[-1]


def _parse_serial(serial: str) -> "UUID":  # type: ignore[name-defined]  # noqa: F821
    """Parse a ``urn:uuid:...`` serial into a :class:`uuid.UUID`."""
    from uuid import UUID

    if serial.startswith("urn:uuid:"):
        return UUID(serial[len("urn:uuid:") :])
    return UUID(serial)
