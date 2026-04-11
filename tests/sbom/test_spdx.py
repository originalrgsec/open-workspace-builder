"""OWB-S107c — Tests for the SPDX 2.3 emitter."""

from __future__ import annotations

import json

from open_workspace_builder.sbom.capability import (
    Capability,
    CapabilityKind,
)
from open_workspace_builder.sbom.discover import Component, ComponentKind
from open_workspace_builder.sbom.license import LicenseEntry, LicenseSource
from open_workspace_builder.sbom.provenance import (
    Provenance,
    ProvenanceConfidence,
    ProvenanceType,
)
from open_workspace_builder.sbom.spdx import (
    SPDX_DATA_LICENSE,
    SPDX_DOCUMENT_ID,
    SPDX_VERSION,
    build_spdx_document,
    sanitize_spdx_id,
    serialize_spdx,
)


def _component(
    *,
    name: str = "demo",
    bom_ref: str = "owb:skill/demo@1.0",
    version: str = "1.0",
    license_entry: LicenseEntry | None = None,
    provenance: Provenance | None = None,
    capabilities: tuple[Capability, ...] = (),
) -> Component:
    return Component(
        kind=ComponentKind.SKILL,
        name=name,
        version=version,
        bom_ref=bom_ref,
        content_hash="sha256-norm1:" + ("a" * 64),
        evidence_path=".claude/skills/demo/SKILL.md",
        source="local",
        provenance=provenance,
        capabilities=capabilities,
        license=license_entry,
    )


# ---------------------------------------------------------------------------
# Top-level structure
# ---------------------------------------------------------------------------


class TestSpdxTopLevel:
    def test_required_fields_present(self) -> None:
        doc = build_spdx_document([_component()], serial="fixed", timestamp="2026-04-11T00:00:00Z")
        assert doc["spdxVersion"] == SPDX_VERSION
        assert doc["dataLicense"] == SPDX_DATA_LICENSE
        assert doc["SPDXID"] == SPDX_DOCUMENT_ID
        assert "name" in doc
        assert "documentNamespace" in doc
        assert "creationInfo" in doc
        assert doc["creationInfo"]["created"] == "2026-04-11T00:00:00Z"
        assert "packages" in doc

    def test_serialized_is_valid_json(self) -> None:
        s = serialize_spdx([_component()], serial="fixed", timestamp="2026-04-11T00:00:00Z")
        parsed = json.loads(s)
        assert parsed["spdxVersion"] == SPDX_VERSION

    def test_namespace_uses_serial(self) -> None:
        doc = build_spdx_document([_component()], serial="abc123", timestamp="2026-04-11T00:00:00Z")
        assert doc["documentNamespace"].endswith("abc123")

    def test_default_creation_info_is_iso(self) -> None:
        doc = build_spdx_document([_component()])
        # Smoke check: created field is ISO 8601-shaped.
        created = doc["creationInfo"]["created"]
        assert len(created) == 20 and created.endswith("Z")


# ---------------------------------------------------------------------------
# Per-package mapping
# ---------------------------------------------------------------------------


class TestSpdxPackageMapping:
    def test_basic_fields(self) -> None:
        doc = build_spdx_document(
            [_component(name="hello", version="1.0")],
            serial="fixed",
            timestamp="2026-04-11T00:00:00Z",
        )
        pkg = doc["packages"][0]
        assert pkg["name"] == "hello"
        assert pkg["versionInfo"] == "1.0"
        assert pkg["SPDXID"].startswith("SPDXRef-")
        assert pkg["filesAnalyzed"] is False

    def test_checksum_is_raw_hex(self) -> None:
        doc = build_spdx_document([_component()], serial="x", timestamp="2026-04-11T00:00:00Z")
        pkg = doc["packages"][0]
        cs = pkg["checksums"][0]
        assert cs["algorithm"] == "SHA256"
        assert ":" not in cs["checksumValue"]
        assert len(cs["checksumValue"]) == 64

    def test_spdx_id_sanitization(self) -> None:
        sid = sanitize_spdx_id("owb:skill/demo@1.0")
        assert sid.startswith("SPDXRef-")
        # No colons, slashes, or @
        assert ":" not in sid[len("SPDXRef-") :]
        assert "/" not in sid
        assert "@" not in sid

    def test_spdx_id_empty_input(self) -> None:
        assert sanitize_spdx_id("") == "SPDXRef-unknown"

    def test_known_spdx_license_concluded_and_declared(self) -> None:
        license_entry = LicenseEntry(
            spdx_id="MIT",
            source=LicenseSource.FRONTMATTER,
            allowed=True,
        )
        doc = build_spdx_document(
            [_component(license_entry=license_entry)],
            serial="x",
            timestamp="2026-04-11T00:00:00Z",
        )
        pkg = doc["packages"][0]
        assert pkg["licenseConcluded"] == "MIT"
        assert pkg["licenseDeclared"] == "MIT"

    def test_custom_license_uses_licenseref(self) -> None:
        license_entry = LicenseEntry(
            spdx_id=None,
            custom_name="Some Weird License",
            source=LicenseSource.SIBLING_FILE,
            allowed=False,
        )
        doc = build_spdx_document(
            [_component(license_entry=license_entry)],
            serial="x",
            timestamp="2026-04-11T00:00:00Z",
        )
        pkg = doc["packages"][0]
        assert pkg["licenseConcluded"].startswith("LicenseRef-")

    def test_no_license_yields_noassertion(self) -> None:
        doc = build_spdx_document([_component()], serial="x", timestamp="2026-04-11T00:00:00Z")
        pkg = doc["packages"][0]
        assert pkg["licenseConcluded"] == "NOASSERTION"
        assert pkg["licenseDeclared"] == "NOASSERTION"

    def test_provenance_source_becomes_download_location(self) -> None:
        prov = Provenance(
            type=ProvenanceType.GIT_HISTORY,
            confidence=ProvenanceConfidence.HIGH,
            source="https://github.com/example/test.git",
            commit="a" * 40,
        )
        doc = build_spdx_document(
            [_component(provenance=prov)], serial="x", timestamp="2026-04-11T00:00:00Z"
        )
        pkg = doc["packages"][0]
        assert pkg["downloadLocation"] == "https://github.com/example/test.git"
        assert "commit:" in pkg["sourceInfo"]

    def test_local_provenance_becomes_noassertion(self) -> None:
        prov = Provenance(
            type=ProvenanceType.LOCAL,
            confidence=ProvenanceConfidence.LOW,
        )
        doc = build_spdx_document(
            [_component(provenance=prov)], serial="x", timestamp="2026-04-11T00:00:00Z"
        )
        pkg = doc["packages"][0]
        assert pkg["downloadLocation"] == "NOASSERTION"

    def test_capability_annotations(self) -> None:
        caps = (
            Capability(kind=CapabilityKind.TOOL, value="Read"),
            Capability(kind=CapabilityKind.TOOL, value="Bash"),
        )
        doc = build_spdx_document(
            [_component(capabilities=caps)], serial="x", timestamp="2026-04-11T00:00:00Z"
        )
        pkg = doc["packages"][0]
        annotations = pkg["annotations"]
        assert len(annotations) == 2
        comments = {a["comment"] for a in annotations}
        assert "owb:capability:tool:Read" in comments
        assert "owb:capability:tool:Bash" in comments
        for ann in annotations:
            assert ann["annotator"].startswith("Tool:")
            assert ann["annotationType"] == "OTHER"

    def test_no_capabilities_omits_annotations(self) -> None:
        doc = build_spdx_document([_component()], serial="x", timestamp="2026-04-11T00:00:00Z")
        pkg = doc["packages"][0]
        assert "annotations" not in pkg


# ---------------------------------------------------------------------------
# JSON shape stability
# ---------------------------------------------------------------------------


class TestSpdxSerialization:
    def test_byte_stable_with_fixed_serial_and_timestamp(self) -> None:
        s1 = serialize_spdx([_component()], serial="fixed", timestamp="2026-04-11T00:00:00Z")
        s2 = serialize_spdx([_component()], serial="fixed", timestamp="2026-04-11T00:00:00Z")
        assert s1 == s2

    def test_byte_stable_with_capabilities(self) -> None:
        """Annotation date must be threaded from the document timestamp.

        Regression: an earlier draft pulled `datetime.now()` inside the
        annotation builder, breaking byte-stability when components had
        capabilities.
        """
        caps = (
            Capability(kind=CapabilityKind.TOOL, value="Read"),
            Capability(kind=CapabilityKind.TOOL, value="Bash"),
        )
        c = _component(capabilities=caps)
        s1 = serialize_spdx([c], serial="fixed", timestamp="2026-04-11T00:00:00Z")
        s2 = serialize_spdx([c], serial="fixed", timestamp="2026-04-11T00:00:00Z")
        assert s1 == s2

    def test_sanitize_spdx_id_collapses_consecutive_hyphens(self) -> None:
        # Pathological bom-ref with adjacent special chars.
        sid = sanitize_spdx_id("owb::skill//foo@@1")
        assert sid.startswith("SPDXRef-")
        assert "--" not in sid
