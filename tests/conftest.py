"""Shared fixtures for tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_target(tmp_path: Path) -> Path:
    """Return a temporary target directory for workspace builds."""
    return tmp_path / "workspace"


@pytest.fixture
def content_root() -> Path:
    """Return the package content root (src/open_workspace_builder/ with content/ and vendor/)."""
    root = Path(__file__).resolve().parent.parent / "src" / "open_workspace_builder"
    assert (root / "content").is_dir(), f"content/ not found at {root}"
    assert (root / "vendor").is_dir(), f"vendor/ not found at {root}"
    return root


@pytest.fixture
def sample_yaml_config(tmp_path: Path) -> Path:
    """Write a minimal YAML config to a temp file and return its path."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "target: custom-output\n"
        "vault:\n"
        "  name: TestVault\n"
        "  create_templates: false\n",
        encoding="utf-8",
    )
    return config_file
