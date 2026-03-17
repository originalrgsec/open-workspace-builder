"""Tests for package metadata and version consistency."""

from __future__ import annotations

import re
from pathlib import Path


def test_version_consistency() -> None:
    """Verify __init__.py and pyproject.toml declare the same version."""
    import claude_workspace_builder

    init_version = claude_workspace_builder.__version__

    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    pyproject_text = pyproject_path.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject_text, re.MULTILINE)
    assert match is not None, "Could not find version in pyproject.toml"
    pyproject_version = match.group(1)

    assert init_version == pyproject_version, (
        f"Version mismatch: __init__.py={init_version}, pyproject.toml={pyproject_version}"
    )


def test_package_has_version() -> None:
    """Verify the package exposes __version__."""
    import claude_workspace_builder

    assert hasattr(claude_workspace_builder, "__version__")
    assert isinstance(claude_workspace_builder.__version__, str)
    assert claude_workspace_builder.__version__  # not empty


def test_entry_point_defined() -> None:
    """Verify pyproject.toml defines the cwb entry point."""
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    pyproject_text = pyproject_path.read_text(encoding="utf-8")
    assert 'cwb = "claude_workspace_builder.cli:cwb"' in pyproject_text
