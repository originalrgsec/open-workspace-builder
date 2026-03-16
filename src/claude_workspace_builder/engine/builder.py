"""Orchestrator that calls vault, ecc, skills, and context modules."""

from __future__ import annotations

from pathlib import Path

from claude_workspace_builder.config import Config
from claude_workspace_builder.engine.context import ContextDeployer
from claude_workspace_builder.engine.ecc import EccInstaller
from claude_workspace_builder.engine.skills import SkillsInstaller
from claude_workspace_builder.engine.vault import VaultBuilder


class WorkspaceBuilder:
    """Builds a Claude workspace from configuration."""

    def __init__(self, config: Config, content_root: Path, dry_run: bool = False) -> None:
        self._config = config
        self._content_root = content_root
        self._dry_run = dry_run
        self._vault = VaultBuilder(config.vault, content_root, dry_run)
        self._ecc = EccInstaller(config.ecc, content_root, dry_run)
        self._skills = SkillsInstaller(config.skills, content_root, dry_run)
        self._context = ContextDeployer(
            config.context_templates, config.claude_md, content_root, dry_run
        )

    def build(self, target: Path) -> None:
        """Run the full build pipeline."""
        target = target.resolve()
        print(f"Building workspace at: {target}")
        print()

        self._vault.build(target)
        self._ecc.install(target)
        self._skills.install(target)
        self._context.deploy(target)

        created_dirs = len(self._vault.created_dirs) + len(self._skills.created_dirs)
        created_files = len(self._vault.created_files) + len(self._context.created_files)
        copied_files = len(self._ecc.copied_files) + len(self._skills.copied_files)

        print()
        print("Build complete.")
        print(f"  Directories created: {created_dirs}")
        print(f"  Files created:       {created_files}")
        print(f"  Files copied:        {copied_files}")
