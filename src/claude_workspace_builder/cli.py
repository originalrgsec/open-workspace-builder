"""Click CLI: cwb group with init subcommand and stubs for future commands."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from claude_workspace_builder.config import load_config
from claude_workspace_builder.engine.builder import WorkspaceBuilder


def _find_content_root() -> Path:
    """Find the package content root (where vendor/ and content/ live).

    Walks up from this file's location to find the project root that contains
    the content/ and vendor/ directories. Falls back to cwd.
    """
    # When installed as a package, content is relative to the project root
    # Try common locations
    candidates = [
        Path(__file__).resolve().parent.parent.parent,  # src/claude_workspace_builder/ -> repo root
        Path.cwd(),
    ]
    for candidate in candidates:
        if (candidate / "content").is_dir() and (candidate / "vendor").is_dir():
            return candidate
    return Path.cwd()


@click.group()
@click.version_option(package_name="claude-workspace-builder")
def cwb() -> None:
    """Scaffold, maintain, and secure Claude Code and Cowork workspaces."""


@cwb.command()
@click.option(
    "--target", "-t",
    default=None,
    type=click.Path(),
    help="Target directory for the built workspace (default: ./output/).",
)
@click.option(
    "--config", "-c",
    "config_path",
    default=None,
    type=click.Path(exists=True),
    help="Path to YAML config file.",
)
@click.option(
    "--dry-run", "-n",
    is_flag=True,
    default=False,
    help="Print what would be created without writing anything.",
)
def init(target: str | None, config_path: str | None, dry_run: bool) -> None:
    """Initialize a new Claude workspace (vault, ECC, skills, context)."""
    config = load_config(config_path)
    target_path = Path(target) if target else Path(config.target)
    content_root = _find_content_root()

    builder = WorkspaceBuilder(config, content_root, dry_run=dry_run)
    builder.build(target_path)


@cwb.command()
def diff() -> None:
    """Show differences between workspace and expected state."""
    click.echo("Not yet implemented")
    sys.exit(1)


@cwb.command()
def migrate() -> None:
    """Migrate workspace to latest template version."""
    click.echo("Not yet implemented")
    sys.exit(1)


@cwb.command()
def ecc() -> None:
    """Manage ECC catalog installation."""
    click.echo("Not yet implemented")
    sys.exit(1)


@cwb.command()
def security() -> None:
    """Run security checks on workspace configuration."""
    click.echo("Not yet implemented")
    sys.exit(1)


@cwb.command(name="package-skills")
def package_skills() -> None:
    """Package custom skills for distribution."""
    click.echo("Not yet implemented")
    sys.exit(1)
