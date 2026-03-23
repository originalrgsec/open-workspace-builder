"""Context file template deployment from content/context/."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_workspace_builder.config import AgentConfigConfig, ContextTemplatesConfig, VaultConfig


def _load_context_template(content_root: Path, filename: str) -> str:
    """Load a context template file from content/context/."""
    template_path = content_root / "content" / "context" / filename
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    return f"# {filename}\n\n(Fill in your details.)\n"


class ContextDeployer:
    """Deploys context file templates and workspace config."""

    def __init__(
        self,
        context_config: ContextTemplatesConfig,
        agent_config: AgentConfigConfig,
        vault_config: VaultConfig,
        content_root: Path,
        dry_run: bool = False,
    ) -> None:
        self._context_config = context_config
        self._agent_config = agent_config
        self._vault_config = vault_config
        self._content_root = content_root
        self._dry_run = dry_run
        self.created_files: list[Path] = []

    def deploy(self, target: Path) -> None:
        """Deploy context templates and workspace config to target."""
        self._deploy_context_templates(target)
        self._deploy_workspace_config(target)

    def _deploy_context_templates(self, target: Path) -> None:
        if not self._context_config.deploy:
            return

        print("=== Deploying Context File Templates ===")
        context_dir = target / self._vault_config.parent_dir

        for filename in self._context_config.files:
            content = _load_context_template(self._content_root, filename)
            deployed_name = filename.replace(".template", "")
            self._write(context_dir / deployed_name, content)

    def _deploy_workspace_config(self, target: Path) -> None:
        if not self._agent_config.deploy:
            return

        print(f"=== Deploying {self._agent_config.filename} ===")
        content = _load_context_template(self._content_root, "claude-md.template.md")
        self._write(
            target / self._agent_config.directory / self._agent_config.filename,
            content,
        )

    def _write(self, path: Path, content: str) -> None:
        if self._dry_run:
            print(f"  [write] {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        self.created_files.append(path)
