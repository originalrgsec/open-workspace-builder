"""Integration tests: full build to temp dir, verify output matches expected structure."""

from __future__ import annotations

from pathlib import Path

import pytest

from open_workspace_builder.config import Config, load_config
from open_workspace_builder.engine.builder import WorkspaceBuilder


@pytest.fixture
def built_workspace(tmp_target: Path, content_root: Path) -> Path:
    """Build a full workspace to a temp directory and return the target path."""
    config = Config()
    builder = WorkspaceBuilder(config, content_root)
    builder.build(tmp_target)
    return tmp_target


class TestVaultStructure:
    """Verify the vault directory tree is created correctly."""

    def test_vault_root_exists(self, built_workspace: Path) -> None:
        vault = built_workspace / "Claude Context" / "Obsidian"
        assert vault.is_dir()

    @pytest.mark.parametrize(
        "subdir",
        [
            "_templates",
            "self",
            "research",
            "research/inbox",
            "research/processed",
            "research/archive",
            "research/mobile-inbox",
            "research/mobile-inbox/archive",
            "projects",
            "projects/Work",
            "projects/Personal",
            "projects/Open Source",
            "decisions",
            "code",
            "business",
        ],
    )
    def test_vault_directories(self, built_workspace: Path, subdir: str) -> None:
        vault = built_workspace / "Claude Context" / "Obsidian"
        assert (vault / subdir).is_dir()

    @pytest.mark.parametrize(
        "filename",
        [
            "_index.md",
            "_bootstrap.md",
            "self/_index.md",
            "research/_index.md",
            "projects/_index.md",
            "projects/Work/_index.md",
            "projects/Personal/_index.md",
            "projects/Open Source/_index.md",
            "decisions/_index.md",
            "code/_index.md",
            "business/_index.md",
        ],
    )
    def test_vault_structural_files(self, built_workspace: Path, filename: str) -> None:
        vault = built_workspace / "Claude Context" / "Obsidian"
        path = vault / filename
        assert path.is_file()
        assert path.read_text(encoding="utf-8").strip() != ""

    def test_vault_index_content(self, built_workspace: Path) -> None:
        vault = built_workspace / "Claude Context" / "Obsidian"
        content = (vault / "_index.md").read_text(encoding="utf-8")
        assert "# Vault Index" in content

    def test_vault_bootstrap_content(self, built_workspace: Path) -> None:
        vault = built_workspace / "Claude Context" / "Obsidian"
        content = (vault / "_bootstrap.md").read_text(encoding="utf-8")
        assert "# Bootstrap" in content
        assert "Project Manifest" in content


class TestTemplates:
    """Verify vault templates are installed."""

    EXPECTED_TEMPLATES = [
        "adr.md",
        "budget-draw-schedule.md",
        "decision-record.md",
        "financing-tracker.md",
        "mobile-inbox.md",
        "post-mortem.md",
        "prd.md",
        "project-index.md",
        "readme.md",
        "research-note.md",
        "roadmap.md",
        "sdr.md",
        "selections-tracker.md",
        "session-log.md",
        "spec.md",
        "status.md",
        "story.md",
        "threat-model.md",
        "vendor-contact-list.md",
    ]

    @pytest.mark.parametrize("template", EXPECTED_TEMPLATES)
    def test_template_exists(self, built_workspace: Path, template: str) -> None:
        templates_dir = built_workspace / "Claude Context" / "Obsidian" / "_templates"
        path = templates_dir / template
        assert path.is_file(), f"Template {template} not found"
        assert path.read_text(encoding="utf-8").strip() != ""

    def test_template_count(self, built_workspace: Path) -> None:
        templates_dir = built_workspace / "Claude Context" / "Obsidian" / "_templates"
        actual = sorted(f.name for f in templates_dir.iterdir() if f.is_file())
        assert actual == sorted(self.EXPECTED_TEMPLATES)


class TestEccInstallation:
    """Verify ECC agents, commands, and rules are installed."""

    def test_agents_installed(self, built_workspace: Path) -> None:
        agents_dir = built_workspace / ".claude" / "agents"
        assert agents_dir.is_dir()
        agent_files = sorted(f.stem for f in agents_dir.iterdir() if f.is_file())
        assert "architect" in agent_files
        assert "code-reviewer" in agent_files

    def test_commands_installed(self, built_workspace: Path) -> None:
        commands_dir = built_workspace / ".claude" / "commands"
        assert commands_dir.is_dir()
        cmd_files = sorted(f.stem for f in commands_dir.iterdir() if f.is_file())
        assert "plan" in cmd_files
        assert "tdd" in cmd_files

    def test_rules_installed(self, built_workspace: Path) -> None:
        rules_dir = built_workspace / ".claude" / "rules"
        assert rules_dir.is_dir()
        assert (rules_dir / "common" / "coding-style.md").is_file()
        assert (rules_dir / "python" / "coding-style.md").is_file()
        assert (rules_dir / "golang" / "coding-style.md").is_file()


class TestSkillsInstallation:
    """Verify custom skills are installed."""

    @pytest.mark.parametrize(
        "skill",
        ["mobile-inbox-triage", "vault-audit", "oss-health-check"],
    )
    def test_skill_installed(self, built_workspace: Path, skill: str) -> None:
        skill_dir = built_workspace / ".skills" / "skills" / skill
        assert skill_dir.is_dir()
        assert (skill_dir / "SKILL.md").is_file()


class TestContextFiles:
    """Verify context file templates and CLAUDE.md are deployed."""

    def test_about_me_deployed(self, built_workspace: Path) -> None:
        path = built_workspace / "Claude Context" / "about-me.md"
        assert path.is_file()
        assert "About Me" in path.read_text(encoding="utf-8")

    def test_brand_voice_deployed(self, built_workspace: Path) -> None:
        path = built_workspace / "Claude Context" / "brand-voice.md"
        assert path.is_file()
        assert "Brand Voice" in path.read_text(encoding="utf-8")

    def test_working_style_deployed(self, built_workspace: Path) -> None:
        path = built_workspace / "Claude Context" / "working-style.md"
        assert path.is_file()
        assert "Working Style" in path.read_text(encoding="utf-8")

    def test_claude_md_deployed(self, built_workspace: Path) -> None:
        path = built_workspace / ".claude" / "CLAUDE.md"
        assert path.is_file()
        content = path.read_text(encoding="utf-8")
        assert "CLAUDE.md" in content
        assert "Obsidian" in content


class TestDryRun:
    """Verify dry run mode doesn't write files."""

    def test_dry_run_creates_no_files(self, tmp_target: Path, content_root: Path) -> None:
        config = Config()
        builder = WorkspaceBuilder(config, content_root, dry_run=True)
        builder.build(tmp_target)
        assert not tmp_target.exists()


class TestYamlConfigBuild:
    """Verify build works with YAML config overlay."""

    def test_custom_vault_name(
        self, tmp_target: Path, content_root: Path, sample_yaml_config: Path
    ) -> None:
        config = load_config(sample_yaml_config)
        builder = WorkspaceBuilder(config, content_root)
        builder.build(tmp_target)
        vault = tmp_target / "Claude Context" / "TestVault"
        assert vault.is_dir()
        assert (vault / "_index.md").is_file()

    def test_templates_skipped_when_disabled(
        self, tmp_target: Path, content_root: Path, sample_yaml_config: Path
    ) -> None:
        config = load_config(sample_yaml_config)
        builder = WorkspaceBuilder(config, content_root)
        builder.build(tmp_target)
        templates_dir = tmp_target / "Claude Context" / "TestVault" / "_templates"
        # readme.md is always generated; no other templates should exist
        template_files = sorted(f.name for f in templates_dir.iterdir()) if templates_dir.exists() else []
        assert template_files == ["readme.md"]
