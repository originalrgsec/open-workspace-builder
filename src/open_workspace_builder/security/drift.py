"""Directive drift detection for workspace config files (S082).

Computes SHA-256 hashes of directive files (CLAUDE.md, agents, rules, skills,
OWB config) and compares against a stored baseline. Modifications between
baseline updates are reported as drift.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1

# File categories to track (relative glob patterns from workspace root)
TRACKED_PATTERNS: tuple[str, ...] = (
    "CLAUDE.md",
    ".claude/CLAUDE.md",
    ".claude/agents/*.md",
    ".claude/rules/**/*.md",
    ".claude/commands/**/*.md",
)

# Directories to scan exhaustively for any file
TRACKED_DIRS: tuple[str, ...] = (
    ".claude/agents",
    ".claude/rules",
    ".claude/commands",
)


@dataclass(frozen=True)
class DriftEntry:
    """A single file's drift status."""

    rel_path: str
    status: str  # "ok", "modified", "added", "deleted", "error"
    message: str = ""


@dataclass(frozen=True)
class DriftReport:
    """Result of a drift check."""

    has_drift: bool
    exit_code: int  # 0=clean, 1=drift, 2=no baseline
    modified: tuple[DriftEntry, ...] = ()
    added: tuple[DriftEntry, ...] = ()
    deleted: tuple[DriftEntry, ...] = ()
    unchanged: tuple[DriftEntry, ...] = ()
    errors: tuple[DriftEntry, ...] = ()
    baseline_timestamp: str = ""

    def to_json(self) -> str:
        """Serialize report to JSON string."""
        return json.dumps(
            {
                "has_drift": self.has_drift,
                "exit_code": self.exit_code,
                "baseline_timestamp": self.baseline_timestamp,
                "modified": [{"path": e.rel_path, "message": e.message} for e in self.modified],
                "added": [{"path": e.rel_path} for e in self.added],
                "deleted": [{"path": e.rel_path} for e in self.deleted],
                "unchanged": [{"path": e.rel_path} for e in self.unchanged],
                "errors": [{"path": e.rel_path, "message": e.message} for e in self.errors],
            },
            indent=2,
        )


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file using chunked reads."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


def _discover_tracked_files(workspace: Path) -> list[Path]:
    """Find all directive files in the workspace that should be tracked."""
    found: set[Path] = set()

    # Check specific file paths
    for pattern in TRACKED_PATTERNS:
        if "*" in pattern or "?" in pattern:
            found.update(workspace.glob(pattern))
        else:
            candidate = workspace / pattern
            if candidate.is_file():
                found.add(candidate)

    # Scan tracked directories exhaustively
    for dir_rel in TRACKED_DIRS:
        dir_path = workspace / dir_rel
        if dir_path.is_dir():
            for child in dir_path.rglob("*"):
                if child.is_file():
                    found.add(child)

    return sorted(found)


# ---------------------------------------------------------------------------
# Baseline management
# ---------------------------------------------------------------------------


def update_baseline(workspace: Path, baseline_path: Path) -> None:
    """Compute and store a drift baseline for the workspace.

    Uses atomic write (write to temp file, then rename) to prevent corruption.
    """
    workspace = workspace.resolve()
    files = _discover_tracked_files(workspace)

    entries: dict[str, dict[str, str]] = {}
    for f in files:
        rel = str(f.relative_to(workspace))
        entries[rel] = {"sha256": _sha256(f)}

    data = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "workspace": str(workspace),
        "files": entries,
    }

    content = json.dumps(data, indent=2) + "\n"

    # Atomic write: write to temp file in same directory, then rename
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(baseline_path.parent),
        prefix=".drift-baseline-",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_name)
    try:
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(baseline_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    finally:
        # Close the file descriptor opened by mkstemp
        import os

        try:
            os.close(fd)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Drift check
# ---------------------------------------------------------------------------


def check_drift(
    workspace: Path,
    baseline_path: Path,
    *,
    file_glob: str | None = None,
) -> DriftReport:
    """Compare current workspace state against a stored baseline.

    Args:
        workspace: Path to workspace root.
        baseline_path: Path to the drift-baseline.json file.
        file_glob: Optional glob pattern to restrict which files are checked.

    Returns:
        DriftReport with categorized entries and exit code.
    """
    workspace = workspace.resolve()

    # No baseline exists
    if not baseline_path.is_file():
        return DriftReport(
            has_drift=False,
            exit_code=2,
        )

    data = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline_files: dict[str, dict[str, str]] = data.get("files", {})
    baseline_timestamp = data.get("timestamp", "")

    # Discover current files
    current_files = _discover_tracked_files(workspace)
    current_rel_paths = {str(f.relative_to(workspace)) for f in current_files}

    # Apply glob filter if specified
    if file_glob is not None:
        baseline_files = {k: v for k, v in baseline_files.items() if fnmatch(k, file_glob)}
        current_files = [
            f for f in current_files if fnmatch(str(f.relative_to(workspace)), file_glob)
        ]
        current_rel_paths = {str(f.relative_to(workspace)) for f in current_files}

    modified: list[DriftEntry] = []
    unchanged: list[DriftEntry] = []
    deleted: list[DriftEntry] = []
    errors: list[DriftEntry] = []
    added: list[DriftEntry] = []

    # Check files in baseline
    for rel_path, entry in baseline_files.items():
        full_path = workspace / rel_path
        if not full_path.exists():
            deleted.append(DriftEntry(rel_path=rel_path, status="deleted"))
            continue

        try:
            current_hash = _sha256(full_path)
        except OSError as exc:
            errors.append(
                DriftEntry(
                    rel_path=rel_path,
                    status="error",
                    message=str(exc),
                )
            )
            continue

        if current_hash != entry["sha256"]:
            modified.append(
                DriftEntry(
                    rel_path=rel_path,
                    status="modified",
                    message="hash mismatch",
                )
            )
        else:
            unchanged.append(DriftEntry(rel_path=rel_path, status="ok"))

    # Check for new files not in baseline
    baseline_rel_paths = set(baseline_files.keys())
    for rel_path in sorted(current_rel_paths - baseline_rel_paths):
        added.append(DriftEntry(rel_path=rel_path, status="added"))

    has_drift = bool(modified or added or deleted)
    exit_code = 1 if has_drift else 0

    return DriftReport(
        has_drift=has_drift,
        exit_code=exit_code,
        modified=tuple(modified),
        added=tuple(added),
        deleted=tuple(deleted),
        unchanged=tuple(unchanged),
        errors=tuple(errors),
        baseline_timestamp=baseline_timestamp,
    )
