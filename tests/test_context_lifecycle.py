"""Tests for context file lifecycle: detect, skip, migrate, status."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from open_workspace_builder.cli import owb
from open_workspace_builder.config import (
    AgentConfigConfig,
    ContextTemplatesConfig,
    VaultConfig,
)
from open_workspace_builder.engine.context import (
    ContextDeployer,
    ContextMigrator,
    _extract_sections,
    _merge_sections,
    has_todo_markers,
)


@pytest.fixture()
def content_root(tmp_path: Path) -> Path:
    """Create a minimal content root with context templates."""
    ctx_dir = tmp_path / "content" / "context"
    ctx_dir.mkdir(parents=True)

    (ctx_dir / "about-me.template.md").write_text(
        "# About Me\n\n## Identity\n\n(Describe your role.)\n\n"
        "## Background\n\n(Fill in your background.)\n",
        encoding="utf-8",
    )
    (ctx_dir / "brand-voice.template.md").write_text(
        "# Brand Voice\n\n## Tone\n\n(Describe your tone.)\n\n"
        "## Vocabulary\n\n(List your terms.)\n",
        encoding="utf-8",
    )
    (ctx_dir / "working-style.template.md").write_text(
        "# Working Style\n\n## Behavior\n\n(Do you want questions first?)\n",
        encoding="utf-8",
    )
    (ctx_dir / "agent-config.template.md").write_text(
        "# WORKSPACE\n\n## Required Context Files\n\nRead these.\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


# ── ContextDeployer: skip existing ────────────────────────────────────────


class TestDeploySkipsExisting:
    def test_deploy_skips_existing_context_files(
        self, content_root: Path, tmp_path: Path
    ) -> None:
        target = tmp_path / "ws"
        target.mkdir()
        # Pre-create about-me.md with custom content
        (target / "about-me.md").write_text("# My Custom About Me\n", encoding="utf-8")

        deployer = ContextDeployer(
            context_config=ContextTemplatesConfig(),
            agent_config=AgentConfigConfig(deploy=False),
            vault_config=VaultConfig(parent_dir=""),
            content_root=content_root,
        )
        deployer.deploy(target)

        # about-me.md should NOT be overwritten
        assert (target / "about-me.md").read_text(encoding="utf-8") == "# My Custom About Me\n"
        # Other files should be created
        assert (target / "brand-voice.md").is_file()
        assert (target / "working-style.md").is_file()

    def test_deploy_creates_stubs_when_missing(
        self, content_root: Path, tmp_path: Path
    ) -> None:
        target = tmp_path / "ws"
        target.mkdir()

        deployer = ContextDeployer(
            context_config=ContextTemplatesConfig(),
            agent_config=AgentConfigConfig(deploy=False),
            vault_config=VaultConfig(parent_dir=""),
            content_root=content_root,
        )
        deployer.deploy(target)

        assert (target / "about-me.md").is_file()
        assert (target / "brand-voice.md").is_file()
        assert (target / "working-style.md").is_file()

    def test_workspace_config_skips_existing(
        self, content_root: Path, tmp_path: Path
    ) -> None:
        target = tmp_path / "ws"
        ai_dir = target / ".ai"
        ai_dir.mkdir(parents=True)
        (ai_dir / "WORKSPACE.md").write_text("# Custom Config\n", encoding="utf-8")

        deployer = ContextDeployer(
            context_config=ContextTemplatesConfig(deploy=False),
            agent_config=AgentConfigConfig(),
            vault_config=VaultConfig(parent_dir=""),
            content_root=content_root,
        )
        deployer.deploy(target)

        assert (ai_dir / "WORKSPACE.md").read_text(encoding="utf-8") == "# Custom Config\n"

    def test_dry_run_still_writes(self, content_root: Path, tmp_path: Path) -> None:
        """Dry run should list files but not check existence (no skip logic)."""
        target = tmp_path / "ws"
        target.mkdir()

        deployer = ContextDeployer(
            context_config=ContextTemplatesConfig(),
            agent_config=AgentConfigConfig(deploy=False),
            vault_config=VaultConfig(parent_dir=""),
            content_root=content_root,
            dry_run=True,
        )
        deployer.deploy(target)

        # Dry run does not create files
        assert not (target / "about-me.md").exists()
        # But tracks them as created_files for reporting
        assert len(deployer.created_files) == 3


# ── Section extraction and merging ────────────────────────────────────────


class TestSectionHelpers:
    def test_extract_sections(self) -> None:
        content = "# Title\n\n## Section A\n\ntext\n\n### Sub B\n\nmore\n\n## Section C\n"
        sections = _extract_sections(content)
        assert sections == ["## Section A", "### Sub B", "## Section C"]

    def test_extract_empty(self) -> None:
        assert _extract_sections("no headings here") == []

    def test_merge_appends_missing(self) -> None:
        existing = "# About Me\n\n## Identity\n\nI am a developer.\n"
        template = (
            "# About Me\n\n## Identity\n\n(Describe your role.)\n\n"
            "## Background\n\n(Fill in your background.)\n"
        )
        result = _merge_sections(existing, template, ["## Background"])
        assert "## Background" in result
        assert "(Fill in your background.)" in result
        assert "I am a developer." in result

    def test_merge_no_missing(self) -> None:
        existing = "# Title\n\n## A\n\ntext\n"
        result = _merge_sections(existing, existing, [])
        assert result == existing


# ── TODO marker detection ─────────────────────────────────────────────────


class TestTodoMarkers:
    def test_stub_file_detected(self, tmp_path: Path) -> None:
        p = tmp_path / "stub.md"
        p.write_text("# About Me\n\n## Identity\n\n(Describe your role.)\n", encoding="utf-8")
        assert has_todo_markers(p) is True

    def test_filled_file_clean(self, tmp_path: Path) -> None:
        p = tmp_path / "filled.md"
        p.write_text(
            "# About Me\n\n## Identity\n\nI am a senior engineer at Acme Corp.\n",
            encoding="utf-8",
        )
        assert has_todo_markers(p) is False

    def test_fill_in_detected(self, tmp_path: Path) -> None:
        p = tmp_path / "partial.md"
        p.write_text("## Background\n\n(Fill in your background.)\n", encoding="utf-8")
        assert has_todo_markers(p) is True


# ── ContextMigrator ───────────────────────────────────────────────────────


class TestContextMigrator:
    def test_migrate_detects_missing_sections(
        self, content_root: Path, tmp_path: Path
    ) -> None:
        target = tmp_path / "ws"
        target.mkdir()
        # Create about-me.md with only Identity section (missing Background)
        (target / "about-me.md").write_text(
            "# About Me\n\n## Identity\n\nI am a developer.\n",
            encoding="utf-8",
        )
        # Create brand-voice and working-style as complete stubs
        (target / "brand-voice.md").write_text(
            "# Brand Voice\n\n## Tone\n\ncasual\n\n## Vocabulary\n\nwords\n",
            encoding="utf-8",
        )
        (target / "working-style.md").write_text(
            "# Working Style\n\n## Behavior\n\nask first\n",
            encoding="utf-8",
        )

        migrator = ContextMigrator(
            content_root, ContextTemplatesConfig(), VaultConfig(parent_dir="")
        )
        migrator.migrate(target, accept_all=True)

        # about-me.md should have Background appended
        content = (target / "about-me.md").read_text(encoding="utf-8")
        assert "## Background" in content
        assert "I am a developer." in content
        assert target / "about-me.md" in migrator.updated_files

    def test_migrate_no_op_when_complete(
        self, content_root: Path, tmp_path: Path
    ) -> None:
        target = tmp_path / "ws"
        target.mkdir()
        # Create all files with all template sections present
        (target / "about-me.md").write_text(
            "# About Me\n\n## Identity\n\nme\n\n## Background\n\nstuff\n",
            encoding="utf-8",
        )
        (target / "brand-voice.md").write_text(
            "# Brand Voice\n\n## Tone\n\ncasual\n\n## Vocabulary\n\nwords\n",
            encoding="utf-8",
        )
        (target / "working-style.md").write_text(
            "# Working Style\n\n## Behavior\n\nask first\n",
            encoding="utf-8",
        )

        migrator = ContextMigrator(
            content_root, ContextTemplatesConfig(), VaultConfig(parent_dir="")
        )
        migrator.migrate(target, accept_all=True)

        assert migrator.updated_files == []
        assert migrator.skipped_files == []


# ── CLI integration ───────────────────────────────────────────────────────


class TestCLIContextStatus:
    def test_status_reports_missing(self, runner: CliRunner, tmp_path: Path) -> None:
        target = tmp_path / "ws"
        target.mkdir()
        result = runner.invoke(owb, ["context", "status", str(target)])
        assert result.exit_code == 0
        assert "[missing]" in result.output

    def test_status_reports_stub(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        target = tmp_path / "ws"
        target.mkdir()
        (target / "about-me.md").write_text(
            "# About Me\n\n(Describe your role.)\n", encoding="utf-8"
        )
        result = runner.invoke(owb, ["context", "status", str(target)])
        assert "[stub]" in result.output

    def test_status_reports_filled(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        target = tmp_path / "ws"
        target.mkdir()
        (target / "about-me.md").write_text(
            "# About Me\n\nI am a senior engineer.\n", encoding="utf-8"
        )
        (target / "brand-voice.md").write_text(
            "# Brand Voice\n\nProfessional tone.\n", encoding="utf-8"
        )
        (target / "working-style.md").write_text(
            "# Working Style\n\nConcise output.\n", encoding="utf-8"
        )
        result = runner.invoke(owb, ["context", "status", str(target)])
        assert "[filled]" in result.output
