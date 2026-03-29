"""Click CLI: owb group with subcommands for init, diff, migrate, and security."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from open_workspace_builder.config import load_config
from open_workspace_builder.engine.builder import WorkspaceBuilder


def _find_content_root() -> Path:
    """Find the package content root (where vendor/ and content/ live).

    Walks up from this file's location to find the project root that contains
    the content/ and vendor/ directories. Raises FileNotFoundError if neither
    candidate contains the required directories.
    """
    candidates = [
        Path(__file__).resolve().parent.parent.parent,  # src/open_workspace_builder/ -> repo root
        Path.cwd(),
    ]
    for candidate in candidates:
        if (candidate / "content").is_dir() and (candidate / "vendor").is_dir():
            return candidate
    checked = ", ".join(str(c) for c in candidates)
    raise FileNotFoundError(
        f"Could not find content/ and vendor/ directories. "
        f"Checked: {checked}. "
        f"Run this command from the project root or install the package correctly."
    )


@click.group()
@click.version_option(package_name="open-workspace-builder")
@click.pass_context
def owb(ctx: click.Context) -> None:
    """Scaffold, maintain, and secure AI coding workspaces."""
    from open_workspace_builder.config import _detect_cli_name

    ctx.ensure_object(dict)
    ctx.obj["cli_name"] = _detect_cli_name()


@owb.command()
@click.option(
    "--target",
    "-t",
    default=None,
    type=click.Path(),
    help="Target directory for the built workspace (default: ./output/).",
)
@click.option(
    "--config",
    "-c",
    "config_path",
    default=None,
    type=click.Path(exists=True),
    help="Path to YAML config file.",
)
@click.option(
    "--dry-run",
    "-n",
    is_flag=True,
    default=False,
    help="Print what would be created without writing anything.",
)
@click.option(
    "--from-vault",
    "from_vault",
    default=None,
    type=click.Path(exists=True),
    help="Generate config from existing vault.",
)
@click.option(
    "--no-wizard",
    is_flag=True,
    default=False,
    help="Skip interactive wizard, use defaults.",
)
@click.pass_context
def init(
    ctx: click.Context,
    target: str | None,
    config_path: str | None,
    dry_run: bool,
    from_vault: str | None,
    no_wizard: bool,
) -> None:
    """Initialize a new AI workspace.

    On first run (no config exists), launches an interactive wizard. Use --no-wizard
    to skip it, --config to provide a pre-written config, or --from-vault to generate
    config from an existing Obsidian vault.
    """
    cli_name = ctx.obj["cli_name"]

    if from_vault is not None:
        from open_workspace_builder.wizard.vault_scan import scan_vault

        config = scan_vault(Path(from_vault), cli_name=cli_name)
    elif config_path is not None:
        config = load_config(config_path, cli_name=cli_name)
    elif no_wizard:
        config = load_config(cli_name=cli_name)
    else:
        # Check if user config already exists
        user_config = Path.home() / f".{cli_name}" / "config.yaml"
        if user_config.exists():
            config = load_config(cli_name=cli_name)
        else:
            from open_workspace_builder.wizard.setup import run_setup_wizard

            config = run_setup_wizard(cli_name=cli_name)

    target_path = Path(target) if target else Path(config.target)
    content_root = _find_content_root()

    builder = WorkspaceBuilder(config, content_root, dry_run=dry_run)
    builder.build(target_path)


@owb.command()
@click.argument("vault_path", type=click.Path(exists=True))
@click.option(
    "--config",
    "-c",
    "config_path",
    default=None,
    type=click.Path(exists=True),
    help="Path to YAML config file.",
)
@click.option(
    "--output",
    "-o",
    "output_file",
    default=None,
    type=click.Path(),
    help="Write JSON report to file.",
)
@click.pass_context
def diff(
    ctx: click.Context, vault_path: str, config_path: str | None, output_file: str | None
) -> None:
    """Show differences between an existing workspace and the reference state.

    Compares VAULT_PATH against a freshly generated reference workspace and reports files
    that are missing, outdated, or modified. Returns exit code 1 if any gaps are found.
    """
    from open_workspace_builder.engine.differ import (
        diff_report_to_dict,
        diff_workspace,
        format_diff_report,
    )

    config = load_config(config_path, cli_name=ctx.obj["cli_name"])
    content_root = _find_content_root()

    report = diff_workspace(Path(vault_path), config=config, content_root=content_root)
    click.echo(format_diff_report(report))

    if output_file:
        Path(output_file).write_text(
            json.dumps(diff_report_to_dict(report), indent=2) + "\n",
            encoding="utf-8",
        )
        click.echo(f"\nReport written to {output_file}")

    has_gaps = any(report.summary.get(k, 0) > 0 for k in ("missing", "outdated", "modified"))
    sys.exit(1 if has_gaps else 0)


@owb.command()
@click.argument("vault_path", type=click.Path(exists=True))
@click.option(
    "--config",
    "-c",
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
    "--dry-run",
    "-n",
    is_flag=True,
    default=False,
    help="Show what would happen without writing files.",
)
@click.pass_context
def migrate(
    ctx: click.Context,
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
    from open_workspace_builder.engine.migrator import (
        format_migrate_report,
        migrate_workspace,
    )

    config = load_config(config_path, cli_name=ctx.obj["cli_name"])
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


@owb.command("update")
@click.argument("source")
@click.option(
    "--accept-all",
    is_flag=True,
    default=False,
    help="Auto-accept all non-flagged files (batch mode).",
)
@click.option(
    "--dry-run",
    "-n",
    is_flag=True,
    default=False,
    help="Fetch and scan but do not write any files.",
)
@click.pass_context
def update_source(
    ctx: click.Context,
    source: str,
    accept_all: bool,
    dry_run: bool,
) -> None:
    """Fetch latest content from SOURCE and selectively apply updates.

    Runs the multi-source update pipeline: clone/fetch, discover files,
    per-file security scan, repo-level audit, then accept/reject per file.
    Use --accept-all to auto-accept files that pass scanning.
    """
    from open_workspace_builder.security.scanner import Scanner
    from open_workspace_builder.sources.audit import RepoAuditor
    from open_workspace_builder.sources.discovery import SourceConfig, SourceDiscovery
    from open_workspace_builder.sources.updater import SourceUpdater

    config = load_config(cli_name=ctx.obj["cli_name"])

    if source not in config.sources.entries:
        click.echo(f"Error: source {source!r} not found in config.")
        click.echo(f"Available sources: {', '.join(config.sources.entries.keys()) or '(none)'}")
        sys.exit(1)

    entry = config.sources.entries[source]
    source_cfg = SourceConfig(
        name=source,
        repo_url=entry.repo_url,
        pin=entry.pin,
        discovery_method=entry.discovery_method,
        patterns=entry.patterns,
        exclude=entry.exclude,
    )

    scanner = Scanner(layers=(1, 2), security_config=config.security)
    discovery = SourceDiscovery([source_cfg])
    auditor = RepoAuditor(scanner)

    content_root = _find_content_root()
    vendor_dir = content_root / "vendor" / source

    def _prompt(rel_path: str, verdict: object) -> str:
        click.echo(f"\n--- {rel_path} ---")
        if verdict is not None and hasattr(verdict, "verdict"):
            icon = {"clean": "OK", "flagged": "WARN", "malicious": "FAIL"}
            click.echo(f"Security: [{icon.get(verdict.verdict, '??')}] {verdict.verdict}")
        while True:
            choice = (
                click.prompt("[a]ccept / [r]eject / [q]uit", type=str, default="r").lower().strip()
            )
            if choice in ("a", "r", "q"):
                return choice

    prompt_fn = None if accept_all else _prompt
    updater = SourceUpdater(config, scanner, discovery, auditor)

    try:
        summary = updater.update(
            source,
            interactive=not accept_all,
            prompt_fn=prompt_fn,
            dry_run=dry_run,
            vendor_dir=vendor_dir,
        )
    except Exception as exc:
        click.echo(f"Error during update: {exc}")
        sys.exit(1)

    if summary.audit_verdict == "block":
        click.echo(f"\n[BLOCKED] Repo audit blocked source {source!r}.")
        for path in summary.files_blocked:
            click.echo(f"  - {path}")
        sys.exit(2)

    accepted = len(summary.files_accepted)
    rejected = len(summary.files_rejected)
    blocked = len(summary.files_blocked)
    warned = len(summary.files_warned)
    click.echo(
        f"\nUpdate complete: {accepted} accepted, {rejected} rejected, "
        f"{blocked} blocked, {warned} warned"
    )


@owb.group()
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
    "--dry-run",
    "-n",
    is_flag=True,
    default=False,
    help="Fetch and scan but do not write any files.",
)
def update(accept_all: bool, dry_run: bool) -> None:
    """Fetch latest upstream ECC content and selectively apply updates.

    Diffs the upstream Everything Code Catalog against your vendored copy,
    runs the security scanner on changed files, and lets you accept or reject each
    update. Use --accept-all to auto-accept files that pass scanning.
    """
    from open_workspace_builder.engine.ecc_update import (
        FileReview,
        run_update,
    )
    from open_workspace_builder.security.reputation import FlagEvent, ReputationLedger

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
            choice = (
                click.prompt(
                    "[a]ccept / [r]eject / [d]etail / [q]uit",
                    type=str,
                    default="r",
                )
                .lower()
                .strip()
            )
            if choice == "d":
                click.echo(f"\n=== Full content of {d.relative_path} ===")
                continue
            if choice in ("a", "r", "q"):
                return choice

    prompt_fn = None if accept_all else _interactive_prompt

    try:
        from open_workspace_builder.config import SecurityConfig

        security_config = SecurityConfig()
        results = run_update(
            vendor_dir,
            dry_run=dry_run,
            accept_all=accept_all,
            prompt_fn=prompt_fn,
            trusted_upstream_urls=security_config.trusted_upstream_urls,
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
        elif r.warnings:
            event = FlagEvent.now(
                source="ecc",
                file_path=r.relative_path,
                flag_category="security_scan",
                severity="warning",
                disposition="flagged",
                details="; ".join(r.warnings),
            )
            ledger.record_event(event)
            click.echo(f"  [WARN] {r.relative_path}: {'; '.join(r.warnings)}")

    if ledger.check_threshold("ecc"):
        click.echo(
            "\n[WARNING] ECC source has exceeded the malicious flag threshold.\n"
            "Recommendation: drop this upstream and freeze on current vendored copy."
        )

    accepted = sum(1 for r in results if r.action == "accepted")
    rejected = sum(1 for r in results if r.action == "rejected")
    blocked = sum(1 for r in results if r.action == "blocked")
    warned = sum(1 for r in results if r.warnings and r.action == "accepted")
    click.echo(
        f"\nUpdate complete: {accepted} accepted, {rejected} rejected, "
        f"{blocked} blocked, {warned} warned"
    )


@ecc.command()
def status() -> None:
    """Display current ECC status: pinned commit, flag history, recent updates."""
    from open_workspace_builder.engine.ecc_update import get_status

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


@owb.group()
def security() -> None:
    """Security scanning and analysis commands."""


@security.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--layers",
    default=None,
    help="Comma-separated layer numbers to run (default: from config or 1,2,3).",
)
@click.option(
    "--config",
    "-c",
    "config_path",
    default=None,
    type=click.Path(exists=True),
    help="Path to YAML config file.",
)
@click.option(
    "--output",
    "-o",
    "output_file",
    default=None,
    type=click.Path(),
    help="Write JSON report to file.",
)
@click.option(
    "--sca",
    is_flag=True,
    default=False,
    help="Run SCA (pip-audit + GuardDog) on discovered dependencies.",
)
@click.option(
    "--sast",
    is_flag=True,
    default=False,
    help="Run SAST (Semgrep) on source code.",
)
@click.option(
    "--correlate",
    is_flag=True,
    default=False,
    help="Run cross-file correlation analysis on directories (requires Layer 3).",
)
@click.pass_context
def scan(
    ctx: click.Context,
    path: str,
    layers: str | None,
    config_path: str | None,
    output_file: str | None,
    sca: bool,
    sast: bool,
    correlate: bool,
) -> None:
    """Scan a file or directory for security issues.

    Runs a three-layer scanner: structural validation, pattern matching, and
    (optionally) semantic analysis via LLM. Use --layers to select which
    layers to run. Use --sca for dependency scanning, --sast for Semgrep
    static analysis, and --correlate for cross-file correlation on directories.
    Returns exit code 2 if any issues are found.
    """
    from open_workspace_builder.security.scanner import Scanner

    config = load_config(config_path, cli_name=ctx.obj.get("cli_name"))
    layer_nums = (
        tuple(int(x.strip()) for x in layers.split(",") if x.strip())
        if layers is not None
        else None
    )

    # Resolve SCA/SAST from flags or config defaults
    run_sca = sca or config.security.sca_enabled
    run_sast = sast or config.security.sast_enabled

    # Construct ModelBackend for Layer 3 if requested.
    backend = None
    effective_layers = layer_nums if layer_nums is not None else config.security.scanner_layers
    if 3 in effective_layers:
        try:
            from open_workspace_builder.llm.backend import ModelBackend

            backend = ModelBackend(models_config=config.models)
        except ImportError:
            pass  # Layer 3 will be skipped gracefully (no backend)

    scanner = Scanner(layers=layer_nums, backend=backend, security_config=config.security)

    target = Path(path)
    if target.is_file():
        verdict = scanner.scan_file(target)
        report_data: dict = {
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
        report = (
            scanner.scan_package(target)
            if correlate
            else scanner.scan_directory(target)
        )
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
        has_issues = any(v.verdict in ("flagged", "malicious") for v in report.verdicts)

    # SCA scanning
    if run_sca:
        sca_data = _run_sca_scan(target)
        report_data["sca"] = sca_data
        if sca_data.get("vulnerabilities") or sca_data.get("guarddog_flagged"):
            has_issues = True

    # SAST scanning
    if run_sast:
        sast_data = _run_sast_scan(target)
        report_data["sast"] = sast_data
        if any(f.get("severity") == "ERROR" for f in sast_data.get("findings", [])):
            has_issues = True

    if output_file:
        Path(output_file).write_text(json.dumps(report_data, indent=2) + "\n", encoding="utf-8")
        click.echo(f"Report written to {output_file}")

    sys.exit(2 if has_issues else 0)


def _run_sca_scan(target: Path) -> dict:
    """Run SCA scanning on discovered dependencies and return JSON-compatible dict."""
    from open_workspace_builder.security.dep_audit import audit_single_package
    from open_workspace_builder.security.dep_discovery import discover_dependencies

    packages = discover_dependencies(target)
    if not packages:
        click.echo("\n--- SCA: No dependencies discovered ---")
        return {"vulnerabilities": [], "guarddog_flagged": [], "packages_scanned": []}

    click.echo(f"\n--- SCA: Scanning {len(packages)} discovered dependencies ---")

    all_vulns: list[dict] = []
    all_flagged: list[dict] = []
    scanned: list[str] = []

    for pkg in packages:
        try:
            report = audit_single_package(pkg)
            scanned.append(pkg)
            for f in report.vuln_report.findings:
                all_vulns.append({
                    "package": f.package,
                    "installed_version": f.installed_version,
                    "vuln_id": f.vuln_id,
                    "fix_version": f.fix_version,
                    "description": f.description,
                })
            for f in report.guarddog_report.flagged:
                all_flagged.append({
                    "package": f.package,
                    "rule_name": f.rule_name,
                    "severity": f.severity,
                    "file_path": f.file_path,
                    "evidence": f.evidence,
                })
        except (ImportError, RuntimeError) as exc:
            click.echo(f"  [skip] {pkg}: {exc}")

    if all_vulns:
        click.echo(f"\n[SCA-VULN] {len(all_vulns)} vulnerabilities found:")
        for v in all_vulns:
            fix_str = f" (fix: {v['fix_version']})" if v.get("fix_version") else ""
            click.echo(f"  {v['package']}  {v['vuln_id']}{fix_str}")
    else:
        click.echo("\n[SCA-OK] No known vulnerabilities in discovered dependencies.")

    if all_flagged:
        click.echo(f"\n[SCA-MALWARE] {len(all_flagged)} guarddog findings:")
        for f in all_flagged:
            click.echo(f"  [{f['severity']}] {f['package']} — {f['rule_name']}")
    elif scanned:
        click.echo("[SCA-OK] GuardDog: all scanned packages clean.")

    return {
        "vulnerabilities": all_vulns,
        "guarddog_flagged": all_flagged,
        "packages_scanned": scanned,
    }


def _run_sast_scan(target: Path) -> dict:
    """Run SAST scanning via Semgrep and return JSON-compatible dict."""
    from open_workspace_builder.security.sast import run_semgrep

    click.echo(f"\n--- SAST: Running Semgrep on {target} ---")
    try:
        report = run_semgrep(target)
    except ImportError:
        click.echo("  [skip] semgrep not installed")
        return {"findings": [], "errors": ["semgrep not installed"], "rules_run": 0}
    except RuntimeError as exc:
        click.echo(f"  [error] {exc}")
        return {"findings": [], "errors": [str(exc)], "rules_run": 0}

    findings_data = [
        {
            "rule_id": f.rule_id,
            "severity": f.severity,
            "message": f.message,
            "file": f.file,
            "line": f.line,
            "code": f.code,
        }
        for f in report.findings
    ]

    errors_by_severity = {"ERROR": 0, "WARNING": 0, "INFO": 0}
    for f in report.findings:
        errors_by_severity[f.severity] = errors_by_severity.get(f.severity, 0) + 1

    if report.findings:
        click.echo(f"\n[SAST] {len(report.findings)} findings:")
        for f in report.findings:
            click.echo(f"  [{f.severity}] {f.rule_id}")
            click.echo(f"    {f.file}:{f.line}")
    else:
        click.echo("\n[SAST-OK] No findings.")

    return {
        "findings": findings_data,
        "errors": list(report.errors),
        "rules_run": report.rules_run,
    }


def _print_verdict(file_path: str, verdict: str, flag_count: int) -> None:
    """Print a single file verdict line."""
    icon = {"clean": "OK", "flagged": "WARN", "malicious": "FAIL", "error": "ERR"}
    click.echo(f"[{icon.get(verdict, '??')}] {file_path} — {verdict} ({flag_count} flags)")


@security.command("sast")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--config",
    "semgrep_config",
    default="auto",
    help="Semgrep config (auto, p/python, p/owasp-top-ten, or file path).",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json", "sarif"]),
    default="text",
    help="Output format.",
)
@click.option(
    "--output",
    "-o",
    "output_file",
    default=None,
    type=click.Path(),
    help="Write output to file.",
)
def security_sast(
    path: str,
    semgrep_config: str,
    fmt: str,
    output_file: str | None,
) -> None:
    """Run SAST scan (Semgrep) against source code."""
    from open_workspace_builder.security.sast import run_semgrep

    target = Path(path)

    try:
        result = run_semgrep(target, config=semgrep_config, sarif=(fmt == "sarif"))
    except ImportError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if fmt == "sarif":
        output = result if isinstance(result, str) else ""
    elif fmt == "json":
        output = json.dumps(
            {
                "findings": [
                    {
                        "rule_id": f.rule_id,
                        "severity": f.severity,
                        "message": f.message,
                        "file": f.file,
                        "line": f.line,
                        "code": f.code,
                    }
                    for f in result.findings
                ],
                "errors": list(result.errors),
                "rules_run": result.rules_run,
            },
            indent=2,
        )
    else:
        output = _format_sast_text(result)

    if output_file:
        Path(output_file).write_text(output + "\n", encoding="utf-8")
        click.echo(f"Report written to {output_file}")
    else:
        click.echo(output)

    # Exit 2 if any ERROR-severity findings
    if isinstance(result, str):
        return
    if any(f.severity == "ERROR" for f in result.findings):
        sys.exit(2)


def _format_sast_text(report) -> str:  # noqa: ANN001
    """Format a SastReport as human-readable text."""
    from open_workspace_builder.security.sast import SastReport

    if not isinstance(report, SastReport):
        return str(report)

    lines = [
        "=== SAST Scan (Semgrep) ===",
        f"Rules run: {report.rules_run}",
        "",
    ]

    counts = {"ERROR": 0, "WARNING": 0, "INFO": 0}
    for f in report.findings:
        severity_tag = f.severity if f.severity in counts else "INFO"
        counts[severity_tag] = counts.get(severity_tag, 0) + 1
        lines.append(f"[{f.severity}] {f.rule_id}")
        lines.append(f"  {f.file}:{f.line}")
        lines.append(f"  {f.message}")
        if f.code:
            lines.append(f"  > {f.code}")
        lines.append("")

    lines.append(
        f"Summary: {counts['ERROR']} error, {counts['WARNING']} warning, {counts['INFO']} info"
    )
    return "\n".join(lines)


# ── owb auth ─────────────────────────────────────────────────────────────────


@owb.group()
@click.pass_context
def auth(ctx: click.Context) -> None:
    """Manage API keys and secrets backends."""
    ctx.ensure_object(dict)


@auth.command("store-key")
@click.option("--backend", "backend_name", default=None, help="Backend to use (env, keyring, age).")
@click.option("--key-name", default="anthropic_api_key", help="Logical key name to store.")
@click.option(
    "--config",
    "-c",
    "config_path",
    default=None,
    type=click.Path(exists=True),
    help="Path to YAML config file.",
)
@click.pass_context
def store_key(
    ctx: click.Context,
    backend_name: str | None,
    key_name: str,
    config_path: str | None,
) -> None:
    """Store an API key in the configured secrets backend.

    Prompts for the secret value (input is masked). Use --backend to override
    the configured backend. Refuses to store empty values.
    """
    from open_workspace_builder.secrets.factory import get_backend

    config = load_config(config_path, cli_name=ctx.obj.get("cli_name"))
    secrets_cfg = config.secrets
    if backend_name is not None:
        from open_workspace_builder.config import SecretsConfig

        secrets_cfg = SecretsConfig(
            backend=backend_name,
            age_identity=config.secrets.age_identity,
            age_secrets_dir=config.secrets.age_secrets_dir,
            keyring_service=config.secrets.keyring_service,
        )

    try:
        backend = get_backend(secrets_cfg)
    except (ValueError, ImportError) as exc:
        click.echo(f"Error: {exc}")
        sys.exit(1)

    value = click.prompt(f"Enter value for '{key_name}'", hide_input=True)
    if not value or not value.strip():
        click.echo("Error: empty value. Nothing stored.")
        sys.exit(1)

    try:
        backend.set(key_name, value.strip())
    except Exception as exc:
        click.echo(f"Error storing key: {exc}")
        sys.exit(1)

    click.echo(f"Key '{key_name}' stored in {backend.backend_name()} backend.")


@auth.command("get-key")
@click.option("--key-name", default="anthropic_api_key", help="Logical key name to retrieve.")
@click.option(
    "--config",
    "-c",
    "config_path",
    default=None,
    type=click.Path(exists=True),
    help="Path to YAML config file.",
)
@click.pass_context
def get_key(ctx: click.Context, key_name: str, config_path: str | None) -> None:
    """Retrieve and display an API key.

    Warns that sensitive data will be displayed and requires confirmation.
    Uses the configured backend with environment variable fallback.
    """
    from open_workspace_builder.secrets.factory import get_backend
    from open_workspace_builder.secrets.resolver import resolve_key

    click.echo("WARNING: This displays sensitive data.")
    if not click.confirm("Display API key?", default=False):
        click.echo("Aborted.")
        return

    config = load_config(config_path, cli_name=ctx.obj.get("cli_name"))
    try:
        backend = get_backend(config.secrets)
    except (ValueError, ImportError):
        backend = None

    try:
        value = resolve_key(key_name, backend)
    except ValueError as exc:
        click.echo(f"Error: {exc}")
        sys.exit(1)

    click.echo(value)


@auth.command("status")
@click.option(
    "--config",
    "-c",
    "config_path",
    default=None,
    type=click.Path(exists=True),
    help="Path to YAML config file.",
)
@click.pass_context
def auth_status(ctx: click.Context, config_path: str | None) -> None:
    """Show secrets backend status, health, and stored keys."""
    import os

    from open_workspace_builder.secrets.factory import get_backend

    config = load_config(config_path, cli_name=ctx.obj.get("cli_name"))
    click.echo(f"Configured backend: {config.secrets.backend}")

    try:
        backend = get_backend(config.secrets)
    except (ValueError, ImportError) as exc:
        click.echo(f"Backend status: UNAVAILABLE ({exc})")
        return

    # Backend-specific health check
    backend_type = config.secrets.backend
    if backend_type == "keyring":
        from open_workspace_builder.secrets.keyring_backend import KeyringBackend

        if KeyringBackend.is_available():
            click.echo("Backend status: available")
        else:
            click.echo("Backend status: locked (fail backend active)")
    elif backend_type == "age":
        from pathlib import Path as _Path

        identity = _Path(config.secrets.age_identity).expanduser()
        if identity.is_file():
            click.echo("Backend status: available (identity file found)")
        else:
            click.echo("Backend status: available (identity will be created on first store)")
    else:
        click.echo("Backend status: available")

    # List stored keys
    keys = backend.list_keys()
    if keys:
        click.echo(f"Stored keys: {', '.join(keys)}")
    else:
        click.echo("Stored keys: (none)")

    # For env backend, also show which OWB env vars are set (names only)
    if backend_type == "env":
        _ENV_NAMES = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OWB_API_KEY", "LITELLM_API_KEY")
        present = [k for k in _ENV_NAMES if k in os.environ]
        if present:
            click.echo(f"Environment variables set: {', '.join(present)}")


@auth.command("backends")
def auth_backends() -> None:
    """List all available secrets backends and their status."""
    click.echo("Available backends:\n")

    # env — always available
    click.echo("  env       : available (reads from environment variables)")

    # keyring
    try:
        from open_workspace_builder.secrets.keyring_backend import KeyringBackend

        if KeyringBackend.is_available():
            click.echo("  keyring   : available")
        else:
            click.echo("  keyring   : installed but using fail backend")
    except ImportError:
        click.echo("  keyring   : not installed (pip install 'open-workspace-builder[keyring]')")

    # age
    try:
        from open_workspace_builder.secrets.age_backend import AgeBackend

        if AgeBackend.is_available():
            click.echo("  age       : available")
        else:
            click.echo("  age       : not available (install pyrage or age CLI)")
    except ImportError:
        click.echo("  age       : not installed (pip install 'open-workspace-builder[age]')")

    # bitwarden
    try:
        from open_workspace_builder.secrets.bitwarden_backend import BitwardenBackend

        if BitwardenBackend.is_available():
            click.echo("  bitwarden : available")
        else:
            click.echo("  bitwarden : not available (install bw CLI: https://bitwarden.com/help/cli/)")
    except ImportError:
        click.echo("  bitwarden : not available (install bw CLI: https://bitwarden.com/help/cli/)")

    # onepassword
    try:
        from open_workspace_builder.secrets.onepassword_backend import OnePasswordBackend

        if OnePasswordBackend.is_available():
            click.echo("  onepassword: available")
        else:
            click.echo("  onepassword: not available (install op CLI: https://developer.1password.com/docs/cli/)")
    except ImportError:
        click.echo("  onepassword: not available (install op CLI: https://developer.1password.com/docs/cli/)")


@auth.command("google-store")
@click.option(
    "--config",
    "-c",
    "config_path",
    default=None,
    help="Path to YAML config file.",
)
@click.pass_context
def auth_google_store(ctx: click.Context, config_path: str | None) -> None:
    """Store Google OAuth client credentials (encrypted with age).

    Prompts for client_id and client_secret (input is masked).
    Credentials are encrypted with age and stored in the config directory.
    """
    cli_name = ctx.obj.get("cli_name", "owb")
    config = load_config(config_path, cli_name=cli_name)
    config_dir = config.paths.config_dir

    client_id = click.prompt("Google OAuth client_id", hide_input=True)
    client_secret = click.prompt("Google OAuth client_secret", hide_input=True)

    if not client_id or not client_secret:
        click.echo("Error: client_id and client_secret cannot be empty.")
        sys.exit(1)

    try:
        from open_workspace_builder.auth.google import store_google_credentials

        secrets_file = store_google_credentials(
            client_id=client_id,
            client_secret=client_secret,
            config_dir=config_dir,
            age_key_path=config.secrets.age_identity,
        )
        click.echo(f"Google OAuth credentials stored at {secrets_file}")
    except (ImportError, FileNotFoundError) as exc:
        click.echo(f"Error: {exc}")
        sys.exit(1)


@auth.command("google")
@click.option(
    "--config",
    "-c",
    "config_path",
    default=None,
    help="Path to YAML config file.",
)
@click.pass_context
def auth_google(ctx: click.Context, config_path: str | None) -> None:
    """Run Google OAuth flow for Sheets API access.

    Opens a browser for user consent. The resulting token is saved for
    use by 'owb metrics export --format gsheets'.
    """
    cli_name = ctx.obj.get("cli_name", "owb")
    config = load_config(config_path, cli_name=cli_name)

    try:
        from open_workspace_builder.auth.google import run_oauth_flow

        token_path = run_oauth_flow(
            config_dir=config.paths.config_dir,
            age_key_path=config.secrets.age_identity,
        )
        click.echo(f"Google Sheets OAuth token saved at {token_path}")
    except (ImportError, FileNotFoundError, ValueError) as exc:
        click.echo(f"Error: {exc}")
        sys.exit(1)


# ── owb audit ────────────────────────────────────────────────────────────


@owb.group()
def audit() -> None:
    """Dependency supply-chain scanning (pip-audit + GuardDog)."""


@audit.command("deps")
@click.option("--fix", is_flag=True, default=False, help="Include fix-version suggestions.")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (default: text).",
)
@click.option(
    "--output",
    "-o",
    "output_file",
    default=None,
    type=click.Path(),
    help="Write report to file.",
)
@click.option("--deep", is_flag=True, default=False, help="Also run GuardDog malware scan.")
@click.option(
    "--suppressions",
    default=None,
    type=click.Path(exists=True),
    help="Path to guarddog suppressions YAML.",
)
@click.option("--licenses", is_flag=True, default=False, help="Also run license compliance check.")
@click.option(
    "--policy",
    default=None,
    type=click.Path(exists=True),
    help="Path to allowed-licenses.md (used with --licenses).",
)
def audit_deps(
    fix: bool,
    fmt: str,
    output_file: str | None,
    deep: bool,
    suppressions: str | None,
    licenses: bool,
    policy: str | None,
) -> None:
    """Scan installed dependencies for known vulnerabilities and malicious code.

    By default runs pip-audit (Layer A) only. Use --deep to add GuardDog
    heuristic scanning (Layer B). Use --licenses to include license compliance
    checking. Exit code 0 if clean, 2 if findings.
    """
    from open_workspace_builder.security.dep_audit import run_full_audit

    suppressions_path = Path(suppressions) if suppressions else None

    try:
        report = run_full_audit(deep=deep, fix=fix, suppressions_file=suppressions_path)
    except ImportError as exc:
        click.echo(f"Error: {exc}")
        sys.exit(1)
    except RuntimeError as exc:
        click.echo(f"Error: {exc}")
        sys.exit(1)

    report_data = _format_full_report(report, include_fix=fix)
    has_findings = bool(report.vuln_report.findings or report.guarddog_report.flagged)

    if fmt == "json":
        click.echo(json.dumps(report_data, indent=2))
    else:
        _print_audit_text(report, include_fix=fix)

    if licenses:
        _run_license_check_inline(policy, fmt)

    if output_file:
        Path(output_file).write_text(
            json.dumps(report_data, indent=2) + "\n", encoding="utf-8"
        )
        click.echo(f"Report written to {output_file}")

    sys.exit(2 if has_findings else 0)


def _run_license_check_inline(policy_flag: str | None, fmt: str) -> None:
    """Run license check as part of audit deps --licenses."""
    from open_workspace_builder.security.license_audit import (
        audit_licenses,
        format_license_report,
        print_license_report,
    )

    policy_path = Path(policy_flag) if policy_flag else _find_policy_file()
    try:
        report = audit_licenses(policy_path)
    except (ValueError, RuntimeError) as exc:
        click.echo(f"License check error: {exc}")
        return

    if fmt == "json":
        click.echo(json.dumps(format_license_report(report), indent=2))
    else:
        print_license_report(report)


@audit.command("package")
@click.argument("name")
@click.option("--version", "version", default=None, help="Version to scan.")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (default: text).",
)
@click.option(
    "--output",
    "-o",
    "output_file",
    default=None,
    type=click.Path(),
    help="Write report to file.",
)
def audit_package(
    name: str,
    version: str | None,
    fmt: str,
    output_file: str | None,
) -> None:
    """Scan a single package for vulnerabilities and malicious code.

    Runs both pip-audit (Layer A) and GuardDog (Layer B) against NAME.
    Use before adding a new dependency or bumping a version.
    """
    from open_workspace_builder.security.dep_audit import audit_single_package

    try:
        report = audit_single_package(name, version=version)
    except (ImportError, RuntimeError) as exc:
        click.echo(f"Error: {exc}")
        sys.exit(1)

    report_data = _format_full_report(report, include_fix=False)
    has_findings = bool(report.vuln_report.findings or report.guarddog_report.flagged)

    if fmt == "json":
        click.echo(json.dumps(report_data, indent=2))
    else:
        _print_audit_text(report, include_fix=False)

    if output_file:
        Path(output_file).write_text(
            json.dumps(report_data, indent=2) + "\n", encoding="utf-8"
        )
        click.echo(f"Report written to {output_file}")

    sys.exit(2 if has_findings else 0)


@audit.command("check-suppressions")
@click.option(
    "--registry",
    default=None,
    type=click.Path(exists=True),
    help="Path to suppressions YAML (default: bundled registry).",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (default: text).",
)
def check_suppressions(registry: str | None, fmt: str) -> None:
    """Check if suppressed CVEs have upstream fixes available.

    Queries the OSV API for each entry in the suppression registry.
    Exit code 0 = no fixes available (all suppressions still valid).
    Exit code 1 = at least one fix available (action needed).
    """
    from open_workspace_builder.security.suppression_monitor import check_all_suppressions

    registry_path = Path(registry) if registry else None

    try:
        statuses = check_all_suppressions(registry_path)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}")
        sys.exit(1)

    fixes_available = sum(1 for s in statuses if s.fix_available)

    if fmt == "json":
        data = [
            {
                "cve": s.suppression.cve,
                "package": s.suppression.package,
                "pinned_version": s.suppression.pinned_version,
                "fix_available": s.fix_available,
                "fixed_version": s.fixed_version,
                "current_version": s.current_version,
                "days_suppressed": s.days_suppressed,
                "error": s.error,
            }
            for s in statuses
        ]
        click.echo(json.dumps(data, indent=2))
    else:
        click.echo("CVE Suppression Status Report")
        click.echo("=" * 30)
        for s in statuses:
            pinned = f"pinned {s.suppression.pinned_version}" if s.suppression.pinned_version else "unpinned"
            if s.fix_available:
                status_str = f"FIX AVAILABLE: {s.fixed_version}"
            elif s.error:
                status_str = f"ERROR: {s.error}"
            else:
                status_str = "NO FIX"
            click.echo(
                f"{s.suppression.cve} | {s.suppression.package} | {pinned} "
                f"| {status_str} | {s.days_suppressed} day(s) suppressed"
            )
            if s.fix_available:
                click.echo(
                    f"  → Action: upgrade {s.suppression.package} to >={s.fixed_version}, "
                    f"remove {s.suppression.ci_flag or s.suppression.cve} from CI"
                )
        click.echo("-" * 30)
        click.echo(
            f"Summary: {len(statuses)} suppression(s), {fixes_available} fix(es) available"
        )

    sys.exit(1 if fixes_available else 0)


@audit.command("licenses")
@click.option(
    "--policy",
    default=None,
    type=click.Path(exists=True),
    help="Path to allowed-licenses.md policy file.",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (default: text).",
)
@click.option(
    "--output",
    "-o",
    "output_file",
    default=None,
    type=click.Path(),
    help="Write report to file.",
)
def audit_licenses_cmd(
    policy: str | None,
    fmt: str,
    output_file: str | None,
) -> None:
    """Check dependency licenses against the allowed-licenses policy.

    Parses the policy file to build allow/conditional/deny lists, then runs
    pip-licenses and classifies each dependency. Exit code: 0 = all pass,
    1 = any fail or unknown, 2 = only conditional findings.
    """
    from open_workspace_builder.security.license_audit import (
        audit_licenses,
        format_license_report,
        print_license_report,
    )

    policy_path = Path(policy) if policy else _find_policy_file()

    try:
        report = audit_licenses(policy_path)
    except (ValueError, RuntimeError) as exc:
        click.echo(f"Error: {exc}")
        sys.exit(1)

    if fmt == "json":
        report_data = format_license_report(report)
        click.echo(json.dumps(report_data, indent=2))
    else:
        print_license_report(report)

    if output_file:
        report_data = format_license_report(report)
        Path(output_file).write_text(
            json.dumps(report_data, indent=2) + "\n", encoding="utf-8"
        )
        click.echo(f"Report written to {output_file}")

    has_fail = any(f.status in ("fail", "unknown") for f in report.findings)
    has_conditional = any(f.status == "conditional" for f in report.findings)
    if has_fail:
        sys.exit(1)
    elif has_conditional:
        sys.exit(2)
    sys.exit(0)


def _find_policy_file() -> Path:
    """Locate the allowed-licenses policy file relative to content root."""
    # Try common locations
    candidates = [
        Path("content/policies/allowed-licenses.md"),
        Path("Obsidian/code/allowed-licenses.md"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise ValueError(
        "Could not find allowed-licenses.md policy file. "
        "Use --policy to specify the path."
    )


def _format_full_report(report: object, *, include_fix: bool) -> dict:
    """Serialize a FullAuditReport to a JSON-compatible dict."""
    vuln = report.vuln_report  # type: ignore[union-attr]
    gd = report.guarddog_report  # type: ignore[union-attr]
    data: dict = {
        "vulnerabilities": [
            {
                "package": f.package,
                "installed_version": f.installed_version,
                "vuln_id": f.vuln_id,
                "fix_version": f.fix_version,
                "description": f.description,
            }
            for f in vuln.findings
        ],
        "skipped": list(vuln.skipped),
        "guarddog_flagged": [
            {
                "package": f.package,
                "rule_name": f.rule_name,
                "severity": f.severity,
                "file_path": f.file_path,
                "evidence": f.evidence,
            }
            for f in gd.flagged
        ],
        "guarddog_clean": list(gd.clean),
    }
    if include_fix:
        data["fix_suggestions"] = list(vuln.fix_suggestions)
    return data


def _print_audit_text(report: object, *, include_fix: bool) -> None:
    """Print a FullAuditReport as human-readable text."""
    vuln = report.vuln_report  # type: ignore[union-attr]
    gd = report.guarddog_report  # type: ignore[union-attr]

    if vuln.findings:
        click.echo(f"\n[VULN] {len(vuln.findings)} known vulnerabilities found:")
        for f in vuln.findings:
            fix_str = f" (fix: {f.fix_version})" if f.fix_version else ""
            click.echo(f"  {f.package}=={f.installed_version}  {f.vuln_id}{fix_str}")
            click.echo(f"    {f.description}")
    else:
        click.echo("\n[OK] No known vulnerabilities found.")

    if vuln.skipped:
        click.echo(f"\n[SKIP] {len(vuln.skipped)} packages skipped: {', '.join(vuln.skipped)}")

    if include_fix and vuln.fix_suggestions:
        click.echo("\n[FIX] Suggested version pins:")
        for s in vuln.fix_suggestions:
            click.echo(f"  {s}")

    if gd.flagged:
        click.echo(f"\n[MALWARE] {len(gd.flagged)} guarddog findings:")
        for f in gd.flagged:
            click.echo(f"  [{f.severity}] {f.package} — {f.rule_name}")
            click.echo(f"    file: {f.file_path}")
            click.echo(f"    evidence: {f.evidence[:200]}")
    elif gd.clean:
        click.echo(f"\n[OK] GuardDog: {len(gd.clean)} packages clean.")

    if not vuln.findings and not gd.flagged:
        click.echo("\nAll checks passed.")


# ── owb context ──────────────────────────────────────────────────────────


@owb.group()
@click.pass_context
def context(ctx: click.Context) -> None:
    """Manage workspace context files (about-me, brand-voice, working-style)."""
    ctx.ensure_object(dict)


@context.command("migrate")
@click.argument("target", type=click.Path(exists=True))
@click.option(
    "--config",
    "-c",
    "config_path",
    default=None,
    type=click.Path(exists=True),
    help="Path to YAML config file.",
)
@click.option(
    "--accept-all",
    is_flag=True,
    default=False,
    help="Accept all reformatting without prompting.",
)
@click.pass_context
def context_migrate(
    ctx: click.Context,
    target: str,
    config_path: str | None,
    accept_all: bool,
) -> None:
    """Reformat existing context files to match current templates.

    Compares each context file against the template, identifies missing sections,
    and offers to append them interactively.
    """
    from open_workspace_builder.engine.context import ContextMigrator

    config = load_config(config_path, cli_name=ctx.obj.get("cli_name"))
    content_root = _find_content_root()
    migrator = ContextMigrator(content_root, config.context_templates, config.vault)
    migrator.migrate(Path(target), accept_all=accept_all)


@context.command("status")
@click.argument("target", type=click.Path(exists=True))
@click.option(
    "--config",
    "-c",
    "config_path",
    default=None,
    type=click.Path(exists=True),
    help="Path to YAML config file.",
)
@click.pass_context
def context_status(
    ctx: click.Context,
    target: str,
    config_path: str | None,
) -> None:
    """Check context file status: filled, stub, or missing."""
    from open_workspace_builder.engine.context import has_todo_markers

    config = load_config(config_path, cli_name=ctx.obj.get("cli_name"))
    parent = config.vault.parent_dir
    context_dir = Path(target) / parent if parent else Path(target)

    files = [f.replace(".template", "") for f in config.context_templates.files]
    for f in files:
        path = context_dir / f
        if not path.exists():
            click.echo(f"  [missing]  {f}")
        elif has_todo_markers(path):
            click.echo(f"  [stub]     {f} — needs filling")
        else:
            click.echo(f"  [filled]   {f}")


@owb.command()
@click.argument("path", type=click.Path(exists=True))
def validate(path: str) -> None:
    """Validate a skill directory against the Agent Skills spec."""
    from open_workspace_builder.evaluator.spec_validator import validate_skill

    result = validate_skill(path)

    if result.valid:
        click.echo(f"[PASS] {path}")
    else:
        click.echo(f"[FAIL] {path}")

    if result.errors:
        click.echo("\nErrors:")
        for error in result.errors:
            click.echo(f"  - {error}")

    if result.warnings:
        click.echo("\nWarnings:")
        for warning in result.warnings:
            click.echo(f"  - {warning}")

    if not result.errors and not result.warnings:
        click.echo("  No issues found.")

    sys.exit(0 if result.valid else 1)


@owb.group()
@click.pass_context
def metrics(ctx: click.Context) -> None:
    """Token consumption tracking and cost analysis."""
    ctx.ensure_object(dict)


@metrics.command("tokens")
@click.option("--since", default=None, help="Start date filter (YYYYMMDD)")
@click.option("--until", default=None, help="End date filter (YYYYMMDD)")
@click.option("--project", "project_filter", default=None, help="Filter by project name")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
@click.option(
    "--claude-dir",
    default=None,
    help="Path to Claude Code data directory (default: ~/.claude)",
)
def metrics_tokens(
    since: str | None,
    until: str | None,
    project_filter: str | None,
    output_format: str,
    claude_dir: str | None,
) -> None:
    """Report token consumption and API-equivalent costs.

    Parses Claude Code session files and calculates per-model, per-project,
    and per-day cost breakdowns.
    """
    from open_workspace_builder.tokens.calculator import build_report
    from open_workspace_builder.tokens.parser import (
        discover_session_files,
        parse_session_file,
        project_name_from_dir,
    )
    from open_workspace_builder.tokens.pricing import load_pricing

    projects_dir = Path(claude_dir or Path.home() / ".claude") / "projects"
    if not projects_dir.is_dir():
        click.echo(f"Error: Claude Code projects directory not found: {projects_dir}")
        sys.exit(1)

    pricing = load_pricing()
    session_files = discover_session_files(projects_dir)

    if not session_files:
        click.echo("No session files found.")
        sys.exit(0)

    # Parse all sessions and group by project.
    session_data: list[tuple[str, str, list]] = []
    for session_file in session_files:
        project_dir_name = session_file.parent.name
        project_name = project_name_from_dir(project_dir_name)

        if project_filter and project_filter.lower() not in project_name.lower():
            continue

        usages = parse_session_file(session_file)
        if usages:
            session_id = session_file.stem
            session_data.append((project_name, session_id, usages))

    report = build_report(session_data, pricing, since=since, until=until)

    if output_format == "json":
        from open_workspace_builder.tokens.reporter import format_report_json

        click.echo(json.dumps(format_report_json(report), indent=2))
    else:
        from open_workspace_builder.tokens.reporter import format_report

        click.echo(format_report(report))


@metrics.command("export")
@click.option(
    "--format",
    "export_format",
    type=click.Choice(["gsheets", "xlsx"]),
    required=True,
    help="Export format",
)
@click.option("--sheet-id", default=None, help="Google Sheet ID (required for gsheets)")
@click.option("--output", "output_path", default=None, help="Output file path (for xlsx)")
@click.option("--since", default=None, help="Start date filter (YYYYMMDD)")
@click.option("--until", default=None, help="End date filter (YYYYMMDD)")
@click.option(
    "--claude-dir",
    default=None,
    help="Path to Claude Code data directory (default: ~/.claude)",
)
def metrics_export(
    export_format: str,
    sheet_id: str | None,
    output_path: str | None,
    since: str | None,
    until: str | None,
    claude_dir: str | None,
) -> None:
    """Export token consumption data to Google Sheets or Excel.

    Google Sheets requires the [sheets] extra and configured OAuth credentials.
    Excel requires the [xlsx] extra.
    """
    if export_format == "gsheets" and not sheet_id:
        click.echo("Error: --sheet-id is required for Google Sheets export.")
        sys.exit(1)
    if export_format == "xlsx" and not output_path:
        click.echo("Error: --output is required for Excel export.")
        sys.exit(1)

    from open_workspace_builder.tokens.calculator import build_report
    from open_workspace_builder.tokens.parser import (
        discover_session_files,
        parse_session_file,
        project_name_from_dir,
    )
    from open_workspace_builder.tokens.pricing import load_pricing

    projects_dir = Path(claude_dir or Path.home() / ".claude") / "projects"
    if not projects_dir.is_dir():
        click.echo(f"Error: Claude Code projects directory not found: {projects_dir}")
        sys.exit(1)

    pricing = load_pricing()
    session_files = discover_session_files(projects_dir)
    session_data: list[tuple[str, str, list]] = []
    for session_file in session_files:
        project_name = project_name_from_dir(session_file.parent.name)
        usages = parse_session_file(session_file)
        if usages:
            session_data.append((project_name, session_file.stem, usages))

    report = build_report(session_data, pricing, since=since, until=until)

    if export_format == "gsheets":
        try:
            from open_workspace_builder.tokens.sheets_export import export_to_sheets
        except ImportError:
            click.echo(
                "Error: Google Sheets export requires additional packages.\n"
                "Install with: uv pip install open-workspace-builder[sheets]"
            )
            sys.exit(1)
        export_to_sheets(report, sheet_id)  # type: ignore[arg-type]
        click.echo(f"Exported to Google Sheet: {sheet_id}")
    elif export_format == "xlsx":
        try:
            from open_workspace_builder.tokens.xlsx_export import export_to_xlsx
        except ImportError:
            click.echo(
                "Error: Excel export requires xlsxwriter.\n"
                "Install with: uv pip install open-workspace-builder[xlsx]"
            )
            sys.exit(1)
        export_to_xlsx(report, output_path)  # type: ignore[arg-type]
        click.echo(f"Exported to: {output_path}")


def _record_sessions(
    projects_dir: Path,
    resolved_ledger: Path,
    story_id: str = "",
) -> tuple[int, list[tuple[str, str, list]]]:
    """Record all sessions to the ledger. Returns (count, session_data).

    The returned session_data can be reused for export without re-parsing.
    """
    from open_workspace_builder.tokens.calculator import build_report
    from open_workspace_builder.tokens.ledger import append_entry
    from open_workspace_builder.tokens.models import LedgerEntry
    from open_workspace_builder.tokens.parser import (
        discover_session_files,
        parse_session_file,
        project_name_from_dir,
    )
    from open_workspace_builder.tokens.pricing import load_pricing

    pricing = load_pricing()
    session_files = discover_session_files(projects_dir)
    recorded = 0
    all_session_data: list[tuple[str, str, list]] = []

    for session_file in session_files:
        project_name = project_name_from_dir(session_file.parent.name)
        usages = parse_session_file(session_file)
        if not usages:
            continue

        session_id = session_file.stem
        all_session_data.append((project_name, session_id, usages))

        session_data = [(project_name, session_id, usages)]
        report = build_report(session_data, pricing)

        entry = LedgerEntry(
            session_id=session_id,
            project=project_name,
            timestamp=usages[0].timestamp,
            total_input=report.total_input,
            total_output=report.total_output,
            total_cache_creation=report.total_cache_creation,
            total_cache_read=report.total_cache_read,
            cost=report.total_cost,
            story_id=story_id,
        )
        append_entry(resolved_ledger, entry)
        recorded += 1

    return recorded, all_session_data


@metrics.command("record")
@click.option(
    "--claude-dir",
    default=None,
    help="Path to Claude Code data directory (default: ~/.claude)",
)
@click.option(
    "--ledger",
    "ledger_path",
    default=None,
    help="Path to ledger file (default: ~/.owb/data/ledger.jsonl)",
)
@click.option("--story", "story_id", default="", help="Story ID to tag this session")
def metrics_record(
    claude_dir: str | None,
    ledger_path: str | None,
    story_id: str,
) -> None:
    """Record session costs to the local ledger.

    Parses all session files and appends a cost summary for each session.
    Skips sessions already in the ledger. Designed to be called from a
    Claude Code session-end hook.
    """
    projects_dir = Path(claude_dir or Path.home() / ".claude") / "projects"
    if not projects_dir.is_dir():
        click.echo(f"Error: Claude Code projects directory not found: {projects_dir}")
        sys.exit(1)

    resolved_ledger = Path(
        ledger_path or Path.home() / ".owb" / "data" / "ledger.jsonl"
    )

    recorded, _ = _record_sessions(projects_dir, resolved_ledger, story_id)
    click.echo(f"Recorded {recorded} session(s) to {resolved_ledger}")


@metrics.command("forecast")
@click.option(
    "--ledger",
    "ledger_path",
    default=None,
    help="Path to ledger file (default: ~/.owb/data/ledger.jsonl)",
)
@click.option(
    "--current-date",
    default=None,
    help="Current date as YYYY-MM-DD (default: today)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
def metrics_forecast(
    ledger_path: str | None,
    current_date: str | None,
    output_format: str,
) -> None:
    """Show monthly cost forecast from ledger data.

    Extrapolates month-to-date cost to a projected monthly total.
    """
    from datetime import date

    from open_workspace_builder.tokens.forecast import forecast_monthly
    from open_workspace_builder.tokens.ledger import read_entries

    resolved_ledger = Path(
        ledger_path or Path.home() / ".owb" / "data" / "ledger.jsonl"
    )
    resolved_date = current_date or date.today().isoformat()

    entries = read_entries(resolved_ledger)
    if not entries:
        click.echo("No ledger data found.")
        sys.exit(0)

    result = forecast_monthly(entries, current_date=resolved_date)

    if output_format == "json":
        click.echo(
            json.dumps(
                {
                    "month_to_date": round(result.month_to_date, 2),
                    "projected_total": round(result.projected_total, 2),
                    "daily_average": round(result.daily_average, 2),
                    "days_elapsed": result.days_elapsed,
                    "days_in_month": result.days_in_month,
                },
                indent=2,
            )
        )
    else:
        click.echo(f"Month-to-date:   ${result.month_to_date:.2f}")
        click.echo(f"Daily average:   ${result.daily_average:.2f}")
        click.echo(
            f"Projected total: ${result.projected_total:.2f} "
            f"({result.days_elapsed}/{result.days_in_month} days)"
        )


@metrics.command("budget-check")
@click.option(
    "--ledger",
    "ledger_path",
    default=None,
    help="Path to ledger file (default: ~/.owb/data/ledger.jsonl)",
)
@click.option(
    "--threshold",
    type=float,
    required=True,
    help="Monthly budget threshold in dollars",
)
@click.option(
    "--current-date",
    default=None,
    help="Current date as YYYY-MM-DD (default: today)",
)
def metrics_budget_check(
    ledger_path: str | None,
    threshold: float,
    current_date: str | None,
) -> None:
    """Check month-to-date cost against budget threshold.

    Exits with code 2 if over budget (useful for hook scripts).
    Exit 0 means under budget.
    """
    from datetime import date

    from open_workspace_builder.tokens.budget import check_budget
    from open_workspace_builder.tokens.ledger import read_entries

    resolved_ledger = Path(
        ledger_path or Path.home() / ".owb" / "data" / "ledger.jsonl"
    )
    resolved_date = current_date or date.today().isoformat()

    entries = read_entries(resolved_ledger)
    result = check_budget(entries, threshold=threshold, current_date=resolved_date)

    if result.exceeded:
        click.echo(
            f"OVER BUDGET: ${result.month_to_date:.2f} / "
            f"${result.threshold:.2f} ({result.pct_used:.1f}%)"
        )
        sys.exit(2)
    else:
        click.echo(
            f"Under budget: ${result.month_to_date:.2f} / "
            f"${result.threshold:.2f} ({result.pct_used:.1f}%) — "
            f"${result.remaining:.2f} remaining"
        )


@metrics.command("sync")
@click.option(
    "--claude-dir",
    default=None,
    help="Path to Claude Code data directory (default: ~/.claude)",
)
@click.option(
    "--ledger",
    "ledger_path",
    default=None,
    help="Path to ledger file (default: ~/.owb/data/ledger.jsonl)",
)
@click.option("--sheet-id", default=None, help="Google Sheet ID for export (optional)")
@click.option("--story", "story_id", default="", help="Story ID to tag sessions")
def metrics_sync(
    claude_dir: str | None,
    ledger_path: str | None,
    sheet_id: str | None,
    story_id: str,
) -> None:
    """Record session costs and optionally export to Google Sheets.

    Combines record + export into a single command for sprint-close hooks.
    If --sheet-id is provided, exports to Google Sheets after recording.
    """
    projects_dir = Path(claude_dir or Path.home() / ".claude") / "projects"
    if not projects_dir.is_dir():
        click.echo(f"Error: Claude Code projects directory not found: {projects_dir}")
        sys.exit(1)

    resolved_ledger = Path(
        ledger_path or Path.home() / ".owb" / "data" / "ledger.jsonl"
    )

    recorded, all_session_data = _record_sessions(
        projects_dir, resolved_ledger, story_id
    )
    click.echo(f"Recorded {recorded} session(s) to {resolved_ledger}")

    if sheet_id:
        try:
            from open_workspace_builder.tokens.sheets_export import export_to_sheets
        except ImportError:
            click.echo(
                "Warning: Google Sheets export requires additional packages.\n"
                "Install with: uv pip install open-workspace-builder[sheets]"
            )
            return

        from open_workspace_builder.tokens.calculator import build_report
        from open_workspace_builder.tokens.pricing import load_pricing

        pricing = load_pricing()
        report = build_report(all_session_data, pricing)
        export_to_sheets(report, sheet_id)
        click.echo(f"Exported to Google Sheet: {sheet_id}")


@metrics.command("by-story")
@click.option(
    "--ledger",
    "ledger_path",
    default=None,
    help="Path to ledger file (default: ~/.owb/data/ledger.jsonl)",
)
@click.option("--since", default=None, help="Start date filter (YYYYMMDD)")
@click.option("--until", default=None, help="End date filter (YYYYMMDD)")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
def metrics_by_story(
    ledger_path: str | None,
    since: str | None,
    until: str | None,
    output_format: str,
) -> None:
    """Show cost breakdown by story ID from ledger data.

    Groups ledger entries by their story_id tag and shows total cost per story.
    """
    from collections import defaultdict

    from open_workspace_builder.tokens.ledger import read_entries

    resolved_ledger = Path(
        ledger_path or Path.home() / ".owb" / "data" / "ledger.jsonl"
    )

    entries = read_entries(resolved_ledger, since=since, until=until)
    if not entries:
        click.echo("No ledger data found.")
        sys.exit(0)

    story_costs: dict[str, dict] = defaultdict(
        lambda: {"total_cost": 0.0, "sessions": 0}
    )
    for entry in entries:
        tag = entry.story_id or "(untagged)"
        story_costs[tag]["total_cost"] += entry.cost.total
        story_costs[tag]["sessions"] += 1

    if output_format == "json":
        # Convert defaultdict to regular dict for JSON serialization
        out = {
            k: {"total_cost": round(v["total_cost"], 2), "sessions": v["sessions"]}
            for k, v in sorted(story_costs.items())
        }
        click.echo(json.dumps(out, indent=2))
    else:
        click.echo("Cost by Story")
        click.echo("=" * 50)
        for tag in sorted(story_costs):
            data = story_costs[tag]
            click.echo(
                f"  {tag:<20s}  ${data['total_cost']:>8.2f}  "
                f"({data['sessions']} session{'s' if data['sessions'] != 1 else ''})"
            )


@owb.group()
@click.pass_context
def stage(ctx: click.Context) -> None:
    """Bootstrap stage assessment and promotion."""
    ctx.ensure_object(dict)


@stage.command("status")
@click.option("--vault", default=None, type=click.Path(exists=True), help="Path to vault directory.")
@click.option(
    "--config",
    "-c",
    "config_path",
    default=None,
    type=click.Path(exists=True),
    help="Path to YAML config file.",
)
def stage_status(vault: str | None, config_path: str | None) -> None:
    """Show current bootstrap stage and exit criteria for the next stage."""
    from open_workspace_builder.stage import StageEvaluator

    config = load_config(config_path)
    vault_path = Path(vault) if vault else Path(config.target)
    if not vault_path.is_dir():
        click.echo(f"Error: Vault path does not exist: {vault_path}")
        sys.exit(1)

    evaluator = StageEvaluator(vault_path=vault_path, config=config)
    assessment = evaluator.assess_current()

    click.echo(f"Current: Stage {assessment.current_stage}")
    if assessment.current_stage == assessment.target_stage:
        click.echo("Maximum stage reached. No further promotion available.")
        return

    click.echo(f"Next:    Stage {assessment.target_stage}")
    click.echo()

    if not assessment.criteria:
        return

    click.echo("Exit criteria:")
    for criterion in assessment.criteria:
        status = "PASS" if criterion.passed else "FAIL"
        click.echo(f"  [{status}] {criterion.name}")
        if not criterion.passed:
            click.echo(f"         {criterion.detail}")

    passed = sum(1 for c in assessment.criteria if c.passed)
    total = len(assessment.criteria)
    click.echo()
    click.echo(f"{passed}/{total} criteria met.")
    if assessment.can_promote:
        click.echo("Ready to promote. Run: owb stage promote")


@stage.command("promote")
@click.option("--vault", default=None, type=click.Path(exists=True), help="Path to vault directory.")
@click.option(
    "--config",
    "-c",
    "config_path",
    default=None,
    type=click.Path(exists=True),
    help="Path to YAML config file.",
)
def stage_promote(vault: str | None, config_path: str | None) -> None:
    """Promote to the next bootstrap stage after verifying exit criteria."""
    import yaml

    from open_workspace_builder.stage import StageEvaluator

    resolved_config_path = Path(config_path) if config_path else None
    config = load_config(config_path)
    vault_path = Path(vault) if vault else Path(config.target)
    if not vault_path.is_dir():
        click.echo(f"Error: Vault path does not exist: {vault_path}")
        sys.exit(1)

    evaluator = StageEvaluator(vault_path=vault_path, config=config)
    assessment = evaluator.assess_current()

    if assessment.current_stage == assessment.target_stage:
        click.echo(f"Already at maximum Stage {assessment.current_stage}. Nothing to promote.")
        sys.exit(1)

    if not assessment.can_promote:
        click.echo(f"Cannot promote from Stage {assessment.current_stage} to Stage {assessment.target_stage}.")
        click.echo()
        click.echo("Criteria not met:")
        for criterion in assessment.criteria:
            if not criterion.passed:
                click.echo(f"  [FAIL] {criterion.name}")
                click.echo(f"         {criterion.detail}")
        sys.exit(1)

    # Write updated stage to config file
    new_stage = assessment.target_stage
    if resolved_config_path and resolved_config_path.exists():
        raw = yaml.safe_load(resolved_config_path.read_text(encoding="utf-8")) or {}
        raw.setdefault("stage", {})["current_stage"] = new_stage
        resolved_config_path.write_text(
            yaml.dump(raw, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
    elif resolved_config_path is None:
        click.echo(
            "Warning: no config file specified — stage not persisted. "
            "Pass --config to save."
        )

    click.echo(f"Promoted to Stage {new_stage}")


@owb.group()
def mcp() -> None:
    """MCP (Model Context Protocol) server commands."""


@mcp.command()
def serve() -> None:
    """Start the OWB MCP server for AI desktop clients.

    Exposes security scan, dependency audit, and license audit as MCP tools.
    Requires the [mcp] extra: uv pip install open-workspace-builder[mcp]
    """
    try:
        from open_workspace_builder.mcp_server import run_server
    except ImportError:
        click.echo(
            "Error: MCP server requires the 'mcp' package.\n"
            "Install it with: uv pip install open-workspace-builder[mcp]"
        )
        sys.exit(1)

    click.echo("Starting OWB MCP server...")
    run_server()
