"""Tests for vault scaffolding additions (Story S008)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from open_workspace_builder.config import Config, load_config
from open_workspace_builder.engine.builder import WorkspaceBuilder


@pytest.fixture
def built_workspace(tmp_target: Path, content_root: Path) -> Path:
    """Build a full workspace and return the target path."""
    config = Config()
    builder = WorkspaceBuilder(config, content_root)
    builder.build(tmp_target)
    return tmp_target


def _vault_root(workspace: Path) -> Path:
    return workspace / "Context" / "Obsidian"


class TestStatusMdGeneration:
    """status.md should be generated per project tier at build time."""

    @pytest.mark.parametrize("tier", ["Work", "Personal", "Open Source"])
    def test_status_md_exists_per_tier(self, built_workspace: Path, tier: str) -> None:
        status_path = _vault_root(built_workspace) / "projects" / tier / "status.md"
        assert status_path.is_file(), f"status.md missing for tier {tier}"

    @pytest.mark.parametrize("tier", ["Work", "Personal", "Open Source"])
    def test_status_md_has_project_name(self, built_workspace: Path, tier: str) -> None:
        content = (_vault_root(built_workspace) / "projects" / tier / "status.md").read_text(
            encoding="utf-8"
        )
        assert f'project: "{tier}"' in content

    @pytest.mark.parametrize("tier", ["Work", "Personal", "Open Source"])
    def test_status_md_has_creation_date(self, built_workspace: Path, tier: str) -> None:
        content = (_vault_root(built_workspace) / "projects" / tier / "status.md").read_text(
            encoding="utf-8"
        )
        today = date.today().isoformat()
        assert f'created: "{today}"' in content

    def test_status_md_has_last_updated_frontmatter(self, built_workspace: Path) -> None:
        content = (_vault_root(built_workspace) / "projects" / "Personal" / "status.md").read_text(
            encoding="utf-8"
        )
        assert "last-updated:" in content


class TestSelfDirectoryStub:
    """self/ directory should have _index.md pointing to context files."""

    def test_self_index_exists(self, built_workspace: Path) -> None:
        path = _vault_root(built_workspace) / "self" / "_index.md"
        assert path.is_file()

    def test_self_index_references_context_files(self, built_workspace: Path) -> None:
        content = (_vault_root(built_workspace) / "self" / "_index.md").read_text(encoding="utf-8")
        assert "working-style.md" in content
        assert "brand-voice.md" in content
        assert "about-me.md" in content


class TestMobileInboxArchive:
    """research/mobile-inbox/archive/ should exist with .gitkeep."""

    def test_archive_dir_exists(self, built_workspace: Path) -> None:
        archive = _vault_root(built_workspace) / "research" / "mobile-inbox" / "archive"
        assert archive.is_dir()

    def test_gitkeep_exists(self, built_workspace: Path) -> None:
        gitkeep = (
            _vault_root(built_workspace) / "research" / "mobile-inbox" / "archive" / ".gitkeep"
        )
        assert gitkeep.is_file()


class TestTemplatesReadme:
    """_templates/readme.md should always be generated, even when templates are disabled."""

    def test_readme_exists_with_templates_enabled(self, built_workspace: Path) -> None:
        path = _vault_root(built_workspace) / "_templates" / "readme.md"
        assert path.is_file()
        content = path.read_text(encoding="utf-8")
        assert "_templates/" in content

    def test_readme_exists_with_templates_disabled(
        self, tmp_target: Path, content_root: Path, sample_yaml_config: Path
    ) -> None:
        """readme.md is generated even when create_templates is false."""
        config = load_config(sample_yaml_config)
        builder = WorkspaceBuilder(config, content_root)
        builder.build(tmp_target)
        vault = tmp_target / "Context" / "TestVault"
        readme = vault / "_templates" / "readme.md"
        assert readme.is_file()
        content = readme.read_text(encoding="utf-8")
        assert "_templates/" in content

    def test_no_other_templates_when_disabled(
        self, tmp_target: Path, content_root: Path, sample_yaml_config: Path
    ) -> None:
        """Only readme.md should be in _templates when templates are disabled."""
        config = load_config(sample_yaml_config)
        builder = WorkspaceBuilder(config, content_root)
        builder.build(tmp_target)
        vault = tmp_target / "Context" / "TestVault"
        templates_dir = vault / "_templates"
        files = [f.name for f in templates_dir.iterdir() if f.is_file()]
        assert files == ["readme.md"]
