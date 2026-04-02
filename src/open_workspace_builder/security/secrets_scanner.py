"""Secrets scanning via external tools (OWB-S086).

Shells out to ``gitleaks`` or ``ggshield`` — never imports them as libraries.
Both tools are optional external binaries; this module degrades gracefully
when they are not installed.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class SecretFinding:
    """A single secrets finding from a scanner."""

    file: str
    line: int
    rule_id: str
    description: str
    match: str  # redacted snippet


class SecretsBackend(Protocol):
    """Protocol that all secrets scanner backends must satisfy."""

    def scan_path(
        self, path: Path, *, json_output: bool = False
    ) -> tuple[list[SecretFinding], int]: ...

    def is_available(self) -> bool: ...

    def version(self) -> str | None: ...


class GitleaksBackend:
    """Default secrets scanner — shells out to gitleaks."""

    EXPECTED_BINARY = "gitleaks"

    def is_available(self) -> bool:
        """Return True if the gitleaks binary is on PATH."""
        return shutil.which(self.EXPECTED_BINARY) is not None

    def version(self) -> str | None:
        """Return gitleaks version string, or None if unavailable."""
        if not self.is_available():
            return None
        result = subprocess.run(
            [self.EXPECTED_BINARY, "version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else None

    def scan_path(
        self, path: Path, *, json_output: bool = False
    ) -> tuple[list[SecretFinding], int]:
        """Run gitleaks detect on the given path.

        Returns (findings, exit_code) where exit_code 0 means clean
        and 1 means leaks were found.
        """
        cmd = [
            self.EXPECTED_BINARY,
            "detect",
            "--source",
            str(path),
            "--no-git",
            "--report-format",
            "json",
            "--report-path",
            "/dev/stdout",
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        findings = _parse_gitleaks_json(result.stdout)
        return findings, result.returncode


class GgshieldBackend:
    """Opt-in alternative — requires ggshield binary and GITGUARDIAN_API_KEY."""

    EXPECTED_BINARY = "ggshield"

    def is_available(self) -> bool:
        """Return True if ggshield binary exists and API key is set."""
        has_binary = shutil.which(self.EXPECTED_BINARY) is not None
        has_key = bool(os.environ.get("GITGUARDIAN_API_KEY"))
        return has_binary and has_key

    def version(self) -> str | None:
        """Return ggshield version string, or None if unavailable."""
        if not self.is_available():
            return None
        result = subprocess.run(
            [self.EXPECTED_BINARY, "version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else None

    def scan_path(
        self, path: Path, *, json_output: bool = False
    ) -> tuple[list[SecretFinding], int]:
        """Run ggshield secret scan on the given path.

        Returns (findings, exit_code) where exit_code 0 means clean
        and 1 means policy breaks were found.
        """
        cmd = [
            self.EXPECTED_BINARY,
            "secret",
            "scan",
            "path",
            str(path),
            "--json",
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        findings = _parse_ggshield_json(result.stdout)
        return findings, result.returncode


def get_secrets_backend(scanner: str = "gitleaks") -> SecretsBackend:
    """Factory for secrets backends.

    Parameters
    ----------
    scanner:
        Backend name: ``"gitleaks"`` or ``"ggshield"``.

    Raises
    ------
    ValueError
        If the scanner name is not recognized.
    """
    backends: dict[str, type[SecretsBackend]] = {
        "gitleaks": GitleaksBackend,
        "ggshield": GgshieldBackend,
    }
    cls = backends.get(scanner)
    if cls is None:
        raise ValueError(
            f"Unknown secrets scanner: {scanner!r}. "
            f"Supported: {', '.join(sorted(backends))}"
        )
    return cls()


# ── Private parsers ─────────────────────────────────────────────────────


def _parse_gitleaks_json(raw: str) -> list[SecretFinding]:
    """Parse gitleaks JSON report into SecretFinding list."""
    if not raw or not raw.strip():
        return []
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(entries, list):
        return []
    return [
        SecretFinding(
            file=entry.get("File", ""),
            line=entry.get("StartLine", 0),
            rule_id=entry.get("RuleID", ""),
            description=entry.get("Description", ""),
            match=entry.get("Match", ""),
        )
        for entry in entries
    ]


def _parse_ggshield_json(raw: str) -> list[SecretFinding]:
    """Parse ggshield JSON report into SecretFinding list."""
    if not raw or not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    findings: list[SecretFinding] = []
    for scan in data.get("scans", []):
        file_id = scan.get("id", "")
        for policy_break in scan.get("policy_breaks", []):
            break_type = policy_break.get("break_type", "")
            for match_entry in policy_break.get("matches", []):
                findings.append(
                    SecretFinding(
                        file=file_id,
                        line=match_entry.get("line_start", 0),
                        rule_id=break_type,
                        description=f"{break_type}: {match_entry.get('type', '')}",
                        match=match_entry.get("match", ""),
                    )
                )
    return findings
