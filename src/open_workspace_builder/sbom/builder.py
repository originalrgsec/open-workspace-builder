"""OWB-S107a / S107b — Build and serialize CycloneDX 1.6 SBOMs from Components.

The standard ``hashes`` field carries the raw SHA-256 hex of the normalized
content (algorithm ``SHA-256``) so downstream SSCA tools see a clean hash.
The full tagged string ``sha256-norm1:<hex>`` plus the normalization version
is encoded in per-component properties so the SBOM is self-describing and
future-proof against normalization algorithm upgrades.

S107b adds three enrichment surfaces emitted as CycloneDX properties /
licenses on each component:

- ``owb:provenance:*`` — type, source, commit, package, version,
  installed_at, confidence
- ``owb:capability:*`` — declared tools, mcp connections, network, exec,
  env keys, transport
- spec-native ``licenses`` field plus ``owb:license:warning`` for
  non-allowed licenses; the top-level metadata aggregates a
  ``owb:license:non-allowed-count`` property.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from cyclonedx.model import HashAlgorithm, HashType, Property
from cyclonedx.model.bom import Bom
from cyclonedx.model.bom_ref import BomRef
from cyclonedx.model.component import Component as CdxComponent
from cyclonedx.model.component import ComponentType
from cyclonedx.model.license import DisjunctiveLicense, License
from cyclonedx.output.json import JsonV1Dot6

from open_workspace_builder.sbom.capability import Capability
from open_workspace_builder.sbom.discover import Component, ComponentKind
from open_workspace_builder.sbom.license import LicenseEntry
from open_workspace_builder.sbom.normalize import NORM_VERSION
from open_workspace_builder.sbom.provenance import Provenance

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

    component_list = list(components)
    non_allowed_count = 0
    for c in component_list:
        bom.components.add(_to_cdx_component(c))
        if c.license is not None and c.license.spdx_id is not None and not c.license.allowed:
            non_allowed_count += 1
        elif c.license is not None and c.license.spdx_id is None and c.license.custom_name:
            # Custom (unrecognized) license also counts as not-allowed.
            non_allowed_count += 1

    # Top-level metadata aggregate so consumers can count non-allowed licenses
    # without re-walking every component.
    if bom.metadata is not None:
        bom.metadata.properties.add(
            Property(
                name="owb:license:non-allowed-count",
                value=str(non_allowed_count),
            )
        )

    # Stash deterministic overrides on the bom object for serialize_bom to pick
    # up. We do this because the CycloneDX library generates the timestamp at
    # serialization time, not at Bom() construction time.
    if options is not None:
        bom._owb_options = options  # type: ignore[attr-defined]

    bom._owb_non_allowed_count = non_allowed_count  # type: ignore[attr-defined]

    return bom


def count_non_allowed_licenses(bom: Bom) -> int:
    """Return the number of components with non-allowed (or custom) licenses.

    Used by the CLI to choose exit code 2 (warnings) vs 0 (clean).
    """
    return int(getattr(bom, "_owb_non_allowed_count", 0))


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
    return _json.dumps(data, indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_cdx_component(c: Component) -> CdxComponent:
    """Map an internal Component to a CycloneDX Component."""
    hex_part = _extract_hex(c.content_hash)

    # cyclonedx-python-lib 9.1.0 does not expose `evidence.occurrences`, so
    # we carry the path as a property. S107c will migrate to the spec-native
    # location when the library is upgraded past 11.x.
    properties = [
        Property(name="owb:normalization", value=NORM_VERSION),
        Property(name="owb:kind", value=c.kind.value),
        Property(name="owb:source", value=c.source),
        Property(name="owb:content-hash", value=c.content_hash),
        Property(name="owb:evidence-path", value=c.evidence_path),
    ]
    properties.extend(_provenance_properties(c.provenance))
    properties.extend(_capability_properties(c.capabilities))
    if c.license is not None and (
        c.license.spdx_id is None
        and c.license.custom_name
        or (c.license.spdx_id is not None and not c.license.allowed)
    ):
        properties.append(Property(name="owb:license:warning", value="non-allowed"))

    licenses = _cdx_licenses(c.license)

    return CdxComponent(
        type=_KIND_TO_CDX_TYPE[c.kind],
        name=c.name,
        version=c.version,
        bom_ref=BomRef(value=c.bom_ref),
        hashes=[HashType(alg=HashAlgorithm.SHA_256, content=hex_part)],
        properties=properties,
        licenses=licenses,
    )


def _provenance_properties(provenance: Provenance | None) -> list[Property]:
    """Render a Provenance record as CycloneDX properties."""
    if provenance is None:
        return []
    out: list[Property] = [
        Property(name="owb:provenance:type", value=provenance.type.value),
        Property(name="owb:provenance:confidence", value=provenance.confidence.value),
    ]
    if provenance.source:
        out.append(Property(name="owb:provenance:source", value=provenance.source))
    if provenance.commit:
        out.append(Property(name="owb:provenance:commit", value=provenance.commit))
    if provenance.package:
        out.append(Property(name="owb:provenance:package", value=provenance.package))
    if provenance.version:
        out.append(Property(name="owb:provenance:version", value=provenance.version))
    if provenance.installed_at:
        out.append(Property(name="owb:provenance:installed-at", value=provenance.installed_at))
    if provenance.added_at:
        out.append(Property(name="owb:provenance:added-at", value=provenance.added_at))
    return out


def _capability_properties(capabilities: tuple[Capability, ...]) -> list[Property]:
    """Render Capability records as CycloneDX properties.

    One property per capability with name ``owb:capability:<kind>:<value>``.
    Tool wildcards add an extra ``owb:capability:warning`` marker so the
    SBOM consumer can distinguish "declared one tool" from "declared
    everything via wildcard."
    """
    out: list[Property] = []
    for cap in capabilities:
        out.append(
            Property(
                name=f"owb:capability:{cap.kind.value}:{cap.value}",
                value="declared",
            )
        )
        if cap.warning:
            out.append(
                Property(
                    name="owb:capability:warning",
                    value=f"{cap.kind.value}:{cap.value}",
                )
            )
    return out


def _cdx_licenses(entry: LicenseEntry | None) -> list[License] | None:
    """Render a detected LicenseEntry as a CycloneDX licenses list."""
    if entry is None:
        return None
    if entry.spdx_id is not None:
        # Use DisjunctiveLicense with the SPDX id. Cyclonedx library accepts
        # SPDX expressions but the disjunctive form is more compatible with
        # downstream consumers.
        try:
            return [DisjunctiveLicense(id=entry.spdx_id)]
        except Exception:
            # Unknown SPDX id (e.g. a typo in frontmatter) — fall through to
            # the named-license form so the SBOM still records what was
            # declared instead of dropping it silently.
            return [DisjunctiveLicense(name=entry.spdx_id)]
    if entry.custom_name is not None:
        return [DisjunctiveLicense(name=entry.custom_name)]
    return None


def _extract_hex(tagged_hash: str) -> str:
    """Pull the raw hex portion out of a ``sha256-norm1:<hex>`` string."""
    return tagged_hash.rsplit(":", 1)[-1]


def _parse_serial(serial: str) -> "UUID":  # type: ignore[name-defined]  # noqa: F821
    """Parse a ``urn:uuid:...`` serial into a :class:`uuid.UUID`."""
    from uuid import UUID

    if serial.startswith("urn:uuid:"):
        return UUID(serial[len("urn:uuid:") :])
    return UUID(serial)
