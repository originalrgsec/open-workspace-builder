"""Tests for the extensible registry system."""

from __future__ import annotations

from pathlib import Path

import pytest

from open_workspace_builder.registry.registry import Registry, RegistryItem


def _write_yaml(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


class TestRegistryLoadFromDirectory:
    """Load registry items from a directory of YAML files."""

    def test_loads_valid_items(self, tmp_path: Path) -> None:
        _write_yaml(
            tmp_path / "item-a.yaml",
            'id: "a"\nversion: "1.0.0"\ntype: "pattern"\npayload:\n  key: value\n',
        )
        _write_yaml(
            tmp_path / "item-b.yaml",
            'id: "b"\nversion: "1.0.0"\ntype: "policy"\npayload:\n  key: value2\n',
        )
        reg = Registry(base_dirs=[tmp_path])
        assert len(reg.all_items) == 2

    def test_loads_yml_extension(self, tmp_path: Path) -> None:
        _write_yaml(
            tmp_path / "item.yml",
            'id: "yml-item"\nversion: "1.0.0"\ntype: "pattern"\n',
        )
        reg = Registry(base_dirs=[tmp_path])
        assert reg.get_item("yml-item") is not None

    def test_empty_directory(self, tmp_path: Path) -> None:
        reg = Registry(base_dirs=[tmp_path])
        assert len(reg.all_items) == 0

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        reg = Registry(base_dirs=[tmp_path / "nope"])
        assert len(reg.all_items) == 0

    def test_item_has_correct_fields(self, tmp_path: Path) -> None:
        _write_yaml(
            tmp_path / "full.yaml",
            (
                'id: "full-item"\n'
                'version: "2.0.0"\n'
                'type: "policy"\n'
                'author: "Test Author"\n'
                'description: "A test item"\n'
                'compatibility: ">=1.0.0"\n'
                "payload:\n  data: hello\n"
            ),
        )
        reg = Registry(base_dirs=[tmp_path])
        item = reg.get_item("full-item")
        assert item is not None
        assert item.id == "full-item"
        assert item.version == "2.0.0"
        assert item.type == "policy"
        assert item.author == "Test Author"
        assert item.description == "A test item"
        assert item.compatibility == ">=1.0.0"
        assert item.payload == {"data": "hello"}

    def test_multiple_base_dirs(self, tmp_path: Path) -> None:
        d1 = tmp_path / "d1"
        d2 = tmp_path / "d2"
        d1.mkdir()
        d2.mkdir()
        _write_yaml(d1 / "a.yaml", 'id: "a"\nversion: "1.0.0"\ntype: "pattern"\n')
        _write_yaml(d2 / "b.yaml", 'id: "b"\nversion: "1.0.0"\ntype: "pattern"\n')
        reg = Registry(base_dirs=[d1, d2])
        assert len(reg.all_items) == 2


class TestRegistryMetadataValidation:
    """Files missing required fields are skipped with warning."""

    def test_missing_id_skipped(self, tmp_path: Path) -> None:
        _write_yaml(tmp_path / "bad.yaml", 'version: "1.0.0"\ntype: "pattern"\n')
        with pytest.warns(UserWarning, match="missing required fields.*id"):
            reg = Registry(base_dirs=[tmp_path])
        assert len(reg.all_items) == 0

    def test_missing_type_skipped(self, tmp_path: Path) -> None:
        _write_yaml(tmp_path / "bad.yaml", 'id: "x"\nversion: "1.0.0"\n')
        with pytest.warns(UserWarning, match="missing required fields.*type"):
            reg = Registry(base_dirs=[tmp_path])
        assert len(reg.all_items) == 0

    def test_missing_version_skipped(self, tmp_path: Path) -> None:
        _write_yaml(tmp_path / "bad.yaml", 'id: "x"\ntype: "pattern"\n')
        with pytest.warns(UserWarning, match="missing required fields.*version"):
            reg = Registry(base_dirs=[tmp_path])
        assert len(reg.all_items) == 0

    def test_valid_items_still_loaded_alongside_invalid(self, tmp_path: Path) -> None:
        _write_yaml(tmp_path / "bad.yaml", 'version: "1.0.0"\ntype: "pattern"\n')
        _write_yaml(
            tmp_path / "good.yaml",
            'id: "good"\nversion: "1.0.0"\ntype: "pattern"\n',
        )
        with pytest.warns(UserWarning):
            reg = Registry(base_dirs=[tmp_path])
        assert len(reg.all_items) == 1
        assert reg.get_item("good") is not None


class TestRegistryOverlayPrecedence:
    """Overlay items with same ID replace base items."""

    def test_overlay_replaces_base(self, tmp_path: Path) -> None:
        base = tmp_path / "base"
        overlay = tmp_path / "overlay"
        base.mkdir()
        overlay.mkdir()
        _write_yaml(
            base / "a.yaml",
            'id: "a"\nversion: "1.0.0"\ntype: "pattern"\npayload:\n  source: base\n',
        )
        _write_yaml(
            overlay / "a.yaml",
            'id: "a"\nversion: "2.0.0"\ntype: "pattern"\npayload:\n  source: overlay\n',
        )
        reg = Registry(base_dirs=[base], overlay_dirs=[overlay])
        item = reg.get_item("a")
        assert item is not None
        assert item.payload["source"] == "overlay"
        assert item.version == "2.0.0"

    def test_merge_base_and_overlay(self, tmp_path: Path) -> None:
        """Base has A+B, overlay has B+C -> result has A(base), B(overlay), C(overlay)."""
        base = tmp_path / "base"
        overlay = tmp_path / "overlay"
        base.mkdir()
        overlay.mkdir()
        _write_yaml(
            base / "a.yaml",
            'id: "a"\nversion: "1.0.0"\ntype: "pattern"\npayload:\n  from: base\n',
        )
        _write_yaml(
            base / "b.yaml",
            'id: "b"\nversion: "1.0.0"\ntype: "pattern"\npayload:\n  from: base\n',
        )
        _write_yaml(
            overlay / "b.yaml",
            'id: "b"\nversion: "2.0.0"\ntype: "pattern"\npayload:\n  from: overlay\n',
        )
        _write_yaml(
            overlay / "c.yaml",
            'id: "c"\nversion: "1.0.0"\ntype: "pattern"\npayload:\n  from: overlay\n',
        )
        reg = Registry(base_dirs=[base], overlay_dirs=[overlay])
        assert len(reg.all_items) == 3
        assert reg.get_item("a") is not None
        assert reg.get_item("a").payload["from"] == "base"
        assert reg.get_item("b").payload["from"] == "overlay"
        assert reg.get_item("c").payload["from"] == "overlay"


class TestGetItemsByType:
    """Filtering by type works correctly."""

    def test_filter_by_type(self, tmp_path: Path) -> None:
        _write_yaml(
            tmp_path / "p.yaml",
            'id: "p1"\nversion: "1.0.0"\ntype: "pattern"\n',
        )
        _write_yaml(
            tmp_path / "pol.yaml",
            'id: "pol1"\nversion: "1.0.0"\ntype: "policy"\n',
        )
        _write_yaml(
            tmp_path / "mf.yaml",
            'id: "mf1"\nversion: "1.0.0"\ntype: "marketplace_format"\n',
        )
        reg = Registry(base_dirs=[tmp_path])
        assert len(reg.get_items_by_type("pattern")) == 1
        assert len(reg.get_items_by_type("policy")) == 1
        assert len(reg.get_items_by_type("marketplace_format")) == 1
        assert len(reg.get_items_by_type("nonexistent")) == 0


class TestGetActiveItems:
    """Filtering by active ID list, including pattern_set resolution."""

    def test_direct_active_id(self, tmp_path: Path) -> None:
        _write_yaml(
            tmp_path / "a.yaml",
            'id: "a"\nversion: "1.0.0"\ntype: "pattern"\n',
        )
        _write_yaml(
            tmp_path / "b.yaml",
            'id: "b"\nversion: "1.0.0"\ntype: "pattern"\n',
        )
        reg = Registry(base_dirs=[tmp_path])
        active = reg.get_active_items("pattern", ("a",))
        assert len(active) == 1
        assert active[0].id == "a"

    def test_pattern_set_resolves_includes(self, tmp_path: Path) -> None:
        _write_yaml(
            tmp_path / "set.yaml",
            (
                'id: "my-set"\nversion: "1.0.0"\ntype: "pattern_set"\n'
                "payload:\n  includes:\n    - p1\n    - p2\n"
            ),
        )
        _write_yaml(
            tmp_path / "p1.yaml",
            'id: "p1"\nversion: "1.0.0"\ntype: "pattern"\npayload:\n  x: 1\n',
        )
        _write_yaml(
            tmp_path / "p2.yaml",
            'id: "p2"\nversion: "1.0.0"\ntype: "pattern"\npayload:\n  x: 2\n',
        )
        reg = Registry(base_dirs=[tmp_path])
        active = reg.get_active_items("pattern", ("my-set",))
        assert len(active) == 2
        ids = {item.id for item in active}
        assert ids == {"p1", "p2"}

    def test_nonexistent_active_id_ignored(self, tmp_path: Path) -> None:
        reg = Registry(base_dirs=[tmp_path])
        assert reg.get_active_items("pattern", ("nope",)) == []


class TestPatternSetResolution:
    """owb-default includes -> resolves to all 12 pattern files from bundled data."""

    def test_bundled_owb_default_resolves(self) -> None:
        patterns_dir = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "open_workspace_builder"
            / "data"
            / "registry"
            / "patterns"
        )
        reg = Registry(base_dirs=[patterns_dir])
        active = reg.get_active_items("pattern", ("owb-default",))
        assert len(active) == 12
        ids = {item.id for item in active}
        expected = {
            "owb-exfiltration",
            "owb-persistence",
            "owb-stealth",
            "owb-self-modification",
            "owb-encoded",
            "owb-network",
            "owb-privilege",
            "owb-sensitive-paths",
            "owb-prompt-injection",
            "owb-jailbreak",
            "owb-markdown-exfil",
            "owb-mcp-manipulation",
        }
        assert ids == expected


class TestMalformedYaml:
    """Malformed YAML files are skipped gracefully."""

    def test_malformed_yaml_skipped(self, tmp_path: Path) -> None:
        _write_yaml(tmp_path / "bad.yaml", "{{invalid yaml: [")
        _write_yaml(
            tmp_path / "good.yaml",
            'id: "ok"\nversion: "1.0.0"\ntype: "pattern"\n',
        )
        with pytest.warns(UserWarning, match="Could not load registry file"):
            reg = Registry(base_dirs=[tmp_path])
        assert len(reg.all_items) == 1

    def test_non_mapping_yaml_skipped(self, tmp_path: Path) -> None:
        _write_yaml(tmp_path / "list.yaml", "- item1\n- item2\n")
        with pytest.warns(UserWarning, match="not a YAML mapping"):
            reg = Registry(base_dirs=[tmp_path])
        assert len(reg.all_items) == 0


class TestRegistryItemImmutability:
    """RegistryItem is frozen."""

    def test_frozen(self) -> None:
        item = RegistryItem(
            id="x",
            version="1.0.0",
            type="pattern",
            author="",
            description="",
            compatibility="",
            payload={},
        )
        with pytest.raises(AttributeError):
            item.id = "y"  # type: ignore[misc]
