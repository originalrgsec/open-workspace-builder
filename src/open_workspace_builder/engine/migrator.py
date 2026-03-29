"""S015 — Workspace migrator: apply diff changes interactively or in batch."""

from __future__ import annotations

import difflib
import json
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from open_workspace_builder.config import Config, load_config
from open_workspace_builder.engine.builder import WorkspaceBuilder
from open_workspace_builder.engine.differ import FileGap, diff_workspace
from open_workspace_builder.security.scanner import Scanner, ScanVerdict
from open_workspace_builder.security.trust import is_trusted, load_trust_manifest


@dataclass(frozen=True)
class MigrateAction:
    """Record of a single migration action taken."""

    path: str
    action: Literal["created", "updated", "skipped", "rejected", "blocked"]
    reason: str


@dataclass(frozen=True)
class MigrateReport:
    """Full migration report."""

    actions: tuple[MigrateAction, ...] = ()
    summary: dict[str, int] = field(default_factory=dict)
    security_flags: tuple[ScanVerdict, ...] = ()


def _ecc_relative_path(gap_path: str) -> str | None:
    """Extract the ECC-relative path from a workspace gap path.

    ECC files live under .claude/ in the workspace (e.g., .claude/agents/planner.md).
    The vendor/ecc directory has the same structure without the .claude/ prefix
    (e.g., agents/planner.md). Returns the ECC-relative path if the gap path
    is under .claude/, or None otherwise.
    """
    ecc_prefix = ".claude/"
    if gap_path.startswith(ecc_prefix):
        return gap_path[len(ecc_prefix):]
    return None


def _scan_file(scanner: Scanner, file_path: Path) -> ScanVerdict:
    """Run the security scanner on a single file."""
    return scanner.scan_file(file_path)


def _show_preview(ref_path: Path, actual_path: Path | None, category: str) -> str:
    """Generate a preview string for the user."""
    lines: list[str] = []
    if category == "missing":
        content = ref_path.read_text(encoding="utf-8", errors="replace")
        preview_lines = content.splitlines()[:10]
        lines.append("  Preview (first 10 lines):")
        for line in preview_lines:
            lines.append(f"    {line}")
        if len(content.splitlines()) > 10:
            lines.append(f"    ... ({len(content.splitlines()) - 10} more lines)")
    elif category in ("outdated", "modified") and actual_path is not None:
        ref_content = ref_path.read_text(encoding="utf-8", errors="replace")
        actual_content = actual_path.read_text(encoding="utf-8", errors="replace")
        diff = difflib.unified_diff(
            actual_content.splitlines(),
            ref_content.splitlines(),
            fromfile="current",
            tofile="reference",
            lineterm="",
        )
        diff_lines = list(diff)[:20]
        lines.append("  Diff preview (first 20 lines):")
        for line in diff_lines:
            lines.append(f"    {line}")
    return "\n".join(lines)


def _show_full_diff(ref_path: Path, actual_path: Path | None) -> str:
    """Generate a full unified diff string."""
    if actual_path is None or not actual_path.exists():
        return ref_path.read_text(encoding="utf-8", errors="replace")
    ref_content = ref_path.read_text(encoding="utf-8", errors="replace")
    actual_content = actual_path.read_text(encoding="utf-8", errors="replace")
    diff = difflib.unified_diff(
        actual_content.splitlines(),
        ref_content.splitlines(),
        fromfile="current",
        tofile="reference",
        lineterm="",
    )
    return "\n".join(diff)


def _write_migration_log(vault_path: Path, action: MigrateAction) -> None:
    """Append an action to the migration log in .owb/migration-log.jsonl."""
    log_dir = vault_path / ".owb"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "migration-log.jsonl"
    entry = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "action": action.action,
        "path": action.path,
        "reason": action.reason,
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _apply_file(ref_file: Path, target_file: Path) -> None:
    """Copy reference file to target, creating parent directories as needed."""
    target_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ref_file, target_file)


def migrate_workspace(
    vault_path: Path,
    *,
    config: Config | None = None,
    content_root: Path | None = None,
    accept_all: bool = False,
    dry_run: bool = False,
    prompt_fn: object | None = None,
) -> MigrateReport:
    """Run diff and apply changes to the workspace.

    Args:
        vault_path: Path to the existing workspace.
        config: Optional config override.
        content_root: Optional content root override.
        accept_all: If True, accept all clean files without prompting.
        dry_run: If True, report what would happen without writing.
        prompt_fn: Callable(str) -> str for interactive prompts. Defaults to input().
    """
    vault_path = vault_path.resolve()
    if not vault_path.is_dir():
        msg = f"Vault path does not exist or is not a directory: {vault_path}"
        raise FileNotFoundError(msg)

    if config is None:
        config = load_config()
    if content_root is None:
        from open_workspace_builder.cli import _find_content_root

        content_root = _find_content_root()
    if prompt_fn is None:
        prompt_fn = input

    # Set up scanner (layers 1 and 2 minimum; layer 3 if API key available)
    scanner = Scanner(layers=(1, 2, 3))

    # Load trust manifest for first-party ECC content
    trust_manifest = load_trust_manifest(content_root)

    actions: list[MigrateAction] = []
    security_flags: list[ScanVerdict] = []

    # Generate reference workspace for both diff and file access
    with tempfile.TemporaryDirectory(prefix="owb-migrate-ref-") as tmp_dir:
        ref_path = Path(tmp_dir) / "reference"
        builder = WorkspaceBuilder(config, content_root, dry_run=False)
        builder.build(ref_path)

        # Get the diff report using the pre-built reference
        report = diff_workspace(vault_path, config=config, content_root=content_root)
        quit_remaining = False

        for gap in report.gaps:
            if quit_remaining:
                action = MigrateAction(
                    path=gap.path,
                    action="skipped",
                    reason="User quit remaining migrations",
                )
                actions.append(action)
                if not dry_run:
                    _write_migration_log(vault_path, action)
                continue

            # Skip extra files — never touch user additions
            if gap.category == "extra":
                continue

            ref_file = ref_path / gap.path
            actual_file = vault_path / gap.path

            # Check trust manifest — skip scanning for unmodified first-party ECC
            ecc_rel = _ecc_relative_path(gap.path)
            trusted = ecc_rel is not None and is_trusted(ref_file, ecc_rel, trust_manifest)

            if not trusted:
                # Security scan the reference file
                verdict = _scan_file(scanner, ref_file)
                if verdict.verdict in ("flagged", "malicious"):
                    security_flags.append(verdict)
                    action = MigrateAction(
                        path=gap.path,
                        action="blocked",
                        reason=f"Security scanner flagged: {verdict.verdict} ({len(verdict.flags)} flags)",
                    )
                    actions.append(action)
                    if not dry_run:
                        _write_migration_log(vault_path, action)
                    continue

            if accept_all:
                # Batch mode: accept all clean files, but modified needs explicit consent
                if gap.category == "modified":
                    action = MigrateAction(
                        path=gap.path,
                        action="skipped",
                        reason="File has user modifications — requires interactive approval",
                    )
                    actions.append(action)
                    if not dry_run:
                        _write_migration_log(vault_path, action)
                    continue

                action_type = "created" if gap.category == "missing" else "updated"
                action = MigrateAction(
                    path=gap.path,
                    action=action_type,
                    reason=f"Batch mode: auto-accepted ({gap.category})",
                )
                actions.append(action)
                if not dry_run:
                    _apply_file(ref_file, actual_file)
                    _write_migration_log(vault_path, action)
                continue

            # Interactive mode
            _print_gap_info(gap, ref_file, actual_file)

            while True:
                response = prompt_fn("[y]es / [n]o / [d]iff / [q]uit: ")
                response = response.strip().lower()

                if response == "d":
                    print(_show_full_diff(ref_file, actual_file if actual_file.exists() else None))
                    continue
                if response in ("y", "yes"):
                    action_type = "created" if gap.category == "missing" else "updated"
                    action = MigrateAction(
                        path=gap.path,
                        action=action_type,
                        reason=f"User accepted ({gap.category})",
                    )
                    actions.append(action)
                    if not dry_run:
                        _apply_file(ref_file, actual_file)
                        _write_migration_log(vault_path, action)
                    break
                if response in ("n", "no"):
                    action = MigrateAction(
                        path=gap.path,
                        action="rejected",
                        reason="User rejected",
                    )
                    actions.append(action)
                    if not dry_run:
                        _write_migration_log(vault_path, action)
                    break
                if response in ("q", "quit"):
                    action = MigrateAction(
                        path=gap.path,
                        action="skipped",
                        reason="User quit",
                    )
                    actions.append(action)
                    if not dry_run:
                        _write_migration_log(vault_path, action)
                    quit_remaining = True
                    break
                print("Invalid input. Please enter y, n, d, or q.")

    summary: dict[str, int] = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "rejected": 0,
        "blocked": 0,
    }
    for a in actions:
        summary[a.action] += 1

    return MigrateReport(
        actions=tuple(actions),
        summary=summary,
        security_flags=tuple(security_flags),
    )


def _print_gap_info(gap: FileGap, ref_file: Path, actual_file: Path) -> None:
    """Print information about a gap for interactive prompting."""
    icons = {"missing": "[-]", "outdated": "[~]", "modified": "[*]"}
    print(f"\n{icons.get(gap.category, '[?]')} {gap.path} ({gap.category})")
    print(f"  {gap.recommendation}")

    actual_for_preview = actual_file if actual_file.exists() else None
    preview = _show_preview(ref_file, actual_for_preview, gap.category)
    if preview:
        print(preview)


def format_migrate_report(report: MigrateReport) -> str:
    """Format a MigrateReport as a human-readable string."""
    lines: list[str] = []
    lines.append("Migration Report")
    lines.append("=" * 50)

    for action in report.actions:
        icon = {
            "created": "[+]",
            "updated": "[~]",
            "skipped": "[.]",
            "rejected": "[x]",
            "blocked": "[!]",
        }
        lines.append(f"  {icon.get(action.action, '[?]')} {action.path} — {action.reason}")

    lines.append(f"\nSummary: {report.summary}")

    if report.security_flags:
        lines.append(f"\nSecurity flags: {len(report.security_flags)} file(s) blocked")
        for verdict in report.security_flags:
            lines.append(f"  [!] {verdict.file_path} — {verdict.verdict}")

    return "\n".join(lines)
