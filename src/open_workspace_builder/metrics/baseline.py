"""Baseline metrics collection for git-backed Python projects (OWB-S049).

Scans a git repository to collect source LOC, test LOC, test count,
commit count, date range, and per-module breakdown. All data structures
are frozen (immutable).
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModuleMetric:
    """LOC breakdown for a single source module (top-level package directory)."""

    name: str
    loc: int
    path: str


@dataclass(frozen=True)
class BaselineMetrics:
    """Aggregate baseline metrics for a project snapshot."""

    source_loc: int
    test_loc: int
    test_count: int
    commit_count: int
    date_range: tuple[str, str]  # (oldest, newest) ISO dates
    modules: tuple[ModuleMetric, ...]


# ── Internal helpers ─────────────────────────────────────────────────────


def _count_lines(file_path: Path) -> int:
    """Count non-empty lines in a single file."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        return sum(1 for line in text.splitlines() if line.strip())
    except (OSError, UnicodeDecodeError):
        return 0


def _count_loc_in_tree(root: Path, glob_pattern: str = "**/*.py") -> int:
    """Sum non-empty lines across all matching files under *root*."""
    return sum(_count_lines(p) for p in root.glob(glob_pattern) if p.is_file())


def _count_test_functions(tests_dir: Path) -> int:
    """Count ``def test_`` occurrences in all Python files under *tests_dir*."""
    pattern = re.compile(r"^\s*def test_", re.MULTILINE)
    total = 0
    for py_file in tests_dir.glob("**/*.py"):
        try:
            text = py_file.read_text(encoding="utf-8", errors="replace")
            total += len(pattern.findall(text))
        except (OSError, UnicodeDecodeError):
            continue
    return total


def _git_log_oneline(project_path: Path, tag_range: str | None = None) -> str:
    """Return raw ``git log --oneline`` output, optionally scoped to a tag range."""
    cmd = ["git", "-C", str(project_path), "log", "--oneline"]
    if tag_range:
        cmd.append(tag_range)
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return result.stdout


def _git_log_dates(project_path: Path, tag_range: str | None = None) -> str:
    """Return raw ``git log --format=%aI`` output for date extraction."""
    cmd = ["git", "-C", str(project_path), "log", "--format=%aI"]
    if tag_range:
        cmd.append(tag_range)
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return result.stdout


def _parse_commit_count(log_output: str) -> int:
    """Count non-empty lines in git log oneline output."""
    return sum(1 for line in log_output.strip().splitlines() if line.strip())


def _parse_date_range(dates_output: str) -> tuple[str, str]:
    """Extract (oldest, newest) ISO date strings from git log dates output."""
    dates = [d.strip() for d in dates_output.strip().splitlines() if d.strip()]
    if not dates:
        return ("", "")
    # git log outputs newest first
    return (dates[-1], dates[0])


def _discover_modules(src_dir: Path) -> tuple[ModuleMetric, ...]:
    """Discover top-level subdirectories under src/<package>/ as modules."""
    if not src_dir.is_dir():
        return ()
    # Find the first package directory under src/
    package_dirs = [d for d in src_dir.iterdir() if d.is_dir() and (d / "__init__.py").exists()]
    if not package_dirs:
        return ()

    modules: list[ModuleMetric] = []
    for pkg_dir in package_dirs:
        for sub in sorted(pkg_dir.iterdir()):
            if sub.is_dir() and (sub / "__init__.py").exists():
                loc = _count_loc_in_tree(sub)
                modules.append(
                    ModuleMetric(
                        name=sub.name,
                        loc=loc,
                        path=str(sub.relative_to(src_dir.parent)),
                    )
                )
    return tuple(modules)


# ── Public API ───────────────────────────────────────────────────────────


def collect_baseline(
    project_path: Path,
    tag_range: str | None = None,
) -> BaselineMetrics:
    """Scan a git repository and collect baseline metrics.

    Parameters
    ----------
    project_path:
        Root of the git repository to analyse.
    tag_range:
        Optional git revision range (e.g. ``v0.1.0..v0.2.0``) to scope
        commit count and date range.
    """
    project_path = project_path.resolve()
    src_dir = project_path / "src"
    tests_dir = project_path / "tests"

    # LOC counts
    source_loc = _count_loc_in_tree(src_dir) if src_dir.is_dir() else 0
    test_loc = _count_loc_in_tree(tests_dir) if tests_dir.is_dir() else 0
    test_count = _count_test_functions(tests_dir) if tests_dir.is_dir() else 0

    # Git history
    log_output = _git_log_oneline(project_path, tag_range)
    commit_count = _parse_commit_count(log_output)

    dates_output = _git_log_dates(project_path, tag_range)
    date_range = _parse_date_range(dates_output)

    # Per-module breakdown
    modules = _discover_modules(src_dir)

    return BaselineMetrics(
        source_loc=source_loc,
        test_loc=test_loc,
        test_count=test_count,
        commit_count=commit_count,
        date_range=date_range,
        modules=modules,
    )


def render_baseline_summary(metrics: BaselineMetrics) -> str:
    """Render baseline metrics as a markdown summary."""
    lines: list[str] = [
        "# Baseline Metrics",
        "",
        "## Overview",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Source LOC | {metrics.source_loc:,} |",
        f"| Test LOC | {metrics.test_loc:,} |",
        f"| Test Count | {metrics.test_count:,} |",
        f"| Commit Count | {metrics.commit_count:,} |",
        f"| Date Range | {metrics.date_range[0]} to {metrics.date_range[1]} |",
        "",
    ]

    if metrics.modules:
        lines.extend(
            [
                "## Module Breakdown",
                "",
                "| Module | LOC | Path |",
                "|--------|-----|------|",
            ]
        )
        for mod in metrics.modules:
            lines.append(f"| {mod.name} | {mod.loc:,} | `{mod.path}` |")
        lines.append("")

    return "\n".join(lines)


def metrics_to_dict(metrics: BaselineMetrics) -> dict:
    """Convert BaselineMetrics to a JSON-serializable dictionary."""
    raw = asdict(metrics)
    # asdict converts tuples to lists; date_range should stay a list for JSON
    return raw


def write_baseline(metrics: BaselineMetrics, output_dir: Path) -> list[Path]:
    """Write baseline metrics to *output_dir*/metrics/.

    Creates:
    - ``metrics/baseline-summary.md`` — human-readable markdown
    - ``metrics/baseline.json`` — machine-readable JSON

    Returns the list of created file paths.
    """
    metrics_dir = output_dir / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)

    md_path = metrics_dir / "baseline-summary.md"
    md_path.write_text(render_baseline_summary(metrics), encoding="utf-8")

    json_path = metrics_dir / "baseline.json"
    json_path.write_text(
        json.dumps(metrics_to_dict(metrics), indent=2) + "\n",
        encoding="utf-8",
    )

    return [md_path, json_path]
