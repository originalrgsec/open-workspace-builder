"""OWB-S107b — SBOM provenance detection.

Where did this skill or agent come from? Four sources, in priority order:

1. **Frontmatter** — explicit ``source:`` field on the component itself.
   Highest confidence: the author told us directly.
2. **Install record** — a future ``owb skill install`` command will write
   records to ``.owb/install-records/`` capturing the package name, version,
   install timestamp, and source URL. S107b ships the *reader* now so the
   schema is locked in; the writer is a future story.
3. **Git history** — ``git log --follow`` on the component file. If the
   workspace is a git repo and has an ``origin`` remote, we get a
   high-confidence source URL plus the commit SHA. If there is no remote,
   we still record the commit SHA at medium confidence.
4. **Local fallback** — none of the above worked. Low confidence; the
   component genuinely could be local-only or our detection just missed.

Each :class:`Provenance` record carries a :class:`ProvenanceConfidence` so
downstream consumers can decide how much to trust it.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class ProvenanceType(str, Enum):
    """Where the provenance information was sourced from."""

    FRONTMATTER = "frontmatter"
    INSTALL_RECORD = "install-record"
    GIT_HISTORY = "git-history"
    LOCAL = "local"


class ProvenanceConfidence(str, Enum):
    """How confident we are in the recorded provenance."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class Provenance:
    """Provenance information for a single component.

    Attributes:
        type: Where this provenance came from.
        source: Canonical source URL or identifier (None for local fallback
            and for git-history without an origin remote).
        commit: Git commit SHA where the file was added, when known.
        package: Package name from an install record, when known.
        version: Package version from an install record, when known.
        installed_at: ISO timestamp from an install record, when known.
        confidence: How much to trust this entry.
    """

    type: ProvenanceType
    confidence: ProvenanceConfidence
    source: str | None = None
    commit: str | None = None
    package: str | None = None
    version: str | None = None
    installed_at: str | None = None


@dataclass(frozen=True)
class InstallRecord:
    """One record from ``.owb/install-records/skills.json``."""

    path: str
    package: str
    version: str
    installed_at: str
    source: str


# ---------------------------------------------------------------------------
# Install record reader
# ---------------------------------------------------------------------------


_INSTALL_RECORDS_PATH = (".owb", "install-records", "skills.json")


def read_install_record(
    *,
    workspace: Path,
    component_relpath: str,
) -> InstallRecord | None:
    """Look up a component's install record, if any.

    Args:
        workspace: Workspace root.
        component_relpath: The component path relative to workspace, in
            forward-slash form.

    Returns:
        The matching :class:`InstallRecord` or ``None`` if no record file
        exists or no record matches.
    """
    record_file = workspace
    for part in _INSTALL_RECORDS_PATH:
        record_file = record_file / part

    if not record_file.is_file():
        return None

    try:
        raw = record_file.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(data, dict):
        return None
    records = data.get("records", [])
    if not isinstance(records, list):
        return None

    for entry in records:
        if not isinstance(entry, dict):
            continue
        if entry.get("path") != component_relpath:
            continue
        try:
            return InstallRecord(
                path=str(entry["path"]),
                package=str(entry["package"]),
                version=str(entry["version"]),
                installed_at=str(entry["installed_at"]),
                source=str(entry["source"]),
            )
        except KeyError:
            return None
    return None


# ---------------------------------------------------------------------------
# Git history walker
# ---------------------------------------------------------------------------


_GITHUB_SSH_RE = re.compile(r"^git@([^:]+):(.+?)(?:\.git)?$")
_GITHUB_HTTPS_RE = re.compile(r"^https?://([^/]+)/(.+?)(?:\.git)?/?$")


def _normalize_remote_url(url: str) -> str:
    """Convert SSH-form git URLs to canonical https form for stable identity."""
    url = url.strip()
    ssh_match = _GITHUB_SSH_RE.match(url)
    if ssh_match:
        host, repo = ssh_match.group(1), ssh_match.group(2)
        if not repo.endswith(".git"):
            repo = f"{repo}.git"
        return f"https://{host}/{repo}"
    https_match = _GITHUB_HTTPS_RE.match(url)
    if https_match:
        host, repo = https_match.group(1), https_match.group(2)
        if not repo.endswith(".git"):
            repo = f"{repo}.git"
        return f"https://{host}/{repo}"
    return url


def _run_git(repo: Path, *args: str) -> str | None:
    """Run a git command quietly. Returns stdout or None on failure."""
    try:
        result = subprocess.run(  # nosec B603 — controlled args, no shell
            ["git", *args],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _detect_git_provenance(
    component_path: Path,
    workspace: Path,
) -> Provenance | None:
    """Look up the commit that added a file and the workspace's origin remote."""
    # Is the workspace inside a git repo?
    inside = _run_git(workspace, "rev-parse", "--is-inside-work-tree")
    if inside != "true":
        return None

    # Find the commit that added the file (use --diff-filter=A for the
    # add commit, fall back to the first commit touching the path).
    try:
        rel = component_path.relative_to(workspace)
    except ValueError:
        return None

    # `--follow` so renames don't lose history.
    log_out = _run_git(
        workspace,
        "log",
        "--follow",
        "--diff-filter=A",
        "--pretty=format:%H",
        "-1",
        "--",
        str(rel),
    )
    if not log_out:
        # Fall back to first commit touching the file.
        log_out = _run_git(
            workspace,
            "log",
            "--follow",
            "--pretty=format:%H",
            "-1",
            "--",
            str(rel),
        )
    if not log_out:
        return None

    commit = log_out.splitlines()[0].strip()
    if len(commit) != 40:
        return None

    # Try to read the origin remote URL
    origin = _run_git(workspace, "config", "--get", "remote.origin.url")
    if origin:
        return Provenance(
            type=ProvenanceType.GIT_HISTORY,
            confidence=ProvenanceConfidence.HIGH,
            source=_normalize_remote_url(origin),
            commit=commit,
        )

    return Provenance(
        type=ProvenanceType.GIT_HISTORY,
        confidence=ProvenanceConfidence.MEDIUM,
        source="local-git",
        commit=commit,
    )


# ---------------------------------------------------------------------------
# Top-level detection
# ---------------------------------------------------------------------------


def detect_provenance(
    *,
    component_path: Path,
    workspace: Path,
    frontmatter: Mapping[str, str],
) -> Provenance:
    """Detect provenance for a component using the four-source priority order."""
    # Step 1: explicit frontmatter
    explicit = frontmatter.get("source") if frontmatter else None
    if explicit:
        return Provenance(
            type=ProvenanceType.FRONTMATTER,
            confidence=ProvenanceConfidence.HIGH,
            source=explicit,
        )

    # Step 2: install record
    if component_path.is_file():
        try:
            relpath = str(component_path.relative_to(workspace)).replace("\\", "/")
            record = read_install_record(
                workspace=workspace,
                component_relpath=relpath,
            )
            if record is not None:
                return Provenance(
                    type=ProvenanceType.INSTALL_RECORD,
                    confidence=ProvenanceConfidence.HIGH,
                    source=record.source,
                    package=record.package,
                    version=record.version,
                    installed_at=record.installed_at,
                )
        except ValueError:
            pass

    # Step 3: git history
    if component_path.is_file():
        git_prov = _detect_git_provenance(component_path, workspace)
        if git_prov is not None:
            return git_prov

    # Step 4: local fallback
    return Provenance(
        type=ProvenanceType.LOCAL,
        confidence=ProvenanceConfidence.LOW,
    )
