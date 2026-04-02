"""Tests for dry-run skip reporting (OWB-S062).

Dry-run mode must report [skip] for files that already exist at the target,
matching the behavior of a real run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from open_workspace_builder.config import (
    AgentConfigConfig,
    Config,
    ContextTemplatesConfig,
    VaultConfig,
)
from open_workspace_builder.engine.context import ContextDeployer
from open_workspace_builder.engine.vault import VaultBuilder


@pytest.fixture
def vault_config() -> VaultConfig:
    return VaultConfig(name="Obsidian", parent_dir="", create_templates=False)


@pytest.fixture
def context_config() -> ContextTemplatesConfig:
    return ContextTemplatesConfig(
        deploy=True,
        files=["about-me.template.md", "working-style.template.md"],
    )


@pytest.fixture
def agent_config() -> AgentConfigConfig:
    return AgentConfigConfig(deploy=True, directory=".claude", filename="CLAUDE.md")


class TestVaultDryRunSkip:
    """VaultBuilder._write() reports [skip] for existing files in dry-run mode."""

    def test_dry_run_skips_existing_files(
        self,
        tmp_path: Path,
        vault_config: VaultConfig,
        content_root: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Pre-create a vault file, then dry-run build. Output must contain [skip]."""
        target = tmp_path / "workspace"
        vault_root = target / vault_config.name
        vault_root.mkdir(parents=True)

        # Pre-create one structural file
        existing = vault_root / "_index.md"
        existing.write_text("# Existing content", encoding="utf-8")

        builder = VaultBuilder(vault_config, content_root, dry_run=True)
        builder.build(target)

        output = capsys.readouterr().out
        assert "[skip]" in output
        assert "_index.md" in output

    def test_dry_run_writes_new_files(
        self,
        tmp_path: Path,
        vault_config: VaultConfig,
        content_root: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Empty target: dry-run must show [write] for files."""
        target = tmp_path / "workspace"
        builder = VaultBuilder(vault_config, content_root, dry_run=True)
        builder.build(target)

        output = capsys.readouterr().out
        assert "[write]" in output


class TestContextDryRunSkip:
    """ContextDeployer must report [skip] / [exists] for existing files in dry-run."""

    def test_dry_run_skips_existing_context_file(
        self,
        tmp_path: Path,
        vault_config: VaultConfig,
        context_config: ContextTemplatesConfig,
        agent_config: AgentConfigConfig,
        content_root: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Pre-create a context file, dry-run deploy. Must show skip, not write."""
        target = tmp_path / "workspace"
        target.mkdir(parents=True)

        # Pre-create about-me.md (deployed name of about-me.template.md)
        existing = target / "about-me.md"
        existing.write_text("# My bio", encoding="utf-8")

        deployer = ContextDeployer(
            context_config, agent_config, vault_config, content_root, dry_run=True
        )
        deployer.deploy(target)

        output = capsys.readouterr().out
        # The existing file must NOT show as [write]
        assert "[write]" not in output or "about-me.md" not in output.split("[write]")[-1].split("\n")[0]
        # Must show a skip/exists indicator for about-me.md
        lines = output.splitlines()
        about_me_lines = [l for l in lines if "about-me.md" in l]
        assert any("[skip]" in l or "[exists]" in l for l in about_me_lines), (
            f"Expected [skip] or [exists] for about-me.md, got: {about_me_lines}"
        )

    def test_dry_run_skips_existing_workspace_config(
        self,
        tmp_path: Path,
        vault_config: VaultConfig,
        context_config: ContextTemplatesConfig,
        agent_config: AgentConfigConfig,
        content_root: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Pre-create CLAUDE.md, dry-run deploy. Must show skip, not write."""
        target = tmp_path / "workspace"
        claude_dir = target / ".claude"
        claude_dir.mkdir(parents=True)
        existing = claude_dir / "CLAUDE.md"
        existing.write_text("# Existing config", encoding="utf-8")

        deployer = ContextDeployer(
            context_config, agent_config, vault_config, content_root, dry_run=True
        )
        deployer.deploy(target)

        output = capsys.readouterr().out
        lines = output.splitlines()
        claude_lines = [l for l in lines if "CLAUDE.md" in l]
        assert any("[skip]" in l or "[exists]" in l for l in claude_lines), (
            f"Expected [skip] or [exists] for CLAUDE.md, got: {claude_lines}"
        )

    def test_dry_run_writes_new_context_files(
        self,
        tmp_path: Path,
        vault_config: VaultConfig,
        context_config: ContextTemplatesConfig,
        agent_config: AgentConfigConfig,
        content_root: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Empty target: dry-run must show [write] for context files."""
        target = tmp_path / "workspace"
        target.mkdir(parents=True)

        deployer = ContextDeployer(
            context_config, agent_config, vault_config, content_root, dry_run=True
        )
        deployer.deploy(target)

        output = capsys.readouterr().out
        assert "[write]" in output


class TestDryRunMatchesRealRun:
    """Dry-run and real-run must agree on which files are skipped vs created."""

    def test_skip_set_matches(
        self,
        tmp_path: Path,
        vault_config: VaultConfig,
        content_root: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Run real build, then dry-run on the same target.

        Every file the real run created should show [skip] in the dry-run,
        and the dry-run should produce zero [write] lines for vault files.
        """
        target = tmp_path / "workspace"

        # Real run first
        real_builder = VaultBuilder(vault_config, content_root, dry_run=False)
        real_builder.build(target)
        capsys.readouterr()  # discard real-run output

        # Dry run on the same populated target
        dry_builder = VaultBuilder(vault_config, content_root, dry_run=True)
        dry_builder.build(target)

        output = capsys.readouterr().out
        lines = output.splitlines()

        # Every vault file line should be [skip], not [write]
        write_lines = [l for l in lines if "[write]" in l]
        assert write_lines == [], (
            f"Dry-run reported [write] for files that already exist: {write_lines}"
        )
