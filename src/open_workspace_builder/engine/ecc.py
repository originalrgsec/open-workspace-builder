"""ECC (Everything Claude Code) installation from vendor/ecc/."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_workspace_builder.config import EccConfig


class EccInstaller:
    """Installs curated ECC agents, commands, and rules."""

    def __init__(
        self,
        ecc_config: EccConfig,
        content_root: Path,
        dry_run: bool = False,
    ) -> None:
        self._config = ecc_config
        self._content_root = content_root
        self._dry_run = dry_run
        self.copied_files: list[Path] = []

    def install(self, target: Path) -> None:
        """Install ECC catalog items to target."""
        print("=== Installing ECC Catalog (Curated) ===")
        source = self._content_root / self._config.source_dir

        if not source.exists():
            print(f"  [warn]  ECC source not found at {source}")
            return

        self._install_agents(source, target)
        self._install_commands(source, target)
        self._install_rules(source, target)

    def _install_agents(self, source: Path, target: Path) -> None:
        agents_src = source / "agents"
        agents_dst = target / ".claude" / "agents"
        for agent_name in self._config.agents:
            src_file = agents_src / f"{agent_name}.md"
            if src_file.exists():
                self._copy(src_file, agents_dst / f"{agent_name}.md")
            else:
                print(f"  [warn]  Agent not found: {agent_name}")

    def _install_commands(self, source: Path, target: Path) -> None:
        commands_src = source / "commands"
        commands_dst = target / ".claude" / "commands"
        for cmd_name in self._config.commands:
            src_file = commands_src / f"{cmd_name}.md"
            if src_file.exists():
                self._copy(src_file, commands_dst / f"{cmd_name}.md")
            else:
                print(f"  [warn]  Command not found: {cmd_name}")

    def _install_rules(self, source: Path, target: Path) -> None:
        rules_src = source / "rules"
        rules_dst = target / ".claude" / "rules"
        for category, filenames in self._config.rules.items():
            for fname in filenames:
                src_file = rules_src / category / f"{fname}.md"
                if src_file.exists():
                    self._copy(src_file, rules_dst / category / f"{fname}.md")
                else:
                    print(f"  [warn]  Rule not found: {category}/{fname}")

    def _copy(self, src: Path, dst: Path) -> None:
        if self._dry_run:
            print(f"  [copy]  {src.name} → {dst}")
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        self.copied_files.append(dst)
