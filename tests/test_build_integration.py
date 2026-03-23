"""Integration tests: full build to temp dir, verify output matches expected structure."""

from __future__ import annotations

from pathlib import Path

import pytest

from open_workspace_builder.config import Config, EccConfig, load_config
from open_workspace_builder.engine.builder import WorkspaceBuilder


@pytest.fixture
def built_workspace(tmp_target: Path, content_root: Path) -> Path:
    """Build a full workspace to a temp directory and return the target path."""
    config = Config()
    builder = WorkspaceBuilder(config, content_root)
    builder.build(tmp_target)
    return tmp_target


@pytest.fixture
def built_workspace_with_ecc(tmp_path: Path, content_root: Path) -> Path:
    """Build a workspace with ECC enabled."""
    target = tmp_path / "ws_ecc"
    config = Config(ecc=EccConfig(enabled=True, target_dir=".claude"))
    builder = WorkspaceBuilder(config, content_root)
    builder.build(target)
    return target


class TestVaultStructure:
    """Verify the vault directory tree is created correctly."""

    def test_vault_root_exists(self, built_workspace: Path) -> None:
        vault = built_workspace / "Context" / "Obsidian"
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
        vault = built_workspace / "Context" / "Obsidian"
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
        vault = built_workspace / "Context" / "Obsidian"
        path = vault / filename
        assert path.is_file()
        assert path.read_text(encoding="utf-8").strip() != ""

    def test_vault_index_content(self, built_workspace: Path) -> None:
        vault = built_workspace / "Context" / "Obsidian"
        content = (vault / "_index.md").read_text(encoding="utf-8")
        assert "# Vault Index" in content

    def test_vault_bootstrap_content(self, built_workspace: Path) -> None:
        vault = built_workspace / "Context" / "Obsidian"
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
        templates_dir = built_workspace / "Context" / "Obsidian" / "_templates"
        path = templates_dir / template
        assert path.is_file(), f"Template {template} not found"
        assert path.read_text(encoding="utf-8").strip() != ""

    def test_template_count(self, built_workspace: Path) -> None:
        templates_dir = built_workspace / "Context" / "Obsidian" / "_templates"
        actual = sorted(f.name for f in templates_dir.iterdir() if f.is_file())
        assert actual == sorted(self.EXPECTED_TEMPLATES)


class TestEccDisabledByDefault:
    """Verify ECC is not installed when disabled (default)."""

    def test_no_ecc_dir_by_default(self, built_workspace: Path) -> None:
        assert not (built_workspace / ".ai" / "agents").exists()
        assert not (built_workspace / ".claude" / "agents").exists()


class TestEccInstallation:
    """Verify ECC agents, commands, and rules are installed when enabled."""

    def test_agents_installed(self, built_workspace_with_ecc: Path) -> None:
        agents_dir = built_workspace_with_ecc / ".claude" / "agents"
        assert agents_dir.is_dir()
        agent_files = sorted(f.stem for f in agents_dir.iterdir() if f.is_file())
        assert "architect" in agent_files
        assert "code-reviewer" in agent_files

    def test_commands_installed(self, built_workspace_with_ecc: Path) -> None:
        commands_dir = built_workspace_with_ecc / ".claude" / "commands"
        assert commands_dir.is_dir()
        cmd_files = sorted(f.stem for f in commands_dir.iterdir() if f.is_file())
        assert "plan" in cmd_files
        assert "tdd" in cmd_files

    def test_rules_installed(self, built_workspace_with_ecc: Path) -> None:
        rules_dir = built_workspace_with_ecc / ".claude" / "rules"
        assert rules_dir.is_dir()
        assert (rules_dir / "common" / "coding-style.md").is_file()
        assert (rules_dir / "python" / "coding-style.md").is_file()
        assert (rules_dir / "golang" / "coding-style.md").is_file()


class TestEccTargetDirConfigurable:
    """Verify ECC installs to custom target_dir."""

    def test_custom_target_dir(self, tmp_path: Path, content_root: Path) -> None:
        target = tmp_path / "ws"
        config = Config(ecc=EccConfig(enabled=True, target_dir=".custom-agent"))
        builder = WorkspaceBuilder(config, content_root)
        builder.build(target)
        assert (target / ".custom-agent" / "agents").is_dir()


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
    """Verify context file templates and workspace config are deployed."""

    def test_about_me_deployed(self, built_workspace: Path) -> None:
        path = built_workspace / "Context" / "about-me.md"
        assert path.is_file()
        assert "About Me" in path.read_text(encoding="utf-8")

    def test_brand_voice_deployed(self, built_workspace: Path) -> None:
        path = built_workspace / "Context" / "brand-voice.md"
        assert path.is_file()
        assert "Brand Voice" in path.read_text(encoding="utf-8")

    def test_working_style_deployed(self, built_workspace: Path) -> None:
        path = built_workspace / "Context" / "working-style.md"
        assert path.is_file()
        assert "Working Style" in path.read_text(encoding="utf-8")

    def test_workspace_config_deployed(self, built_workspace: Path) -> None:
        path = built_workspace / ".ai" / "WORKSPACE.md"
        assert path.is_file()
        content = path.read_text(encoding="utf-8")
        assert "Obsidian" in content


class TestAgentConfigConfigurable:
    """Verify workspace config deploys to configured directory/filename."""

    def test_custom_agent_config(self, tmp_path: Path, content_root: Path) -> None:
        from open_workspace_builder.config import AgentConfigConfig

        target = tmp_path / "ws"
        config = Config(agent_config=AgentConfigConfig(directory=".claude", filename="CLAUDE.md"))
        builder = WorkspaceBuilder(config, content_root)
        builder.build(target)
        assert (target / ".claude" / "CLAUDE.md").is_file()


class TestVaultParentDirConfigurable:
    """Verify context files deploy to configured parent dir."""

    def test_custom_parent_dir(self, tmp_path: Path, content_root: Path) -> None:
        from open_workspace_builder.config import VaultConfig

        target = tmp_path / "ws"
        config = Config(vault=VaultConfig(parent_dir="My Context"))
        builder = WorkspaceBuilder(config, content_root)
        builder.build(target)
        assert (target / "My Context" / "Obsidian").is_dir()
        assert (target / "My Context" / "about-me.md").is_file()


class TestAssistantNameInContent:
    """Verify vault bootstrap uses configured assistant_name."""

    def test_default_assistant_name(self, built_workspace: Path) -> None:
        vault = built_workspace / "Context" / "Obsidian"
        bootstrap = (vault / "_bootstrap.md").read_text(encoding="utf-8")
        assert "AI assistant" in bootstrap

    def test_custom_assistant_name(self, tmp_path: Path, content_root: Path) -> None:
        from open_workspace_builder.config import VaultConfig

        target = tmp_path / "ws"
        config = Config(vault=VaultConfig(assistant_name="Claude"))
        builder = WorkspaceBuilder(config, content_root)
        builder.build(target)
        vault = target / "Context" / "Obsidian"
        bootstrap = (vault / "_bootstrap.md").read_text(encoding="utf-8")
        assert "Claude" in bootstrap
        index = (vault / "_index.md").read_text(encoding="utf-8")
        assert "Claude sessions" in index


class TestGenericBuildNoClaude:
    """Verify default build produces workspace with no Claude in dir names."""

    def test_no_claude_in_directory_names(self, built_workspace: Path) -> None:
        for item in built_workspace.rglob("*"):
            if item.is_dir():
                assert "claude" not in item.name.lower(), f"Found 'claude' in dir: {item}"

    def test_no_claude_in_config_filenames(self, built_workspace: Path) -> None:
        config_file = built_workspace / ".ai" / "WORKSPACE.md"
        assert config_file.is_file()
        assert not (built_workspace / ".claude").exists()


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
        vault = tmp_target / "Context" / "TestVault"
        assert vault.is_dir()
        assert (vault / "_index.md").is_file()

    def test_templates_skipped_when_disabled(
        self, tmp_target: Path, content_root: Path, sample_yaml_config: Path
    ) -> None:
        config = load_config(sample_yaml_config)
        builder = WorkspaceBuilder(config, content_root)
        builder.build(tmp_target)
        templates_dir = tmp_target / "Context" / "TestVault" / "_templates"
        # readme.md is always generated; no other templates should exist
        template_files = (
            sorted(f.name for f in templates_dir.iterdir()) if templates_dir.exists() else []
        )
        assert template_files == ["readme.md"]
