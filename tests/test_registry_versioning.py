"""Tests for registry version gating and unknown field warnings (S083)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from open_workspace_builder.registry.registry import Registry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_registry_item(
    directory: Path,
    filename: str,
    *,
    item_id: str = "test-item",
    version: str = "1.0",
    item_type: str = "pattern",
    min_owb_version: str | None = None,
    extra_fields: dict | None = None,
) -> Path:
    """Write a registry YAML file with optional version gate and extra fields."""
    data: dict = {
        "id": item_id,
        "version": version,
        "type": item_type,
        "author": "test",
        "description": "Test item",
        "compatibility": ">=0.1.0",
    }
    if min_owb_version is not None:
        data["min_owb_version"] = min_owb_version
    if extra_fields:
        data.update(extra_fields)
    data["payload"] = {"rules": []}

    path = directory / filename
    path.write_text(yaml.dump(data), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# AC-1: Items without min_owb_version load normally
# ---------------------------------------------------------------------------


class TestNoVersionConstraint:
    """Registry items without min_owb_version load identically to current behavior."""

    def test_item_loads_without_version_field(self, tmp_path: Path) -> None:
        _write_registry_item(tmp_path, "item.yaml")
        registry = Registry(base_dirs=[tmp_path])
        item = registry.get_item("test-item")
        assert item is not None
        assert item.id == "test-item"

    def test_multiple_items_load(self, tmp_path: Path) -> None:
        _write_registry_item(tmp_path, "a.yaml", item_id="item-a")
        _write_registry_item(tmp_path, "b.yaml", item_id="item-b")
        registry = Registry(base_dirs=[tmp_path])
        assert registry.get_item("item-a") is not None
        assert registry.get_item("item-b") is not None


# ---------------------------------------------------------------------------
# AC-2: Items with min_owb_version above running version are skipped
# ---------------------------------------------------------------------------


class TestVersionGateSkip:
    """Items requiring a newer OWB version are skipped with warning."""

    def test_item_with_future_version_skipped(self, tmp_path: Path) -> None:
        _write_registry_item(
            tmp_path,
            "future.yaml",
            item_id="future-item",
            min_owb_version="99.0.0",
        )
        registry = Registry(base_dirs=[tmp_path])
        assert registry.get_item("future-item") is None

    def test_skipped_item_produces_warning(self, tmp_path: Path) -> None:
        _write_registry_item(
            tmp_path,
            "future.yaml",
            item_id="future-item",
            min_owb_version="99.0.0",
        )
        with pytest.warns(UserWarning, match="requires OWB >= 99.0.0"):
            Registry(base_dirs=[tmp_path])


# ---------------------------------------------------------------------------
# AC-3: Items with min_owb_version at or below running version load normally
# ---------------------------------------------------------------------------


class TestVersionGatePass:
    """Items compatible with the current version load normally."""

    def test_item_with_current_version_loads(self, tmp_path: Path) -> None:
        _write_registry_item(
            tmp_path,
            "compat.yaml",
            item_id="compat-item",
            min_owb_version="0.1.0",
        )
        registry = Registry(base_dirs=[tmp_path])
        assert registry.get_item("compat-item") is not None

    def test_item_with_exact_version_loads(self, tmp_path: Path) -> None:
        """Edge case: min_owb_version equals current version."""
        from importlib.metadata import version

        try:
            current = version("open-workspace-builder")
        except Exception:
            current = "0.1.0"

        _write_registry_item(
            tmp_path,
            "exact.yaml",
            item_id="exact-item",
            min_owb_version=current,
        )
        registry = Registry(base_dirs=[tmp_path])
        assert registry.get_item("exact-item") is not None


# ---------------------------------------------------------------------------
# AC-4/5: Unknown fields produce warnings but don't block loading
# ---------------------------------------------------------------------------


class TestUnknownFieldWarnings:
    """Unknown fields in registry items produce warnings but load successfully."""

    def test_unknown_field_produces_warning(self, tmp_path: Path) -> None:
        _write_registry_item(
            tmp_path,
            "extra.yaml",
            item_id="extra-item",
            extra_fields={"delegated_scan": True, "priority_override": 5},
        )
        with pytest.warns(UserWarning, match="unknown field"):
            Registry(base_dirs=[tmp_path])

    def test_unknown_field_item_still_loads(self, tmp_path: Path) -> None:
        _write_registry_item(
            tmp_path,
            "extra.yaml",
            item_id="extra-item",
            extra_fields={"delegated_scan": True},
        )
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            registry = Registry(base_dirs=[tmp_path])
        assert registry.get_item("extra-item") is not None

    def test_known_fields_produce_no_warning(self, tmp_path: Path) -> None:
        """Items with only known fields should not produce unknown field warnings."""
        _write_registry_item(tmp_path, "clean.yaml", item_id="clean-item")
        # Should not warn about unknown fields
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Registry(base_dirs=[tmp_path])
        unknown_warnings = [x for x in w if "unknown field" in str(x.message).lower()]
        assert len(unknown_warnings) == 0
