"""Context file template deployment from content/context/."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from claude_workspace_builder.config import ClaudeMdConfig, ContextTemplatesConfig


def _load_context_template(content_root: Path, filename: str) -> str:
    """Load a context template file from content/context/."""
    template_path = content_root / "content" / "context" / filename
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    return f"# {filename}\n\n(Fill in your details.)\n"


class ContextDeployer:
    """Deploys context file templates and CLAUDE.md."""

    def __init__(
        self,
        context_config: ContextTemplatesConfig,
        claude_md_config: ClaudeMdConfig,
        content_root: Path,
        dry_run: bool = False,
    ) -> None:
        self._context_config = context_config
        self._claude_md_config = claude_md_config
        self._content_root = content_root
        self._dry_run = dry_run
        self.created_files: list[Path] = []

    def deploy(self, target: Path) -> None:
        """Deploy context templates and CLAUDE.md to target."""
        self._deploy_context_templates(target)
        self._deploy_claude_md(target)

    def _deploy_context_templates(self, target: Path) -> None:
        if not self._context_config.deploy:
            return

        print("=== Deploying Context File Templates ===")
        context_dir = target / "Claude Context"

        for filename in self._context_config.files:
            content = _load_context_template(self._content_root, filename)
            deployed_name = filename.replace(".template", "")
            self._write(context_dir / deployed_name, content)

    def _deploy_claude_md(self, target: Path) -> None:
        if not self._claude_md_config.deploy:
            return

        print("=== Deploying CLAUDE.md Template ===")
        content = _load_context_template(self._content_root, "claude-md.template.md")
        self._write(target / ".claude" / "CLAUDE.md", content)

    def _write(self, path: Path, content: str) -> None:
        if self._dry_run:
            print(f"  [write] {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        self.created_files.append(path)
