"""S013 — Reputation ledger: append-only event log for security findings."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_LEDGER_PATH = Path("~/.cwb/reputation-ledger.jsonl")


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
        """Append a single event to the ledger."""
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event)) + "\n")

    def check_threshold(self, source: str, threshold: int = 3) -> bool:
        """Return True if confirmed malicious count for source exceeds threshold."""
        count = sum(
            1 for e in self._read_all()
            if e.source == source and e.disposition == "confirmed_malicious"
        )
        return count > threshold

    def get_history(self, source: str) -> list[FlagEvent]:
        """Return all events for a given source."""
        return [e for e in self._read_all() if e.source == source]

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
