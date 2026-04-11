"""OWB-S107a — SBOM builder tests.

The builder takes a tuple of :class:`Component` records and produces a
CycloneDX 1.6 JSON document. Output must validate against the official
CycloneDX schema.
"""

from __future__ import annotations

import json


from open_workspace_builder.sbom.builder import (
    BomOptions,
    build_bom,
    serialize_bom,
)
from open_workspace_builder.sbom.discover import Component, ComponentKind

FIXED_SERIAL = "urn:uuid:00000000-0000-0000-0000-000000000001"
FIXED_TS = "2026-04-10T00:00:00+00:00"


def _make_components() -> tuple[Component, ...]:
    return (
        Component(
            kind=ComponentKind.SKILL,
            name="xlsx",
            version="1.2.0",
            bom_ref="owb:skill/xlsx@1.2.0",
            content_hash="sha256-norm1:" + "a" * 64,
            evidence_path=".claude/skills/xlsx/SKILL.md",
            source="local",
        ),
        Component(
            kind=ComponentKind.AGENT,
            name="planner",
            version="abc123456789",
            bom_ref="owb:agent/planner@abc123456789",
            content_hash="sha256-norm1:" + "b" * 64,
            evidence_path=".claude/agents/planner.md",
            source="local",
        ),
        Component(
            kind=ComponentKind.COMMAND,
            name="commit",
            version="def987654321",
            bom_ref="owb:command/commit@def987654321",
            content_hash="sha256-norm1:" + "c" * 64,
            evidence_path=".claude/commands/commit.md",
            source="local",
        ),
        Component(
            kind=ComponentKind.MCP_SERVER,
            name="github",
            version="111111111111",
            bom_ref="owb:mcp-server/github@111111111111",
            content_hash="sha256-norm1:" + "d" * 64,
            evidence_path=".mcp.json",
            source="local",
        ),
    )


class TestBomShape:
    def test_builds_valid_bom_object(self) -> None:
        bom = build_bom(_make_components())
        assert bom is not None

    def test_bom_contains_all_components(self) -> None:
        components = _make_components()
        bom = build_bom(components)
        assert len(bom.components) == len(components)

    def test_deterministic_options_override_timestamp(self) -> None:
        opts = BomOptions(serial=FIXED_SERIAL, timestamp=FIXED_TS)
        bom = build_bom(_make_components(), options=opts)
        # Serial and timestamp are fed through serialization; see JSON tests.
        json_str = serialize_bom(bom)
        data = json.loads(json_str)
        assert data["serialNumber"] == FIXED_SERIAL
        assert data["metadata"]["timestamp"] == FIXED_TS


class TestJsonSerialization:
    def test_serializes_to_cyclonedx_1_6(self) -> None:
        bom = build_bom(_make_components())
        data = json.loads(serialize_bom(bom))
        assert data["bomFormat"] == "CycloneDX"
        assert data["specVersion"] == "1.6"

    def test_every_component_has_bom_ref(self) -> None:
        bom = build_bom(_make_components())
        data = json.loads(serialize_bom(bom))
        assert all("bom-ref" in c for c in data["components"])

    def test_every_component_has_sha256_hash(self) -> None:
        bom = build_bom(_make_components())
        data = json.loads(serialize_bom(bom))
        for c in data["components"]:
            hashes = c.get("hashes", [])
            assert any(h.get("alg") == "SHA-256" for h in hashes)

    def test_hash_content_is_hex_of_normalized(self) -> None:
        """The standard hashes field holds the raw hex of the normalized SHA-256.

        The full tagged string `sha256-norm1:<hex>` is stored in properties so
        downstream tools that read the standard `hashes` field get a clean hex.
        """
        components = _make_components()
        bom = build_bom(components)
        data = json.loads(serialize_bom(bom))
        xlsx = next(c for c in data["components"] if c["name"] == "xlsx")
        sha = next(h for h in xlsx["hashes"] if h["alg"] == "SHA-256")
        assert sha["content"] == "a" * 64  # the raw hex portion

    def test_normalization_version_in_properties(self) -> None:
        """Every component carries `owb:normalization` = `norm1` as a property."""
        bom = build_bom(_make_components())
        data = json.loads(serialize_bom(bom))
        for c in data["components"]:
            props = {p["name"]: p["value"] for p in c.get("properties", [])}
            assert props.get("owb:normalization") == "norm1"

    def test_skill_has_library_type(self) -> None:
        bom = build_bom(_make_components())
        data = json.loads(serialize_bom(bom))
        xlsx = next(c for c in data["components"] if c["name"] == "xlsx")
        assert xlsx["type"] == "library"

    def test_mcp_server_has_application_type(self) -> None:
        bom = build_bom(_make_components())
        data = json.loads(serialize_bom(bom))
        gh = next(c for c in data["components"] if c["name"] == "github")
        assert gh["type"] == "application"

    def test_component_has_owb_kind_property(self) -> None:
        bom = build_bom(_make_components())
        data = json.loads(serialize_bom(bom))
        xlsx = next(c for c in data["components"] if c["name"] == "xlsx")
        props = {p["name"]: p["value"] for p in xlsx.get("properties", [])}
        assert props.get("owb:kind") == "skill"

    def test_component_has_evidence_path(self) -> None:
        """Evidence path is exposed as an `owb:evidence-path` property.

        CycloneDX 1.6 spec supports `evidence.occurrences[].location`, but
        cyclonedx-python-lib 9.1.0 does not expose the Occurrence API. We
        carry the path as a property for machine-readability and will migrate
        to `evidence.occurrences` in S107b or S107c when the library is
        upgraded.
        """
        bom = build_bom(_make_components())
        data = json.loads(serialize_bom(bom))
        xlsx = next(c for c in data["components"] if c["name"] == "xlsx")
        props = {p["name"]: p["value"] for p in xlsx.get("properties", [])}
        assert props.get("owb:evidence-path") == ".claude/skills/xlsx/SKILL.md"


class TestCycloneDxSchemaValidation:
    """The emitted JSON must pass the official CycloneDX 1.6 JSON schema validator."""

    def test_valid_against_schema_strict(self) -> None:
        from cyclonedx.schema import SchemaVersion
        from cyclonedx.validation.json import JsonStrictValidator

        bom = build_bom(_make_components())
        json_str = serialize_bom(bom)
        validator = JsonStrictValidator(SchemaVersion.V1_6)
        errors = validator.validate_str(json_str)
        assert errors is None, f"Schema validation failed: {errors}"

    def test_empty_component_list_still_valid(self) -> None:
        from cyclonedx.schema import SchemaVersion
        from cyclonedx.validation.json import JsonStrictValidator

        bom = build_bom(())
        json_str = serialize_bom(bom)
        validator = JsonStrictValidator(SchemaVersion.V1_6)
        errors = validator.validate_str(json_str)
        assert errors is None


class TestDeterminism:
    def test_same_input_same_output_with_fixed_options(self) -> None:
        """With a fixed serial and timestamp, serialization is byte-stable."""
        opts = BomOptions(serial=FIXED_SERIAL, timestamp=FIXED_TS)
        s1 = serialize_bom(build_bom(_make_components(), options=opts))
        s2 = serialize_bom(build_bom(_make_components(), options=opts))
        assert s1 == s2
