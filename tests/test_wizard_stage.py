"""Tests for wizard stage selection step."""

from __future__ import annotations

from pathlib import Path

import pytest

from open_workspace_builder.config import StageConfig
from open_workspace_builder.wizard.setup import _step_stage_selection


class TestStepStageSelection:
    """_step_stage_selection detects or prompts for starting stage."""

    def test_no_vault_returns_stage_0(self, tmp_path: Path) -> None:
        """When no vault exists, default to stage 0."""
        result = _step_stage_selection(vault_path=None)
        assert result.current_stage == 0

    def test_empty_vault_returns_stage_0(self, tmp_path: Path) -> None:
        """Empty vault directory suggests stage 0."""
        vault = tmp_path / "Obsidian"
        vault.mkdir()
        result = _step_stage_selection(vault_path=vault)
        assert result.current_stage == 0

    def test_populated_vault_suggests_stage_1(self, tmp_path: Path) -> None:
        """Vault meeting stage 0 exit criteria suggests stage 1."""
        vault = tmp_path / "Obsidian"
        vault.mkdir()
        (vault / "_index.md").write_text("# Index\nContent here.", encoding="utf-8")
        (vault / "_bootstrap.md").write_text("# Bootstrap\nContent here.", encoding="utf-8")
        self_dir = vault / "self"
        self_dir.mkdir()
        (self_dir / "_index.md").write_text(
            "# Self\nReal content about the user.", encoding="utf-8"
        )
        proj = vault / "projects" / "TestProj"
        proj.mkdir(parents=True)
        (proj / "status.md").write_text("# Status\nActive.", encoding="utf-8")

        result = _step_stage_selection(vault_path=vault)
        assert result.current_stage == 1

    def test_vault_with_meta_stage_reads_it(self, tmp_path: Path) -> None:
        """If vault-meta.json has a stage, use it directly."""
        import json

        vault = tmp_path / "Obsidian"
        vault.mkdir()
        meta = {"version": "0.8.2", "stage": 1}
        (vault / "vault-meta.json").write_text(json.dumps(meta), encoding="utf-8")
        result = _step_stage_selection(vault_path=vault)
        assert result.current_stage == 1

    def test_returns_frozen_stage_config(self, tmp_path: Path) -> None:
        result = _step_stage_selection(vault_path=None)
        assert isinstance(result, StageConfig)
        with pytest.raises(AttributeError):
            result.current_stage = 1  # type: ignore[misc]
