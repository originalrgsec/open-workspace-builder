"""OWB-S107c — Tests for `owb sbom show`."""

from __future__ import annotations

import json
from typing import Any

from open_workspace_builder.sbom.show import (
    find_component,
    render_detail_json,
    render_detail_text,
    render_summary_json,
    render_summary_text,
    summarize,
)


def _component(
    bom_ref: str,
    *,
    name: str = "x",
    version: str = "1",
    kind: str = "skill",
    license_id: str = "MIT",
    provenance_type: str = "git-history",
    confidence: str = "high",
    capabilities: tuple[str, ...] = ("owb:capability:tool:Read",),
) -> dict[str, Any]:
    properties = [
        {"name": "owb:kind", "value": kind},
        {"name": "owb:provenance:type", "value": provenance_type},
        {"name": "owb:provenance:confidence", "value": confidence},
    ]
    for cap in capabilities:
        properties.append({"name": cap, "value": "declared"})
    return {
        "type": "library",
        "bom-ref": bom_ref,
        "name": name,
        "version": version,
        "hashes": [{"alg": "SHA-256", "content": "f" * 64}],
        "licenses": [{"license": {"id": license_id}}],
        "properties": properties,
    }


def _bom(*components: dict[str, Any]) -> dict[str, Any]:
    return {"bomFormat": "CycloneDX", "specVersion": "1.6", "components": list(components)}


class TestSummarize:
    def test_one_component(self) -> None:
        bom = _bom(_component("owb:skill/a@1"))
        rows = summarize(bom)
        assert len(rows) == 1
        assert rows[0].name == "x"
        assert rows[0].license == "MIT"
        assert rows[0].provenance_type == "git-history"
        assert rows[0].capability_count == 1

    def test_no_components(self) -> None:
        assert summarize({"components": []}) == ()

    def test_missing_components_key(self) -> None:
        assert summarize({}) == ()


class TestRenderSummary:
    def test_text_includes_headers(self) -> None:
        bom = _bom(_component("owb:skill/a@1"))
        text = render_summary_text(summarize(bom))
        assert "KIND" in text
        assert "BOM-REF" in text
        assert "owb:skill/a@1" in text

    def test_text_no_components(self) -> None:
        assert render_summary_text(()) == "(no components)"

    def test_json_is_valid(self) -> None:
        bom = _bom(_component("owb:skill/a@1"))
        out = render_summary_json(summarize(bom))
        parsed = json.loads(out)
        assert parsed[0]["bom-ref"] == "owb:skill/a@1"
        assert parsed[0]["provenance"]["type"] == "git-history"


class TestFindComponent:
    def test_found(self) -> None:
        bom = _bom(_component("owb:skill/a@1"), _component("owb:skill/b@1", name="y"))
        detail = find_component(bom, "owb:skill/b@1")
        assert detail is not None
        assert detail.name == "y"

    def test_not_found(self) -> None:
        bom = _bom(_component("owb:skill/a@1"))
        assert find_component(bom, "owb:skill/missing@9") is None


class TestRenderDetail:
    def test_text_dump_lists_caps_and_props(self) -> None:
        bom = _bom(
            _component(
                "owb:skill/a@1",
                capabilities=("owb:capability:tool:Read", "owb:capability:tool:Bash"),
            )
        )
        detail = find_component(bom, "owb:skill/a@1")
        assert detail is not None
        text = render_detail_text(detail)
        assert "owb:capability:tool:Read" in text
        assert "owb:capability:tool:Bash" in text
        assert "MIT" in text

    def test_json_dump_is_valid(self) -> None:
        bom = _bom(_component("owb:skill/a@1"))
        detail = find_component(bom, "owb:skill/a@1")
        assert detail is not None
        out = render_detail_json(detail)
        parsed = json.loads(out)
        assert parsed["bom-ref"] == "owb:skill/a@1"
        assert "MIT" in parsed["licenses"]
