"""S035 — Source discovery: config-driven file discovery with glob patterns."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceConfig:
    """Configuration for a single upstream content source."""

    name: str
    repo_url: str
    pin: str
    discovery_method: str = "glob"
    patterns: tuple[str, ...] = ("**/SKILL.md",)
    exclude: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscoveredFile:
    """A file discovered within an upstream source."""

    source_name: str
    relative_path: str
    absolute_path: str


class SourceDiscovery:
    """Discover content files within upstream sources using glob patterns."""

    def __init__(self, sources: list[SourceConfig]) -> None:
        self._sources: dict[str, SourceConfig] = {s.name: s for s in sources}

    @property
    def source_names(self) -> tuple[str, ...]:
        """Return all registered source names."""
        return tuple(self._sources.keys())

    def get_config(self, source_name: str) -> SourceConfig:
        """Return config for a source, raising KeyError if not found."""
        if source_name not in self._sources:
            raise KeyError(f"Unknown source: {source_name!r}")
        return self._sources[source_name]

    def discover(self, source_name: str, local_path: str) -> list[DiscoveredFile]:
        """Discover files matching the source's glob patterns.

        Args:
            source_name: Name of the registered source to use for patterns.
            local_path: Local filesystem path to search (cloned repo root).

        Returns:
            Sorted list of DiscoveredFile objects.

        Raises:
            KeyError: If source_name is not registered.
            FileNotFoundError: If local_path does not exist.
        """
        config = self.get_config(source_name)
        root = Path(local_path)
        if not root.exists():
            raise FileNotFoundError(f"Source path does not exist: {local_path}")

        matched: set[Path] = set()
        for pattern in config.patterns:
            matched.update(root.glob(pattern))

        discovered: list[DiscoveredFile] = []
        for path in sorted(matched):
            if not path.is_file():
                continue
            rel = str(path.relative_to(root))
            if _is_excluded(rel, config.exclude):
                continue
            discovered.append(
                DiscoveredFile(
                    source_name=source_name,
                    relative_path=rel,
                    absolute_path=str(path),
                )
            )
        return discovered


def _is_excluded(relative_path: str, exclude_patterns: tuple[str, ...]) -> bool:
    """Check whether a relative path matches any exclude pattern."""
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(relative_path, pattern):
            return True
        # Also check each path component prefix for directory patterns
        parts = relative_path.split("/")
        for i in range(len(parts)):
            partial = "/".join(parts[: i + 1])
            if fnmatch.fnmatch(partial, pattern.rstrip("/")):
                return True
    return False
