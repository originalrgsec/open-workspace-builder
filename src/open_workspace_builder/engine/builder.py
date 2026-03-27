"""Orchestrator that calls vault, ecc, skills, and context modules."""

from __future__ import annotations

from pathlib import Path

from open_workspace_builder.config import Config
from open_workspace_builder.engine.context import ContextDeployer
from open_workspace_builder.engine.ecc import EccInstaller
from open_workspace_builder.engine.skills import SkillsInstaller
from open_workspace_builder.engine.vault import VaultBuilder


class WorkspaceBuilder:
    """Builds an AI workspace from configuration."""

    REQUIRED_SUBDIRS = ("content", "vendor")

    def __init__(self, config: Config, content_root: Path, dry_run: bool = False) -> None:
        missing = [d for d in self.REQUIRED_SUBDIRS if not (content_root / d).is_dir()]
        if missing:
            raise FileNotFoundError(
                f"Content root {content_root} is missing required directories: "
                f"{', '.join(missing)}. "
                f"Ensure the package is installed correctly or run from the project root."
            )
        self._config = config
        self._content_root = content_root
        self._dry_run = dry_run
        self._vault = VaultBuilder(config.vault, content_root, dry_run)
        self._ecc = EccInstaller(config.ecc, content_root, dry_run)
        self._skills = SkillsInstaller(config.skills, content_root, dry_run)
        self._context = ContextDeployer(
            config.context_templates, config.agent_config, config.vault, content_root, dry_run
        )

    def build(self, target: Path) -> None:
        """Run the full build pipeline."""
        target = target.resolve()
        print(f"Building workspace at: {target}")
        print()

        self._vault.build(target)
        if self._config.ecc.enabled:
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
