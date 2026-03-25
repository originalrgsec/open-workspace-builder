"""Discover Python dependencies from source files and config."""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Standard library module names (Python 3.10+).
_STDLIB_MODULES: frozenset[str] = (
    frozenset(sys.stdlib_module_names)
    if hasattr(sys, "stdlib_module_names")
    else frozenset()
)


def discover_dependencies(path: Path) -> list[str]:
    """Scan a directory or file for dependency indicators.

    Checks:
    - ``requirements.txt`` files
    - ``pyproject.toml`` ``[project.dependencies]``
    - Import statements in ``.py`` files for non-stdlib packages

    Returns a deduplicated, sorted list of package names (no versions).
    """
    if path.is_file():
        return _discover_from_file(path)

    packages: set[str] = set()
    for child in path.rglob("requirements*.txt"):
        packages.update(_parse_requirements(child))
    for child in path.rglob("pyproject.toml"):
        packages.update(_parse_pyproject(child))
    for child in path.rglob("*.py"):
        packages.update(_parse_imports(child))
    return sorted(packages)


def _discover_from_file(path: Path) -> list[str]:
    """Dispatch discovery based on filename."""
    name = path.name
    if name.startswith("requirements") and name.endswith(".txt"):
        return sorted(_parse_requirements(path))
    if name == "pyproject.toml":
        return sorted(_parse_pyproject(path))
    if name.endswith(".py"):
        return sorted(_parse_imports(path))
    return []


def _parse_requirements(path: Path) -> set[str]:
    """Extract package names from a requirements.txt file."""
    packages: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Strip version specifiers: "package>=1.0" → "package"
        name = re.split(r"[>=<!~\[;]", line)[0].strip()
        if name:
            packages.add(_normalize(name))
    return packages


def _parse_pyproject(path: Path) -> set[str]:
    """Extract dependency names from pyproject.toml [project.dependencies]."""
    packages: set[str] = set()
    text = path.read_text(encoding="utf-8")

    in_deps = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "[project.dependencies]" or stripped.startswith("dependencies = ["):
            in_deps = True
            continue
        if in_deps:
            if stripped.startswith("[") and not stripped.startswith('"'):
                break
            if stripped == "]":
                in_deps = False
                continue
            # Parse quoted dependency strings: "click>=8.0",
            match = re.match(r'^"([^"]+)"', stripped)
            if match:
                dep_str = match.group(1)
                name = re.split(r"[>=<!~\[;]", dep_str)[0].strip()
                if name:
                    packages.add(_normalize(name))

    return packages


def _parse_imports(path: Path) -> set[str]:
    """Extract non-stdlib package names from import statements."""
    packages: set[str] = set()
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return packages

    for line in text.splitlines():
        stripped = line.strip()
        # import foo / import foo.bar
        match = re.match(r"^import\s+(\w+)", stripped)
        if match:
            mod = match.group(1)
            if mod not in _STDLIB_MODULES and mod != "__future__":
                packages.add(_normalize(mod))
            continue
        # from foo import bar / from foo.bar import baz
        match = re.match(r"^from\s+(\w+)", stripped)
        if match:
            mod = match.group(1)
            if mod not in _STDLIB_MODULES and mod != "__future__":
                packages.add(_normalize(mod))

    return packages


def _normalize(name: str) -> str:
    """Normalize package name: lowercase, replace underscores with hyphens."""
    return name.lower().replace("_", "-")
