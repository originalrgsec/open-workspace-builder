"""Context file template deployment, lifecycle detection, and migration."""

from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_workspace_builder.config import AgentConfigConfig, ContextTemplatesConfig, VaultConfig

# Patterns that indicate a template stub has not been filled in.
_TODO_PATTERNS = re.compile(
    r"\(Describe your|\(Fill in|\(List your|\(Years of|\(Do you want"
    r"|\(What is your|\(Any token|\(MCP >|\(Which tools"
    r"|\(Headers,|\(Anti-patterns|\(What the agent can|\(What requires"
    r"|\(Domains to|\(Your business|\(Types of work|\(novice/mid/expert\)"
    r"|\(One-sentence description"
)

# Matches markdown ## and ### heading lines. Module-level compile avoids
# re-compiling on every _extract_sections() call.
_HEADING_RE = re.compile(r"^#{2,3}\s+")


def _load_context_template(content_root: Path, filename: str) -> str:
    """Load a context template file from content/context/."""
    template_path = content_root / "content" / "context" / filename
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    return f"# {filename}\n\n(Fill in your details.)\n"


def has_todo_markers(path: Path) -> bool:
    """Return True if the file contains template placeholder text."""
    content = path.read_text(encoding="utf-8")
    return bool(_TODO_PATTERNS.search(content))


def _extract_sections(content: str) -> list[str]:
    """Return list of markdown heading lines (## and ### level)."""
    return [line.strip() for line in content.splitlines() if _HEADING_RE.match(line)]


def _merge_sections(existing: str, template: str, missing_headings: list[str]) -> str:
    """Append missing template sections to the end of existing content.

    For each missing heading, extracts the heading and all lines until the next
    heading (or end of file) from the template, then appends them.
    """
    template_lines = template.splitlines(keepends=True)
    chunks_to_add: list[str] = []

    for heading in missing_headings:
        # Find the heading line in template
        start_idx = None
        for i, line in enumerate(template_lines):
            if line.strip() == heading:
                start_idx = i
                break
        if start_idx is None:
            continue

        # Collect lines from heading until the next heading of same or higher level
        heading_level = len(heading) - len(heading.lstrip("#"))
        chunk_lines = [template_lines[start_idx]]
        for j in range(start_idx + 1, len(template_lines)):
            line = template_lines[j]
            match = re.match(r"^(#{2,3})\s+", line)
            if match and len(match.group(1)) <= heading_level:
                break
            chunk_lines.append(line)

        chunks_to_add.append("".join(chunk_lines))

    if not chunks_to_add:
        return existing

    result = existing.rstrip("\n") + "\n"
    for chunk in chunks_to_add:
        result += "\n" + chunk

    return result


def _show_diff(old: str, new: str, filename: str) -> None:
    """Print a unified diff between old and new content."""
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=filename, tofile=filename)
    for line in diff:
        print(line, end="")
    print()


_POLICY_COMPLIANCE_PREAMBLE = """\
## Policy Compliance

Before writing any code, running any implementation skill, or starting a sprint:
the rules deployed to this workspace's rules directory contain enforceable policy
requirements extracted from the project's governance documents. These rules are
loaded automatically and must be followed. The full policy documents are available
in the project's vault or documentation directory for detailed context when needed.

Do not proceed with implementation if a policy rule conflicts with the current task.
Escalate to the owner with options and tradeoffs.
"""


def _policy_compliance_preamble(content_root: Path) -> str:
    """Return the policy compliance preamble if policies exist, empty string otherwise."""
    policies_dir = content_root / "content" / "policies"
    if not policies_dir.is_dir():
        return ""
    has_policies = any(f.is_file() and f.suffix == ".md" for f in policies_dir.iterdir())
    return _POLICY_COMPLIANCE_PREAMBLE if has_policies else ""


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

        print("=== Context Files ===")
        parent = self._vault_config.parent_dir
        context_dir = target / parent if parent else target

        for filename in self._context_config.files:
            deployed_name = filename.replace(".template", "")
            dest = context_dir / deployed_name

            if dest.exists():
                print(f"  [exists] {dest} — skipping (use 'owb context migrate' to reformat)")
                continue

            content = _load_context_template(self._content_root, filename)
            self._write(dest, content)

    def _deploy_workspace_config(self, target: Path) -> None:
        if not self._agent_config.deploy:
            return

        dest = target / self._agent_config.directory / self._agent_config.filename

        if dest.exists():
            print(f"  [exists] {dest} — skipping")
            return

        print(f"=== Deploying {self._agent_config.filename} ===")
        content = _load_context_template(self._content_root, "agent-config.template.md")
        preamble = _policy_compliance_preamble(self._content_root)
        if preamble:
            content = content.rstrip("\n") + "\n\n" + preamble
        self._write(dest, content)

    def _write(self, path: Path, content: str) -> None:
        if self._dry_run:
            print(f"  [write] {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        self.created_files.append(path)


class ContextMigrator:
    """Interactive reformat of existing context files against templates."""

    def __init__(
        self,
        content_root: Path,
        context_config: ContextTemplatesConfig,
        vault_config: VaultConfig,
    ) -> None:
        self._content_root = content_root
        self._context_config = context_config
        self._vault_config = vault_config
        self.updated_files: list[Path] = []
        self.skipped_files: list[Path] = []

    def migrate(self, target: Path, *, accept_all: bool = False) -> None:
        """Compare existing context files against templates and offer reformatting."""
        import click

        parent = self._vault_config.parent_dir
        context_dir = target / parent if parent else target

        print("=== Context File Migration ===")

        for filename in self._context_config.files:
            deployed_name = filename.replace(".template", "")
            existing_path = context_dir / deployed_name

            if not existing_path.exists():
                print(f"  [missing] {deployed_name} — run 'owb init' to create stub")
                continue

            template_content = _load_context_template(self._content_root, filename)
            existing_content = existing_path.read_text(encoding="utf-8")

            template_sections = _extract_sections(template_content)
            existing_sections = _extract_sections(existing_content)

            missing = [s for s in template_sections if s not in existing_sections]
            if not missing:
                print(f"  [ok] {deployed_name} — all template sections present")
                continue

            proposed = _merge_sections(existing_content, template_content, missing)
            print(f"\n  {deployed_name}: {len(missing)} missing section(s):")
            for s in missing:
                print(f"    + {s}")

            _show_diff(existing_content, proposed, deployed_name)

            if accept_all or click.confirm(f"  Apply reformatted {deployed_name}?", default=False):
                existing_path.write_text(proposed, encoding="utf-8")
                print(f"  [updated] {deployed_name}")
                self.updated_files.append(existing_path)
            else:
                print(f"  [skipped] {deployed_name}")
                self.skipped_files.append(existing_path)
