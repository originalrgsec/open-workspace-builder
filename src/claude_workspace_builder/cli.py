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
    """Initialize a new Claude workspace.

    Creates the full directory structure including Obsidian vault, ECC agents/commands/rules,
    custom Cowork skills, context templates, and CLAUDE.md entry point. Defaults work out of
    the box — pass --config to customize which components are installed.
    """
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
    """Show differences between an existing workspace and the reference state.

    Compares VAULT_PATH against a freshly generated reference workspace and reports files
    that are missing, outdated, or modified. Returns exit code 1 if any gaps are found.
    """
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
    """Migrate an existing workspace to the latest reference state.

    Reviews each changed file interactively. Use --accept-all for batch mode.
    Files that fail security scanning are blocked. Returns exit code 2 if any
    files are blocked by security.
    """
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


@cwb.group()
def ecc() -> None:
    """Manage ECC catalog installation."""


@ecc.command()
@click.option(
    "--accept-all",
    is_flag=True,
    default=False,
    help="Auto-accept all non-flagged files (batch mode).",
)
@click.option(
    "--dry-run", "-n",
    is_flag=True,
    default=False,
    help="Fetch and scan but do not write any files.",
)
def update(accept_all: bool, dry_run: bool) -> None:
    """Fetch latest upstream ECC content and selectively apply updates.

    Diffs the upstream Everything Claude Code catalog against your vendored copy,
    runs the security scanner on changed files, and lets you accept or reject each
    update. Use --accept-all to auto-accept files that pass scanning.
    """
    from claude_workspace_builder.engine.ecc_update import (
        FileReview,
        run_update,
    )
    from claude_workspace_builder.security.reputation import FlagEvent, ReputationLedger

    content_root = _find_content_root()
    vendor_dir = content_root / "vendor" / "ecc"

    if not vendor_dir.exists():
        click.echo("Error: vendor/ecc/ not found.")
        sys.exit(1)

    def _interactive_prompt(review: FileReview) -> str:
        d = review.diff
        click.echo(f"\n--- {d.relative_path} [{d.category}] ---")
        if d.unified_diff:
            click.echo(d.unified_diff)

        if review.verdict is not None and hasattr(review.verdict, "verdict"):
            v = review.verdict
            icon = {"clean": "OK", "flagged": "WARN", "malicious": "FAIL"}
            click.echo(f"Security: [{icon.get(v.verdict, '??')}] {v.verdict}")
            if hasattr(v, "flags"):
                for f in v.flags:
                    click.echo(f"  [{f.severity}] {f.category}: {f.description}")

        while True:
            choice = click.prompt(
                "[a]ccept / [r]eject / [d]etail / [q]uit",
                type=str,
                default="r",
            ).lower().strip()
            if choice == "d":
                click.echo(f"\n=== Full content of {d.relative_path} ===")
                continue
            if choice in ("a", "r", "q"):
                return choice

    prompt_fn = None if accept_all else _interactive_prompt

    try:
        results = run_update(
            vendor_dir,
            dry_run=dry_run,
            accept_all=accept_all,
            prompt_fn=prompt_fn,
        )
    except Exception as exc:
        click.echo(f"Error during update: {exc}")
        sys.exit(1)

    ledger = ReputationLedger()
    for r in results:
        if r.action == "blocked":
            event = FlagEvent.now(
                source="ecc",
                file_path=r.relative_path,
                flag_category="security_scan",
                severity="critical",
                disposition="confirmed_malicious",
                details="; ".join(r.flag_details or []),
            )
            ledger.record_event(event)

    if ledger.check_threshold("ecc"):
        click.echo(
            "\n[WARNING] ECC source has exceeded the malicious flag threshold.\n"
            "Recommendation: drop this upstream and freeze on current vendored copy."
        )

    accepted = sum(1 for r in results if r.action == "accepted")
    rejected = sum(1 for r in results if r.action == "rejected")
    blocked = sum(1 for r in results if r.action == "blocked")
    click.echo(f"\nUpdate complete: {accepted} accepted, {rejected} rejected, {blocked} blocked")


@ecc.command()
def status() -> None:
    """Display current ECC status: pinned commit, flag history, recent updates."""
    from claude_workspace_builder.engine.ecc_update import get_status

    content_root = _find_content_root()
    vendor_dir = content_root / "vendor" / "ecc"

    if not vendor_dir.exists():
        click.echo("Error: vendor/ecc/ not found.")
        sys.exit(1)

    info = get_status(vendor_dir)

    click.echo("=== ECC Status ===")
    click.echo(f"  Repo URL:     {info['repo_url']}")
    click.echo(f"  Pinned commit: {info['commit_hash']}")
    click.echo(f"  Last fetch:    {info['fetch_date']}")

    if info["flag_history"]:
        click.echo(f"\n  Flag history ({len(info['flag_history'])} events):")
        for event in info["flag_history"]:
            click.echo(
                f"    [{event['severity']}] {event['file_path']} "
                f"— {event['disposition']} ({event['timestamp']})"
            )
    else:
        click.echo("\n  No flag history for ECC source.")

    if info["recent_updates"]:
        click.echo(f"\n  Recent updates ({len(info['recent_updates'])}):")
        for entry in info["recent_updates"]:
            accepted = len(entry.get("files_accepted", []))
            rejected = len(entry.get("files_rejected", []))
            blocked = len(entry.get("files_blocked", []))
            click.echo(
                f"    {entry.get('timestamp', '?')} — "
                f"{accepted} accepted, {rejected} rejected, {blocked} blocked"
            )
    else:
        click.echo("\n  No update history.")


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
    """Scan a file or directory for security issues.

    Runs a three-layer scanner: structural validation, pattern matching, and
    (optionally) semantic analysis via Claude API. Use --layers to select which
    layers to run. Returns exit code 2 if any issues are found.
    """
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
    """Package custom skills for Cowork distribution. (Coming soon.)"""
    click.echo("Not yet implemented")
    sys.exit(1)
