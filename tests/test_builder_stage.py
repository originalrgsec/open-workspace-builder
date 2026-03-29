"""Tests for builder vault-meta.json stage output."""

from __future__ import annotations

import json
from pathlib import Path

from open_workspace_builder.config import Config, StageConfig
from open_workspace_builder.engine.builder import WorkspaceBuilder


class TestBuilderVaultMeta:
    """Builder writes vault-meta.json with stage information."""

    def test_vault_meta_created(self, tmp_path: Path, content_root: Path) -> None:
        target = tmp_path / "workspace"
        config = Config()
        builder = WorkspaceBuilder(config, content_root)
        builder.build(target)

        vault = target / "Obsidian"
        meta_path = vault / "vault-meta.json"
        assert meta_path.is_file()

    def test_vault_meta_contains_stage(self, tmp_path: Path, content_root: Path) -> None:
        target = tmp_path / "workspace"
        config = Config(stage=StageConfig(current_stage=0))
        builder = WorkspaceBuilder(config, content_root)
        builder.build(target)

        vault = target / "Obsidian"
        meta = json.loads((vault / "vault-meta.json").read_text(encoding="utf-8"))
        assert meta["stage"] == 0

    def test_vault_meta_reflects_configured_stage(
        self, tmp_path: Path, content_root: Path
    ) -> None:
        target = tmp_path / "workspace"
        config = Config(stage=StageConfig(current_stage=2))
        builder = WorkspaceBuilder(config, content_root)
        builder.build(target)

        vault = target / "Obsidian"
        meta = json.loads((vault / "vault-meta.json").read_text(encoding="utf-8"))
        assert meta["stage"] == 2

    def test_vault_meta_contains_version(
        self, tmp_path: Path, content_root: Path
    ) -> None:
        target = tmp_path / "workspace"
        config = Config()
        builder = WorkspaceBuilder(config, content_root)
        builder.build(target)

        vault = target / "Obsidian"
        meta = json.loads((vault / "vault-meta.json").read_text(encoding="utf-8"))
        assert "version" in meta

    def test_vault_meta_is_valid_json(
        self, tmp_path: Path, content_root: Path
    ) -> None:
        target = tmp_path / "workspace"
        config = Config()
        builder = WorkspaceBuilder(config, content_root)
        builder.build(target)

        vault = target / "Obsidian"
        raw = (vault / "vault-meta.json").read_text(encoding="utf-8")
        meta = json.loads(raw)  # should not raise
        assert isinstance(meta, dict)

    def test_dry_run_does_not_write_meta(
        self, tmp_path: Path, content_root: Path
    ) -> None:
        target = tmp_path / "workspace"
        config = Config()
        builder = WorkspaceBuilder(config, content_root, dry_run=True)
        builder.build(target)

        vault = target / "Obsidian"
        # Dry run should not create the file
        assert not (vault / "vault-meta.json").exists()
