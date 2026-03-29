"""S013 — Reputation ledger: append-only event log for security findings."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_LEDGER_PATH = Path("~/.owb/reputation-ledger.jsonl")


@dataclass(frozen=True)
class FlagEvent:
    """A single recorded security event."""

    timestamp: str
    source: str
    file_path: str
    flag_category: str
    severity: str
    disposition: str  # "confirmed_malicious", "false_positive", "unreviewed"
    details: str

    @staticmethod
    def now(
        source: str,
        file_path: str,
        flag_category: str,
        severity: str,
        disposition: str,
        details: str,
    ) -> FlagEvent:
        """Create a FlagEvent with the current UTC timestamp."""
        return FlagEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            source=source,
            file_path=file_path,
            flag_category=flag_category,
            severity=severity,
            disposition=disposition,
            details=details,
        )


class ReputationLedger:
    """Append-only reputation ledger stored as JSONL."""

    def __init__(self, ledger_path: str | Path = _DEFAULT_LEDGER_PATH) -> None:
        self._path = Path(ledger_path).expanduser()
        self._ensure_file()

    def _ensure_file(self) -> None:
        """Create ledger file with 0600 permissions if it doesn't exist."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.touch()
            os.chmod(self._path, 0o600)

    def record_event(self, event: FlagEvent) -> None:
        """Record an event, deduplicating by (source, file_path).

        If an event with the same (source, file_path) already exists, it is
        replaced with the new event. Otherwise, the new event is appended.
        Writes atomically via temp file + rename.
        """
        existing = self._read_all()
        key = (event.source, event.file_path)
        updated = [e for e in existing if (e.source, e.file_path) != key]
        updated.append(event)
        self._write_all(updated)

    def check_threshold(self, source: str, threshold: int = 3) -> bool:
        """Return True if distinct confirmed-malicious files for source exceeds threshold."""
        distinct_files = {
            e.file_path
            for e in self._read_all()
            if e.source == source and e.disposition == "confirmed_malicious"
        }
        return len(distinct_files) > threshold

    def get_history(self, source: str) -> list[FlagEvent]:
        """Return all events for a given source."""
        return [e for e in self._read_all() if e.source == source]

    def _write_all(self, events: list[FlagEvent]) -> None:
        """Atomically rewrite the ledger with the given events."""
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._path.parent), suffix=".jsonl.tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                for e in events:
                    f.write(json.dumps(asdict(e)) + "\n")
            os.replace(tmp_path, self._path)
            os.chmod(self._path, 0o600)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _read_all(self) -> list[FlagEvent]:
        """Read all events from the ledger file."""
        events: list[FlagEvent] = []
        if not self._path.exists():
            return events
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                events.append(FlagEvent(**data))
            except (json.JSONDecodeError, TypeError):
                continue  # Skip malformed lines.
        return events
