"""Shared fixtures for tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def load_script(name: str) -> ModuleType:
    """Load a module from `scripts/` by filename stem.

    The release helpers in `scripts/` live outside the `src/` package and
    are invoked by the release workflow via `python scripts/<name>.py`.
    Tests import them via importlib so the scripts can remain dep-free.
    """
    path = SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
        "target: custom-output\nvault:\n  name: TestVault\n  create_templates: false\n",
        encoding="utf-8",
    )
    return config_file
