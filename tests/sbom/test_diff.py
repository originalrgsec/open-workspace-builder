"""OWB-S107c — Tests for the structural SBOM diff."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from open_workspace_builder.sbom.diff import (
    DiffResult,
    diff_boms,
    load_bom,
    render_json,
    render_text,
)


def _component(
    bom_ref: str,
    *,
    name: str = "x",
    version: str = "1.0",
    hash_content: str = "a" * 64,
    license_id: str | None = None,
    capabilities: tuple[str, ...] = (),
    provenance_source: str | None = None,
    provenance_commit: str | None = None,
) -> dict[str, Any]:
    properties: list[dict[str, str]] = [
        {"name": "owb:kind", "value": "skill"},
    ]
    for cap in capabilities:
        properties.append({"name": cap, "value": "declared"})
    if provenance_source is not None:
        properties.append({"name": "owb:provenance:source", "value": provenance_source})
    if provenance_commit is not None:
        properties.append({"name": "owb:provenance:commit", "value": provenance_commit})

    licenses: list[dict[str, Any]] = []
    if license_id is not None:
        licenses.append({"license": {"id": license_id}})

    return {
        "type": "library",
        "bom-ref": bom_ref,
        "name": name,
        "version": version,
        "hashes": [{"alg": "SHA-256", "content": hash_content}],
        "licenses": licenses,
        "properties": properties,
    }


def _bom(*components: dict[str, Any]) -> dict[str, Any]:
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "components": list(components),
    }


# ---------------------------------------------------------------------------
# Bucket cases
# ---------------------------------------------------------------------------


class TestDiffBuckets:
    def test_no_differences(self) -> None:
        a = _bom(_component("owb:skill/a@1"))
        b = _bom(_component("owb:skill/a@1"))
        result = diff_boms(a, b)
        assert not result.has_differences
        assert result.unchanged_count == 1

    def test_added_component(self) -> None:
        a = _bom(_component("owb:skill/a@1"))
        b = _bom(_component("owb:skill/a@1"), _component("owb:skill/b@1"))
        result = diff_boms(a, b)
        assert result.added == ("owb:skill/b@1",)
        assert result.removed == ()
        assert result.changed == ()
        assert result.unchanged_count == 1

    def test_removed_component(self) -> None:
        a = _bom(_component("owb:skill/a@1"), _component("owb:skill/b@1"))
        b = _bom(_component("owb:skill/a@1"))
        result = diff_boms(a, b)
        assert result.removed == ("owb:skill/b@1",)
        assert result.added == ()
        assert result.unchanged_count == 1

    def test_hash_change_is_changed(self) -> None:
        a = _bom(_component("owb:skill/a@1", hash_content="a" * 64))
        b = _bom(_component("owb:skill/a@1", hash_content="b" * 64))
        result = diff_boms(a, b)
        assert len(result.changed) == 1
        change = result.changed[0]
        assert change.bom_ref == "owb:skill/a@1"
        assert any(c.field == "content_hash" for c in change.changes)

    def test_license_change_is_changed(self) -> None:
        a = _bom(_component("owb:skill/a@1", license_id="MIT"))
        b = _bom(_component("owb:skill/a@1", license_id="Apache-2.0"))
        result = diff_boms(a, b)
        assert len(result.changed) == 1
        assert any(c.field == "licenses" for c in result.changed[0].changes)

    def test_capability_set_change_is_changed(self) -> None:
        a = _bom(
            _component(
                "owb:skill/a@1",
                capabilities=("owb:capability:tool:Read",),
            )
        )
        b = _bom(
            _component(
                "owb:skill/a@1",
                capabilities=("owb:capability:tool:Read", "owb:capability:tool:Bash"),
            )
        )
        result = diff_boms(a, b)
        assert len(result.changed) == 1
        assert any(c.field == "capabilities" for c in result.changed[0].changes)

    def test_provenance_source_change_is_changed(self) -> None:
        a = _bom(_component("owb:skill/a@1", provenance_source="https://x/a"))
        b = _bom(_component("owb:skill/a@1", provenance_source="https://x/b"))
        result = diff_boms(a, b)
        assert any(c.field == "provenance_source" for c in result.changed[0].changes)

    def test_provenance_commit_change_is_changed(self) -> None:
        a = _bom(_component("owb:skill/a@1", provenance_commit="abc"))
        b = _bom(_component("owb:skill/a@1", provenance_commit="def"))
        result = diff_boms(a, b)
        assert any(c.field == "provenance_commit" for c in result.changed[0].changes)

    def test_added_at_property_does_not_count_as_changed(self) -> None:
        """added_at is metadata; it must NOT be in the comparable surface."""
        a = _bom(_component("owb:skill/a@1"))
        b_raw = _component("owb:skill/a@1")
        b_raw["properties"].append({"name": "owb:provenance:added-at", "value": "2026-04-11"})
        b = _bom(b_raw)
        result = diff_boms(a, b)
        assert not result.has_differences


# ---------------------------------------------------------------------------
# Loaders and formatters
# ---------------------------------------------------------------------------


class TestLoadBom:
    def test_loads_valid_bom(self, tmp_path: Path) -> None:
        bom_path = tmp_path / "x.cdx.json"
        bom_path.write_text(json.dumps(_bom()))
        loaded = load_bom(bom_path)
        assert loaded["bomFormat"] == "CycloneDX"

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_bom(tmp_path / "nope.json")

    def test_invalid_json_raises(self, tmp_path: Path) -> None:
        bom_path = tmp_path / "x.cdx.json"
        bom_path.write_text("not json")
        with pytest.raises(ValueError):
            load_bom(bom_path)

    def test_non_dict_root_raises(self, tmp_path: Path) -> None:
        bom_path = tmp_path / "x.cdx.json"
        bom_path.write_text("[]")
        with pytest.raises(ValueError):
            load_bom(bom_path)


class TestRenderJson:
    def test_stable_json_output(self) -> None:
        result = DiffResult(added=("a", "b"), removed=("c",), unchanged_count=3)
        rendered = render_json(result)
        parsed = json.loads(rendered)
        assert parsed["added"] == ["a", "b"]
        assert parsed["removed"] == ["c"]
        assert parsed["changed"] == []
        assert parsed["unchanged_count"] == 3
        # Stable: re-render is byte-identical
        assert render_json(result) == rendered

    def test_changed_serializes_field_deltas(self) -> None:
        a = _bom(_component("owb:skill/a@1", license_id="MIT"))
        b = _bom(_component("owb:skill/a@1", license_id="Apache-2.0"))
        result = diff_boms(a, b)
        rendered = render_json(result)
        parsed = json.loads(rendered)
        assert parsed["changed"][0]["bom-ref"] == "owb:skill/a@1"
        assert parsed["changed"][0]["changes"][0]["field"] == "licenses"


class TestRenderText:
    def test_summary_only_when_no_changes(self) -> None:
        result = DiffResult(unchanged_count=5)
        rendered = render_text(result)
        assert "summary: +0 -0 ~0 =5" in rendered
        assert "+ added" not in rendered

    def test_lists_each_change(self) -> None:
        a = _bom(_component("owb:skill/a@1"), _component("owb:skill/b@1"))
        b = _bom(_component("owb:skill/a@1"), _component("owb:skill/c@1"))
        result = diff_boms(a, b)
        rendered = render_text(result)
        assert "+ added    owb:skill/c@1" in rendered
        assert "- removed  owb:skill/b@1" in rendered
