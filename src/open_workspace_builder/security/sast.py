"""SAST scanning via Semgrep CLI (OWB-S056).

Shells out to the ``semgrep`` CLI — never imports it as a library.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SastFinding:
    """A single SAST finding from Semgrep."""

    rule_id: str
    severity: str  # ERROR, WARNING, INFO
    message: str
    file: str
    line: int
    code: str


@dataclass(frozen=True)
class SastReport:
    """Aggregated Semgrep results."""

    findings: tuple[SastFinding, ...]
    errors: tuple[str, ...]
    rules_run: int


def run_semgrep(
    target: Path,
    config: str = "auto",
    sarif: bool = False,
    timeout: int = 300,
) -> SastReport | str:
    """Run Semgrep against *target* path.

    Parameters
    ----------
    target:
        File or directory to scan.
    config:
        Semgrep config string.  ``"auto"`` for recommended rules,
        ``"p/python"`` for Python-specific, ``"p/owasp-top-ten"``, or a
        local file path.
    sarif:
        When *True*, return raw SARIF JSON string instead of
        :class:`SastReport`.
    timeout:
        Maximum seconds for the semgrep process.

    Returns
    -------
    SastReport | str
        Parsed report, or raw SARIF string when *sarif* is True.

    Raises
    ------
    ImportError
        If the ``semgrep`` CLI is not installed.
    RuntimeError
        If the semgrep process times out.
    """
    fmt_flag = "--sarif" if sarif else "--json"
    cmd = [
        "semgrep",
        "--config",
        config,
        fmt_flag,
        str(target),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        raise ImportError(
            "semgrep is not installed. Install it with: pip install semgrep"
        ) from None
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"semgrep timed out after {timeout}s"
        ) from exc

    if sarif:
        return result.stdout

    raw = json.loads(result.stdout) if result.stdout else {}
    return _parse_semgrep_json(raw)


def _parse_semgrep_json(raw: dict) -> SastReport:
    """Parse ``semgrep --json`` output into :class:`SastReport`."""
    findings: list[SastFinding] = []
    for r in raw.get("results", []):
        extra = r.get("extra", {})
        severity = extra.get("severity", "INFO").upper()
        lines = extra.get("lines", "").strip()
        findings.append(
            SastFinding(
                rule_id=r.get("check_id", "unknown"),
                severity=severity,
                message=extra.get("message", ""),
                file=r.get("path", ""),
                line=r.get("start", {}).get("line", 0),
                code=lines,
            )
        )

    errors: list[str] = []
    for e in raw.get("errors", []):
        msg = e.get("message", "") or e.get("long_msg", "") or str(e)
        errors.append(msg)

    rules_run = len(raw.get("paths", {}).get("scanned", []))

    return SastReport(
        findings=tuple(findings),
        errors=tuple(errors),
        rules_run=rules_run,
    )
