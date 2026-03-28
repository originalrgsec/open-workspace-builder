"""Parse Claude Code JSONL session files into TokenUsage records."""

from __future__ import annotations

import json
from pathlib import Path

from open_workspace_builder.tokens.models import TokenUsage


def project_name_from_dir(dirname: str) -> str:
    """Extract a human-readable project name from a Claude Code project directory name.

    Claude Code encodes the workspace path as a directory name by replacing '/'
    with '-'. For example: '-Users-rgraber-projects-Code-open-workspace-builder'
    represents '/Users/rgraber/projects/Code/open-workspace-builder'.

    We reconstruct the path, then take the final path segment as the project name.
    This preserves hyphenated project names like 'open-workspace-builder'.
    """
    # The dirname is a path with '/' replaced by '-' and a leading '-'.
    # Reconstruct by replacing the leading '-' with '/' and splitting on
    # known path prefixes to find the last real directory segment.
    # Replace remaining '-' that are actual path separators.
    # Strategy: the dirname encodes '/' as '-'. We cannot distinguish path
    # separators from hyphens in names without knowing the filesystem, but
    # Claude Code uses the cwd path. Known patterns:
    # -Users-<user>-...-<project>  where segments are single words or
    # well-known dirs (Users, projects, Code, Documents, etc.)
    # The safest approach: reconstruct from the known prefix pattern.
    # Split on known single-word path segments that never contain hyphens.
    known_segments = {
        "Users", "home", "projects", "Code", "PersonalCode", "Documents",
        "Desktop", "Downloads", "Claude", "Cowork", "var", "tmp", "opt",
    }

    parts = dirname.lstrip("-").split("-")
    # Walk from left, consuming known single-word segments. Everything after
    # the last known segment is the project name.
    last_known_idx = -1
    for i, part in enumerate(parts):
        if part in known_segments:
            last_known_idx = i

    if last_known_idx >= 0 and last_known_idx < len(parts) - 1:
        return "-".join(parts[last_known_idx + 1 :])

    # Fallback: return the full dirname minus leading hyphen.
    return dirname.lstrip("-") or dirname


def discover_session_files(projects_dir: Path) -> list[Path]:
    """Find all .jsonl session files under the Claude Code projects directory.

    Returns a sorted list of paths (sorted by name for deterministic ordering).
    """
    if not projects_dir.is_dir():
        return []
    files: list[Path] = []
    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir():
            continue
        for jsonl_file in sorted(project_dir.glob("*.jsonl")):
            if jsonl_file.is_file():
                files.append(jsonl_file)
    return files


def parse_session_file(path: Path) -> list[TokenUsage]:
    """Parse a single JSONL session file and extract TokenUsage from assistant messages.

    Skips malformed lines and messages without usage data. Never raises on
    parse errors — returns what it can extract.
    """
    usages: list[TokenUsage] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return usages

    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        if msg.get("type") != "assistant":
            continue

        message = msg.get("message")
        if not isinstance(message, dict):
            continue

        usage = message.get("usage")
        if not isinstance(usage, dict):
            continue

        model = message.get("model", "unknown")
        timestamp = msg.get("timestamp", "")

        usages.append(
            TokenUsage(
                model=model,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
                cache_read_tokens=usage.get("cache_read_input_tokens", 0),
                timestamp=timestamp,
            )
        )

    return usages
