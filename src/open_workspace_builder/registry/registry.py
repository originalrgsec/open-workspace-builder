"""Registry: loads, validates, and merges registry items from directories."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RegistryItem:
    """A validated registry item with metadata and payload."""

    id: str
    version: str
    type: str  # "pattern", "pattern_set", "policy", "marketplace_format"
    author: str
    description: str
    compatibility: str
    payload: dict[str, Any]


_REQUIRED_FIELDS = ("id", "version", "type")
_KNOWN_FIELDS = frozenset({
    "id", "version", "type", "author", "description", "compatibility",
    "payload", "min_owb_version",
})


def _load_yaml_file(path: Path) -> dict[str, Any] | None:
    """Load a single YAML file, returning None on failure."""
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        warnings.warn(
            "PyYAML is required for registry loading. Install with: pip install pyyaml",
            stacklevel=3,
        )
        return None

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        warnings.warn(f"Could not load registry file {path}: {exc}", stacklevel=3)
        return None

    if not isinstance(raw, dict):
        warnings.warn(f"Registry file {path} is not a YAML mapping, skipping", stacklevel=3)
        return None

    return raw


def _get_owb_version() -> str:
    """Return the current OWB version string."""
    try:
        from importlib.metadata import version
        return version("open-workspace-builder")
    except Exception:
        return "0.0.0"


def _check_min_version(raw: dict[str, Any], source: Path) -> bool:
    """Check min_owb_version constraint. Returns True if compatible, False if not."""
    min_ver = raw.get("min_owb_version")
    if min_ver is None:
        return True

    try:
        from packaging.version import Version
        current = Version(_get_owb_version())
        required = Version(str(min_ver))
        if current < required:
            item_name = raw.get("id", source.name)
            warnings.warn(
                f"Skipping registry item '{item_name}': requires OWB >= {min_ver}, "
                f"running {current}",
                stacklevel=4,
            )
            return False
    except Exception:
        # If packaging is unavailable or version parsing fails, allow the item
        pass

    return True


def _warn_unknown_fields(raw: dict[str, Any], source: Path) -> None:
    """Warn about unrecognized fields in a registry item."""
    unknown = sorted(set(raw.keys()) - _KNOWN_FIELDS)
    if unknown:
        item_name = raw.get("id", source.name)
        warnings.warn(
            f"Registry item '{item_name}' contains unknown field(s): "
            f"{', '.join(unknown)} — may require a newer OWB version",
            stacklevel=4,
        )


def _parse_item(raw: dict[str, Any], source: Path) -> RegistryItem | None:
    """Parse and validate a raw dict into a RegistryItem, or None on failure."""
    missing = [f for f in _REQUIRED_FIELDS if f not in raw]
    if missing:
        warnings.warn(
            f"Registry file {source} missing required fields: {', '.join(missing)}, skipping",
            stacklevel=3,
        )
        return None

    # Check version compatibility
    if not _check_min_version(raw, source):
        return None

    # Warn about unknown fields
    _warn_unknown_fields(raw, source)

    return RegistryItem(
        id=str(raw["id"]),
        version=str(raw["version"]),
        type=str(raw["type"]),
        author=str(raw.get("author", "")),
        description=str(raw.get("description", "")),
        compatibility=str(raw.get("compatibility", "")),
        payload=raw.get("payload", {}),
    )


def _load_dir(directory: Path) -> dict[str, RegistryItem]:
    """Load all .yaml/.yml files from a directory (non-recursive), return items keyed by id."""
    items: dict[str, RegistryItem] = {}
    if not directory.is_dir():
        return items

    for path in sorted(directory.iterdir()):
        if path.suffix not in (".yaml", ".yml") or not path.is_file():
            continue
        raw = _load_yaml_file(path)
        if raw is None:
            continue
        item = _parse_item(raw, path)
        if item is not None:
            items[item.id] = item

    return items


class Registry:
    """Loads, validates, and merges registry items from directories."""

    def __init__(
        self,
        base_dirs: list[Path],
        overlay_dirs: list[Path] | None = None,
    ) -> None:
        """Load registry items from base directories, with optional overlay directories.

        Overlay items with the same ID as a base item replace the base item.
        Items with different IDs from both sources are merged.
        """
        self._items: dict[str, RegistryItem] = {}

        for d in base_dirs:
            self._items.update(_load_dir(d))

        if overlay_dirs:
            for d in overlay_dirs:
                self._items.update(_load_dir(d))

    def get_items_by_type(self, item_type: str) -> list[RegistryItem]:
        """Return all items of a given type."""
        return [item for item in self._items.values() if item.type == item_type]

    def get_active_items(self, item_type: str, active_ids: tuple[str, ...]) -> list[RegistryItem]:
        """Return items matching the active ID list from config.

        If an active ID refers to a pattern_set (type ending in '_set'),
        resolve its 'includes' list to individual items.
        """
        result: list[RegistryItem] = []
        seen: set[str] = set()

        for aid in active_ids:
            item = self._items.get(aid)
            if item is None:
                continue

            # Resolve set items (e.g. pattern_set → individual patterns)
            if item.type.endswith("_set"):
                includes = item.payload.get("includes", [])
                for ref_id in includes:
                    if ref_id in seen:
                        continue
                    ref = self._items.get(ref_id)
                    if ref is not None and ref.type == item_type:
                        result.append(ref)
                        seen.add(ref_id)
            elif item.type == item_type:
                if item.id not in seen:
                    result.append(item)
                    seen.add(item.id)

        return result

    def get_item(self, item_id: str) -> RegistryItem | None:
        """Return a single item by ID, or None."""
        return self._items.get(item_id)

    @property
    def all_items(self) -> dict[str, RegistryItem]:
        """Return all loaded items."""
        return dict(self._items)
