"""S014 — Workspace differ: compare existing workspace against builder reference."""

from __future__ import annotations

import hashlib
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from open_workspace_builder.config import Config, load_config
from open_workspace_builder.engine.builder import WorkspaceBuilder


@dataclass(frozen=True)
class FileGap:
    """A single difference between reference and actual workspace."""

    path: str  # relative path within workspace
    category: Literal["missing", "outdated", "modified", "extra"]
    reference_hash: str | None  # SHA-256 of reference file (None for "extra")
    actual_hash: str | None  # SHA-256 of actual file (None for "missing")
    recommendation: str  # human-readable action suggestion


@dataclass(frozen=True)
class DiffReport:
    """Full comparison report between reference and actual workspace."""

    gaps: tuple[FileGap, ...] = ()
    summary: dict[str, int] = field(default_factory=dict)


def _sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _collect_relative_files(root: Path) -> set[str]:
    """Walk a directory tree and return all file paths relative to root."""
    files: set[str] = set()
    if not root.is_dir():
        return files
    for item in root.rglob("*"):
        if item.is_file():
            files.add(str(item.relative_to(root)))
    return files


def diff_workspace(
    vault_path: Path,
    config: Config | None = None,
    content_root: Path | None = None,
) -> DiffReport:
    """Compare an existing workspace against the builder's reference output.

    Generates the reference workspace in a temp directory, then walks both trees
    comparing file presence and content hashes.
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

    # Generate reference workspace to a temp directory
    with tempfile.TemporaryDirectory(prefix="owb-diff-ref-") as tmp_dir:
        ref_path = Path(tmp_dir) / "reference"
        builder = WorkspaceBuilder(config, content_root, dry_run=False)
        builder.build(ref_path)

        ref_files = _collect_relative_files(ref_path)
        actual_files = _collect_relative_files(vault_path)

        gaps: list[FileGap] = []

        # Files in reference but not in actual → missing
        for rel in sorted(ref_files - actual_files):
            gaps.append(
                FileGap(
                    path=rel,
                    category="missing",
                    reference_hash=_sha256(ref_path / rel),
                    actual_hash=None,
                    recommendation=f"Create {rel} from reference template",
                )
            )

        # Files in both → compare hashes
        for rel in sorted(ref_files & actual_files):
            ref_hash = _sha256(ref_path / rel)
            actual_hash = _sha256(vault_path / rel)
            if ref_hash != actual_hash:
                # Check if the file in the workspace has user customizations
                # by comparing file sizes; larger actual files likely have user edits
                ref_size = (ref_path / rel).stat().st_size
                actual_size = (vault_path / rel).stat().st_size
                if actual_size > ref_size:
                    gaps.append(
                        FileGap(
                            path=rel,
                            category="modified",
                            reference_hash=ref_hash,
                            actual_hash=actual_hash,
                            recommendation=(
                                f"Review changes in {rel} — file has user customizations"
                            ),
                        )
                    )
                else:
                    gaps.append(
                        FileGap(
                            path=rel,
                            category="outdated",
                            reference_hash=ref_hash,
                            actual_hash=actual_hash,
                            recommendation=f"Update {rel} to latest reference version",
                        )
                    )

        # Files in actual but not in reference → extra
        for rel in sorted(actual_files - ref_files):
            gaps.append(
                FileGap(
                    path=rel,
                    category="extra",
                    reference_hash=None,
                    actual_hash=_sha256(vault_path / rel),
                    recommendation=f"User file {rel} — no action needed",
                )
            )

    summary = {"missing": 0, "outdated": 0, "modified": 0, "extra": 0}
    for gap in gaps:
        summary[gap.category] += 1

    return DiffReport(gaps=tuple(gaps), summary=summary)


def format_diff_report(report: DiffReport) -> str:
    """Format a DiffReport as a human-readable string."""
    lines: list[str] = []
    icons = {"missing": "[-]", "outdated": "[~]", "modified": "[*]", "extra": "[+]"}

    if not report.gaps:
        lines.append("Workspace is up to date — no gaps found.")
        return "\n".join(lines)

    lines.append("Workspace Diff Report")
    lines.append("=" * 50)

    for category in ("missing", "outdated", "modified", "extra"):
        category_gaps = [g for g in report.gaps if g.category == category]
        if not category_gaps:
            continue
        lines.append(f"\n{category.upper()} ({len(category_gaps)}):")
        for gap in category_gaps:
            lines.append(f"  {icons[gap.category]} {gap.path}")
            lines.append(f"      {gap.recommendation}")

    lines.append(f"\nSummary: {report.summary}")
    return "\n".join(lines)


def diff_report_to_dict(report: DiffReport) -> dict:
    """Convert a DiffReport to a JSON-serializable dictionary."""
    return {
        "gaps": [
            {
                "path": g.path,
                "category": g.category,
                "reference_hash": g.reference_hash,
                "actual_hash": g.actual_hash,
                "recommendation": g.recommendation,
            }
            for g in report.gaps
        ],
        "summary": report.summary,
    }
