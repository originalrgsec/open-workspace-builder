"""Click CLI: cwb group with subcommands for init, diff, migrate, and security."""

from __future__ import annotations

import json
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
@click.argument("vault_path", type=click.Path(exists=True))
@click.option(
    "--config", "-c",
    "config_path",
    default=None,
    type=click.Path(exists=True),
    help="Path to YAML config file.",
)
@click.option(
    "--output", "-o",
    "output_file",
    default=None,
    type=click.Path(),
    help="Write JSON report to file.",
)
def diff(vault_path: str, config_path: str | None, output_file: str | None) -> None:
    """Show differences between workspace and reference state."""
    from claude_workspace_builder.engine.differ import (
        diff_report_to_dict,
        diff_workspace,
        format_diff_report,
    )

    config = load_config(config_path)
    content_root = _find_content_root()

    report = diff_workspace(
        Path(vault_path), config=config, content_root=content_root
    )
    click.echo(format_diff_report(report))

    if output_file:
        Path(output_file).write_text(
            json.dumps(diff_report_to_dict(report), indent=2) + "\n",
            encoding="utf-8",
        )
        click.echo(f"\nReport written to {output_file}")

    has_gaps = any(
        report.summary.get(k, 0) > 0 for k in ("missing", "outdated", "modified")
    )
    sys.exit(1 if has_gaps else 0)


@cwb.command()
@click.argument("vault_path", type=click.Path(exists=True))
@click.option(
    "--config", "-c",
    "config_path",
    default=None,
    type=click.Path(exists=True),
    help="Path to YAML config file.",
)
@click.option(
    "--accept-all",
    is_flag=True,
    default=False,
    help="Accept all clean files without prompting (batch mode).",
)
@click.option(
    "--dry-run", "-n",
    is_flag=True,
    default=False,
    help="Show what would happen without writing files.",
)
def migrate(
    vault_path: str,
    config_path: str | None,
    accept_all: bool,
    dry_run: bool,
) -> None:
    """Migrate workspace to latest reference state."""
    from claude_workspace_builder.engine.migrator import (
        format_migrate_report,
        migrate_workspace,
    )

    config = load_config(config_path)
    content_root = _find_content_root()

    report = migrate_workspace(
        Path(vault_path),
        config=config,
        content_root=content_root,
        accept_all=accept_all,
        dry_run=dry_run,
    )
    click.echo(format_migrate_report(report))

    has_blocked = report.summary.get("blocked", 0) > 0
    sys.exit(2 if has_blocked else 0)


@cwb.command()
def ecc() -> None:
    """Manage ECC catalog installation."""
    click.echo("Not yet implemented")
    sys.exit(1)


@cwb.group()
def security() -> None:
    """Security scanning and analysis commands."""


@security.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--layers",
    default="1,2,3",
    help="Comma-separated layer numbers to run (default: 1,2,3).",
)
@click.option(
    "--output", "-o",
    "output_file",
    default=None,
    type=click.Path(),
    help="Write JSON report to file.",
)
def scan(path: str, layers: str, output_file: str | None) -> None:
    """Scan a file or directory for security issues."""
    from claude_workspace_builder.security.scanner import Scanner

    layer_nums = tuple(int(x.strip()) for x in layers.split(",") if x.strip())
    scanner = Scanner(layers=layer_nums)

    target = Path(path)
    if target.is_file():
        verdict = scanner.scan_file(target)
        report_data = {
            "file": verdict.file_path,
            "verdict": verdict.verdict,
            "flags": [
                {
                    "category": f.category,
                    "severity": f.severity,
                    "evidence": f.evidence,
                    "description": f.description,
                    "line_number": f.line_number,
                    "layer": f.layer,
                }
                for f in verdict.flags
            ],
        }
        _print_verdict(verdict.file_path, verdict.verdict, len(verdict.flags))
        has_issues = verdict.verdict in ("flagged", "malicious")
    else:
        report = scanner.scan_directory(target)
        report_data = {
            "directory": report.directory,
            "summary": report.summary,
            "verdicts": [
                {
                    "file": v.file_path,
                    "verdict": v.verdict,
                    "flags": [
                        {
                            "category": f.category,
                            "severity": f.severity,
                            "evidence": f.evidence,
                            "description": f.description,
                            "line_number": f.line_number,
                            "layer": f.layer,
                        }
                        for f in v.flags
                    ],
                }
                for v in report.verdicts
            ],
        }
        for v in report.verdicts:
            _print_verdict(v.file_path, v.verdict, len(v.flags))
        click.echo(f"\nSummary: {report.summary}")
        has_issues = any(
            v.verdict in ("flagged", "malicious") for v in report.verdicts
        )

    if output_file:
        Path(output_file).write_text(
            json.dumps(report_data, indent=2) + "\n", encoding="utf-8"
        )
        click.echo(f"Report written to {output_file}")

    sys.exit(2 if has_issues else 0)


def _print_verdict(file_path: str, verdict: str, flag_count: int) -> None:
    """Print a single file verdict line."""
    icon = {"clean": "OK", "flagged": "WARN", "malicious": "FAIL", "error": "ERR"}
    click.echo(f"[{icon.get(verdict, '??')}] {file_path} — {verdict} ({flag_count} flags)")


@cwb.command(name="package-skills")
def package_skills() -> None:
    """Package custom skills for distribution."""
    click.echo("Not yet implemented")
    sys.exit(1)
