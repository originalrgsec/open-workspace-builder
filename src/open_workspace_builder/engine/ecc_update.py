"""ECC upstream update workflow: fetch, diff, scan, and apply updates."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


_TRACKED_DIRS = ("agents", "commands", "rules")


@dataclass(frozen=True)
class FileDiff:
    """Categorized file difference between upstream and vendor."""

    relative_path: str
    category: str  # "new", "changed", "removed", "unchanged"
    unified_diff: str | None = None


@dataclass(frozen=True)
class FileReview:
    """A file diff combined with its security scan verdict."""

    diff: FileDiff
    verdict: object | None = None  # ScanVerdict when scanned


@dataclass(frozen=True)
class UpdateResult:
    """Result of processing a single file during update."""

    relative_path: str
    category: str
    action: str  # "accepted", "rejected", "blocked", "skipped", "unchanged"
    flag_details: list[str] | None = None
    warnings: list[str] | None = None


def _sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _load_json(path: Path) -> dict:
    """Load a JSON file, returning empty dict if missing."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, data: dict) -> None:
    """Write dict as pretty-printed JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, record: dict) -> None:
    """Append a single JSON record to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def fetch_upstream(vendor_dir: Path, target_dir: Path) -> str:
    """Clone or fetch the upstream repo into target_dir. Returns HEAD commit hash."""
    meta = _load_json(vendor_dir / ".upstream-meta.json")
    repo_url = meta.get("repo_url", "")
    if not repo_url:
        raise ValueError("No repo_url found in .upstream-meta.json")

    if (target_dir / ".git").is_dir():
        subprocess.run(
            ["git", "-C", str(target_dir), "fetch", "--all"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(target_dir), "reset", "--hard", "origin/main"],
            check=True,
            capture_output=True,
        )
    else:
        target_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(target_dir)],
            check=True,
            capture_output=True,
        )

    result = subprocess.run(
        ["git", "-C", str(target_dir), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def diff_trees(upstream_dir: Path, vendor_dir: Path) -> list[FileDiff]:
    """Compare upstream and vendor tracked directories, return categorized diffs."""
    import difflib

    diffs: list[FileDiff] = []

    upstream_files: set[str] = set()
    vendor_files: set[str] = set()

    for tracked in _TRACKED_DIRS:
        us_dir = upstream_dir / tracked
        vn_dir = vendor_dir / tracked

        if us_dir.is_dir():
            for f in us_dir.rglob("*"):
                if f.is_file():
                    upstream_files.add(str(f.relative_to(upstream_dir)))

        if vn_dir.is_dir():
            for f in vn_dir.rglob("*"):
                if f.is_file():
                    vendor_files.add(str(f.relative_to(vendor_dir)))

    all_paths = sorted(upstream_files | vendor_files)

    for rel_path in all_paths:
        us_file = upstream_dir / rel_path
        vn_file = vendor_dir / rel_path

        if us_file.exists() and not vn_file.exists():
            diffs.append(FileDiff(relative_path=rel_path, category="new"))
        elif not us_file.exists() and vn_file.exists():
            diffs.append(FileDiff(relative_path=rel_path, category="removed"))
        elif us_file.exists() and vn_file.exists():
            us_hash = _sha256(us_file)
            vn_hash = _sha256(vn_file)
            if us_hash == vn_hash:
                diffs.append(FileDiff(relative_path=rel_path, category="unchanged"))
            else:
                vn_lines = vn_file.read_text(encoding="utf-8", errors="replace").splitlines(
                    keepends=True
                )
                us_lines = us_file.read_text(encoding="utf-8", errors="replace").splitlines(
                    keepends=True
                )
                unified = "".join(
                    difflib.unified_diff(
                        vn_lines,
                        us_lines,
                        fromfile=f"vendor/{rel_path}",
                        tofile=f"upstream/{rel_path}",
                    )
                )
                diffs.append(
                    FileDiff(relative_path=rel_path, category="changed", unified_diff=unified)
                )

    return diffs


def scan_file_for_update(
    file_path: Path,
    scanner: object | None = None,
) -> object:
    """Run security scanner on a file. Returns ScanVerdict."""
    if scanner is None:
        from open_workspace_builder.security.scanner import Scanner

        scanner = Scanner(layers=(1, 2))

    return scanner.scan_file(file_path)  # type: ignore[union-attr]


def apply_accepted_file(
    upstream_dir: Path,
    vendor_dir: Path,
    rel_path: str,
    content_hashes: dict[str, str],
) -> dict[str, str]:
    """Copy an accepted file from upstream to vendor. Returns updated hashes dict."""
    import shutil

    src = upstream_dir / rel_path
    dst = vendor_dir / rel_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

    new_hash = _sha256(dst)
    return {**content_hashes, rel_path: new_hash}


def build_update_log_entry(
    upstream_commit: str,
    results: list[UpdateResult],
    *,
    trusted_source_exempt: bool = False,
) -> dict:
    """Build a structured log entry for the update."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "upstream_commit": upstream_commit,
        "trusted_source_exempt": trusted_source_exempt,
        "files_offered": [r.relative_path for r in results],
        "files_accepted": [r.relative_path for r in results if r.action == "accepted"],
        "files_rejected": [r.relative_path for r in results if r.action == "rejected"],
        "files_blocked": [r.relative_path for r in results if r.action == "blocked"],
        "files_warned": [r.relative_path for r in results if r.warnings],
        "flag_details": {
            r.relative_path: r.flag_details
            for r in results
            if r.flag_details
        },
    }


def update_upstream_meta(
    vendor_dir: Path,
    commit_hash: str,
) -> None:
    """Update .upstream-meta.json with new commit and fetch date."""
    meta_path = vendor_dir / ".upstream-meta.json"
    meta = _load_json(meta_path)
    updated = {
        **meta,
        "commit_hash": commit_hash,
        "fetch_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    _save_json(meta_path, updated)


def run_update(
    vendor_dir: Path,
    *,
    dry_run: bool = False,
    accept_all: bool = False,
    prompt_fn: object | None = None,
    scanner: object | None = None,
    trusted_upstream_urls: tuple[str, ...] = (),
) -> list[UpdateResult]:
    """Execute the full update workflow.

    Args:
        vendor_dir: Path to vendor/ecc/ directory.
        dry_run: If True, fetch and scan but do not write.
        accept_all: If True, auto-accept non-flagged files.
        prompt_fn: Callable(FileReview) -> str for interactive prompts.
                   Returns "a" (accept), "r" (reject), "q" (quit).
        scanner: Optional Scanner instance (for testing). When provided,
                 takes precedence over trusted-source auto-selection.
        trusted_upstream_urls: URLs whose content skips Layer 2 pattern
                               scanning (Layer 1 structural checks still run).

    Returns:
        List of UpdateResult for each file processed.
    """
    with tempfile.TemporaryDirectory() as tmp:
        upstream_dir = Path(tmp) / "upstream"
        upstream_commit = fetch_upstream(vendor_dir, upstream_dir)

        diffs = diff_trees(upstream_dir, vendor_dir)

        # Resolve scanner: explicit scanner wins; otherwise check trusted-source
        effective_scanner = scanner
        trusted_source_exempt = False
        if effective_scanner is None and trusted_upstream_urls:
            meta = _load_json(vendor_dir / ".upstream-meta.json")
            repo_url = meta.get("repo_url", "")
            if repo_url in trusted_upstream_urls:
                from open_workspace_builder.security.scanner import Scanner

                effective_scanner = Scanner(layers=(1,))
                trusted_source_exempt = True

        # Scan new and changed files
        reviews: list[FileReview] = []
        for d in diffs:
            if d.category in ("new", "changed"):
                upstream_file = upstream_dir / d.relative_path
                verdict = scan_file_for_update(
                    upstream_file, scanner=effective_scanner
                )
                reviews.append(FileReview(diff=d, verdict=verdict))
            else:
                reviews.append(FileReview(diff=d, verdict=None))

        # Process each file
        results: list[UpdateResult] = []
        content_hashes = _load_json(vendor_dir / ".content-hashes.json")
        quit_requested = False

        for review in reviews:
            d = review.diff

            if d.category in ("unchanged", "removed"):
                results.append(
                    UpdateResult(
                        relative_path=d.relative_path,
                        category=d.category,
                        action="skipped" if d.category == "removed" else "unchanged",
                    )
                )
                continue

            # Check security verdict
            is_malicious = False
            is_flagged = False
            scan_details: list[str] = []
            if review.verdict is not None:
                verdict = review.verdict
                if hasattr(verdict, "verdict"):
                    if verdict.verdict == "malicious":
                        is_malicious = True
                    elif verdict.verdict == "flagged":
                        is_flagged = True
                    if hasattr(verdict, "flags"):
                        scan_details = [
                            f"[{f.severity}] {f.category}: {f.description}"
                            for f in verdict.flags
                        ]

            if is_malicious:
                results.append(
                    UpdateResult(
                        relative_path=d.relative_path,
                        category=d.category,
                        action="blocked",
                        flag_details=scan_details,
                    )
                )
                continue

            # Warning-level findings: note as warnings but allow the file through
            file_warnings = scan_details if is_flagged else None

            if quit_requested:
                results.append(
                    UpdateResult(
                        relative_path=d.relative_path,
                        category=d.category,
                        action="rejected",
                    )
                )
                continue

            if accept_all:
                action = "a"
            elif prompt_fn is not None:
                action = prompt_fn(review)  # type: ignore[operator]
            else:
                action = "a"

            if action == "q":
                quit_requested = True
                results.append(
                    UpdateResult(
                        relative_path=d.relative_path,
                        category=d.category,
                        action="rejected",
                    )
                )
                continue

            if action == "a":
                if not dry_run:
                    content_hashes = apply_accepted_file(
                        upstream_dir, vendor_dir, d.relative_path, content_hashes
                    )
                results.append(
                    UpdateResult(
                        relative_path=d.relative_path,
                        category=d.category,
                        action="accepted",
                        warnings=file_warnings,
                    )
                )
            else:
                results.append(
                    UpdateResult(
                        relative_path=d.relative_path,
                        category=d.category,
                        action="rejected",
                        warnings=file_warnings,
                    )
                )

        # Write metadata (unless dry-run)
        if not dry_run:
            _save_json(vendor_dir / ".content-hashes.json", content_hashes)
            update_upstream_meta(vendor_dir, upstream_commit)

        # Always write update log
        log_entry = build_update_log_entry(
            upstream_commit,
            results,
            trusted_source_exempt=trusted_source_exempt,
        )
        _append_jsonl(vendor_dir / ".update-log.jsonl", log_entry)

    return results


def get_status(vendor_dir: Path, ledger_path: Path | None = None) -> dict:
    """Read current ECC status for display.

    Returns:
        Dict with keys: repo_url, commit_hash, fetch_date, flag_history, recent_updates.
    """
    from open_workspace_builder.security.reputation import ReputationLedger

    meta = _load_json(vendor_dir / ".upstream-meta.json")

    ledger = ReputationLedger(ledger_path) if ledger_path else ReputationLedger()
    history = ledger.get_history("ecc")

    recent_updates: list[dict] = []
    log_path = vendor_dir / ".update-log.jsonl"
    if log_path.exists():
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        for line in lines[-5:]:
            try:
                recent_updates.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return {
        "repo_url": meta.get("repo_url", "unknown"),
        "commit_hash": meta.get("commit_hash", "unknown"),
        "fetch_date": meta.get("fetch_date", "unknown"),
        "flag_history": [
            {
                "timestamp": e.timestamp,
                "file_path": e.file_path,
                "flag_category": e.flag_category,
                "severity": e.severity,
                "disposition": e.disposition,
            }
            for e in history
        ],
        "recent_updates": recent_updates,
    }
