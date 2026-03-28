"""Append-only JSONL ledger for session cost records."""

from __future__ import annotations

import fcntl
import json
from dataclasses import asdict
from pathlib import Path

from open_workspace_builder.tokens.models import LedgerEntry, TokenCost


def append_entry(ledger_path: Path, entry: LedgerEntry) -> None:
    """Append a single LedgerEntry as a JSON line. Skips duplicates by session_id.

    Creates the file and parent directories if they do not exist.
    Uses file locking to prevent duplicate writes from concurrent hook invocations.
    """
    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    with ledger_path.open("a+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            existing_ids = _read_session_ids_from_text(f.read())
            if entry.session_id in existing_ids:
                return
            f.seek(0, 2)  # seek to end
            f.write(json.dumps(asdict(entry), default=str) + "\n")
            f.flush()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def read_entries(
    ledger_path: Path,
    since: str | None = None,
    until: str | None = None,
) -> list[LedgerEntry]:
    """Read all LedgerEntry records from the ledger file.

    Skips malformed lines. Optionally filters by date range (YYYYMMDD, inclusive).
    """
    if not ledger_path.is_file():
        return []

    entries: list[LedgerEntry] = []
    try:
        text = ledger_path.read_text(encoding="utf-8")
    except OSError:
        return entries

    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue

        try:
            entry = _entry_from_dict(raw)
        except (KeyError, TypeError):
            continue

        if not _matches_date_filter(entry.timestamp, since, until):
            continue

        entries.append(entry)

    return entries


def _entry_from_dict(raw: dict) -> LedgerEntry:
    """Reconstruct a LedgerEntry from a parsed JSON dict."""
    cost_data = raw.get("cost", {})
    return LedgerEntry(
        session_id=raw["session_id"],
        project=raw["project"],
        timestamp=raw["timestamp"],
        total_input=raw["total_input"],
        total_output=raw["total_output"],
        total_cache_creation=raw["total_cache_creation"],
        total_cache_read=raw["total_cache_read"],
        cost=TokenCost(
            input_cost=cost_data.get("input_cost", 0.0),
            output_cost=cost_data.get("output_cost", 0.0),
            cache_write_cost=cost_data.get("cache_write_cost", 0.0),
            cache_read_cost=cost_data.get("cache_read_cost", 0.0),
        ),
        story_id=raw.get("story_id", ""),
    )


def _read_session_ids_from_text(text: str) -> set[str]:
    """Extract session IDs from ledger file content."""
    ids: set[str] = set()
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
            ids.add(raw["session_id"])
        except (json.JSONDecodeError, KeyError):
            continue
    return ids


def _matches_date_filter(
    timestamp: str, since: str | None, until: str | None
) -> bool:
    """Check if a timestamp falls within the date filter range."""
    if not since and not until:
        return True
    date_str = timestamp[:10].replace("-", "") if len(timestamp) >= 10 else ""
    if since and date_str < since:
        return False
    if until and date_str > until:
        return False
    return True
