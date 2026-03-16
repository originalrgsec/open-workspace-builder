"""Custom skill installation from content/skills/."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from claude_workspace_builder.config import SkillsConfig


class SkillsInstaller:
    """Installs custom Cowork skills."""

    def __init__(
        self,
        skills_config: SkillsConfig,
        content_root: Path,
        dry_run: bool = False,
    ) -> None:
        self._config = skills_config
        self._content_root = content_root
        self._dry_run = dry_run
        self.created_dirs: list[Path] = []
        self.copied_files: list[Path] = []

    def install(self, target: Path) -> None:
        """Install skills to target."""
        print("=== Installing Custom Skills ===")
        source = self._content_root / self._config.source_dir

        if not source.exists():
            print(f"  [warn]  Skills source not found at {source}")
            return

        skills_dst = target / ".skills" / "skills"

        for skill_name in self._config.install:
            skill_src = source / skill_name
            if skill_src.exists():
                print(f"  Installing skill: {skill_name}")
                self._copy_tree(skill_src, skills_dst / skill_name)
            else:
                print(f"  [warn]  Skill not found: {skill_name}")

    def _copy_tree(self, src: Path, dst: Path) -> None:
        """Copy a directory tree, creating destination dirs as needed."""
        if not src.exists():
            print(f"  [warn]  Source not found: {src}")
            return
        for item in sorted(src.rglob("*")):
            rel = item.relative_to(src)
            dest_path = dst / rel
            if item.is_dir():
                self._mkdir(dest_path)
            elif item.is_file():
                self._copy(item, dest_path)

    def _mkdir(self, path: Path) -> None:
        if self._dry_run:
            print(f"  [mkdir] {path}")
        else:
            path.mkdir(parents=True, exist_ok=True)
        self.created_dirs.append(path)

    def _copy(self, src: Path, dst: Path) -> None:
        if self._dry_run:
            print(f"  [copy]  {src.name} → {dst}")
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        self.copied_files.append(dst)
