"""S037 — Multi-source update pipeline: clone, discover, scan, audit, apply."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_workspace_builder.config import Config
    from open_workspace_builder.security.scanner import Scanner
    from open_workspace_builder.sources.audit import RepoAuditor
    from open_workspace_builder.sources.discovery import DiscoveredFile, SourceDiscovery


@dataclass(frozen=True)
class UpdateSummary:
    """Summary of an update operation for a single source."""

    source_name: str
    files_accepted: tuple[str, ...]
    files_rejected: tuple[str, ...]
    files_blocked: tuple[str, ...]
    files_warned: tuple[str, ...]
    audit_verdict: str


class SourceUpdater:
    """Multi-source update pipeline: clone, discover, scan, audit, apply."""

    def __init__(
        self,
        config: Config,
        scanner: Scanner,
        discovery: SourceDiscovery,
        auditor: RepoAuditor,
    ) -> None:
        self._config = config
        self._scanner = scanner
        self._discovery = discovery
        self._auditor = auditor

    def update(
        self,
        source_name: str,
        interactive: bool = True,
        prompt_fn: object | None = None,
        dry_run: bool = False,
        vendor_dir: Path | None = None,
    ) -> UpdateSummary:
        """Execute the full update pipeline for a named source.

        Pipeline: clone/fetch -> discover -> per-file scan -> repo audit -> apply.

        Args:
            source_name: Name of the registered source.
            interactive: If True and prompt_fn provided, prompt per file.
            prompt_fn: Callable(relative_path, verdict) -> str ("a"/"r"/"q").
            dry_run: If True, do not write files.
            vendor_dir: Override vendor directory (for testing).

        Returns:
            UpdateSummary with counts and audit verdict.
        """
        source_config = self._discovery.get_config(source_name)

        with tempfile.TemporaryDirectory() as tmp:
            repo_dir = Path(tmp) / "repo"
            _clone_or_fetch(source_config.repo_url, source_config.pin, repo_dir)

            discovered = self._discovery.discover(source_name, str(repo_dir))

            # Per-file security scan
            file_verdicts: dict[str, object] = {}
            for df in discovered:
                verdict = self._scanner.scan_file(Path(df.absolute_path))
                file_verdicts[df.relative_path] = verdict

            # Repo-level audit
            audit_result = self._auditor.audit(source_name, str(repo_dir), discovered)

            # If audit is BLOCK, halt entirely
            if audit_result.verdict.value == "block":
                return UpdateSummary(
                    source_name=source_name,
                    files_accepted=(),
                    files_rejected=(),
                    files_blocked=tuple(f.relative_path for f in discovered),
                    files_warned=(),
                    audit_verdict=audit_result.verdict.value,
                )

            # Identify warned files from audit (quarantined)
            warned_paths: set[str] = set()
            if audit_result.verdict.value == "warn":
                from open_workspace_builder.sources.audit import AuditVerdict

                for finding in audit_result.findings:
                    if finding.severity == AuditVerdict.WARN:
                        warned_paths.add(finding.file_path)

            # Filter out warned and security-flagged files
            clean_files: list[DiscoveredFile] = []
            blocked_paths: list[str] = []
            for df in discovered:
                if df.relative_path in warned_paths:
                    continue
                verdict = file_verdicts.get(df.relative_path)
                if verdict is not None and hasattr(verdict, "verdict"):
                    if verdict.verdict in ("flagged", "malicious"):
                        blocked_paths.append(df.relative_path)
                        continue
                clean_files.append(df)

            # Interactive or auto-accept
            accepted: list[str] = []
            rejected: list[str] = []
            quit_requested = False

            for df in clean_files:
                if quit_requested:
                    rejected.append(df.relative_path)
                    continue

                if not interactive:
                    action = "a"
                elif prompt_fn is not None:
                    action = prompt_fn(df.relative_path, file_verdicts.get(df.relative_path))
                else:
                    action = "a"

                if action == "q":
                    quit_requested = True
                    rejected.append(df.relative_path)
                elif action == "a":
                    accepted.append(df.relative_path)
                else:
                    rejected.append(df.relative_path)

            # Build path lookup from discovered files
            abs_by_rel: dict[str, str] = {df.relative_path: df.absolute_path for df in discovered}

            # Apply accepted files
            if not dry_run and vendor_dir is not None:
                for rel_path in accepted:
                    src = Path(abs_by_rel[rel_path])
                    dst = vendor_dir / rel_path
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)

                # Update metadata
                _write_update_metadata(
                    vendor_dir, source_name, source_config.pin, accepted, rejected, blocked_paths
                )

        return UpdateSummary(
            source_name=source_name,
            files_accepted=tuple(accepted),
            files_rejected=tuple(rejected),
            files_blocked=tuple(blocked_paths),
            files_warned=tuple(warned_paths),
            audit_verdict=audit_result.verdict.value,
        )


def _clone_or_fetch(repo_url: str, pin: str, target_dir: Path) -> None:
    """Clone a repo to target_dir. If pin is a commit/tag, checkout that ref."""
    target_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(target_dir)],
        check=True,
        capture_output=True,
    )
    if pin:
        try:
            subprocess.run(
                ["git", "-C", str(target_dir), "checkout", pin],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError:
            pass  # Pin may be HEAD or invalid; continue with cloned state


def _sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _write_update_metadata(
    vendor_dir: Path,
    source_name: str,
    pin: str,
    accepted: list[str],
    rejected: list[str],
    blocked: list[str],
) -> None:
    """Write update log and metadata."""
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source_name,
        "pin": pin,
        "files_accepted": accepted,
        "files_rejected": rejected,
        "files_blocked": blocked,
    }
    log_path = vendor_dir / ".update-log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")
