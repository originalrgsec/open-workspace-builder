"""S036 — Repo-level security audit for upstream content sources."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_workspace_builder.security.scanner import Scanner
    from open_workspace_builder.sources.discovery import DiscoveredFile


class AuditVerdict(Enum):
    """Overall verdict for a repo audit."""

    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"


@dataclass(frozen=True)
class AuditFinding:
    """A single finding from a repo audit."""

    file_path: str
    risk_type: str
    severity: AuditVerdict
    description: str


@dataclass(frozen=True)
class RepoAuditResult:
    """Aggregated result of a repo-level audit."""

    source_name: str
    verdict: AuditVerdict
    findings: tuple[AuditFinding, ...]
    audited_at: str


_HOST_MODIFY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bos\.system\s*\("),
    re.compile(r"\bsubprocess\b"),
    re.compile(r"\bos\.exec"),
    re.compile(r"\bshutil\.rmtree\s*\("),
    re.compile(r"\bos\.remove\s*\("),
    re.compile(r"\bos\.environ\b"),
)

_EVENT_TRIGGER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bon_install\b"),
    re.compile(r"\bpost_activate\b"),
    re.compile(r"\bpre_install\b"),
    re.compile(r"\bpost_install\b"),
    re.compile(r"\bon_load\b"),
    re.compile(r"\bon_enable\b"),
)

_SAFE_MODULES = (
    "typing",
    "dataclasses",
    "enum",
    "pathlib",
    "re",
    "os",
    "sys",
    "json",
    "collections",
    "functools",
    "itertools",
    "abc",
    "textwrap",
    "datetime",
    "hashlib",
    "math",
    "string",
)
_SAFE_RE = "|".join(_SAFE_MODULES)

_CROSS_IMPORT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(rf"^\s*import\s+(?!{_SAFE_RE})\w+", re.MULTILINE),
    re.compile(rf"^\s*from\s+(?!\.(?:\s|$))(?!{_SAFE_RE})\w+\s+import", re.MULTILINE),
)


class RepoAuditor:
    """Repo-level security auditor that catches cross-file risks."""

    def __init__(self, scanner: Scanner) -> None:
        self._scanner = scanner

    def audit(
        self,
        source_name: str,
        repo_path: str,
        discovered_files: list[DiscoveredFile],
    ) -> RepoAuditResult:
        """Run repo-level audit checks on discovered files."""
        root = Path(repo_path)
        findings: list[AuditFinding] = []
        findings.extend(_check_hooks_directories(root))
        findings.extend(_check_setup_scripts(root))
        findings.extend(_check_event_triggers(discovered_files))
        findings.extend(_check_cross_imports(discovered_files))
        verdict = _compute_verdict(findings)
        return RepoAuditResult(
            source_name=source_name,
            verdict=verdict,
            findings=tuple(findings),
            audited_at=datetime.now(timezone.utc).isoformat(),
        )


def _compute_verdict(findings: list[AuditFinding]) -> AuditVerdict:
    """Derive overall verdict: BLOCK if any BLOCK, WARN if any WARN, else PASS."""
    severities = {f.severity for f in findings}
    if AuditVerdict.BLOCK in severities:
        return AuditVerdict.BLOCK
    if AuditVerdict.WARN in severities:
        return AuditVerdict.WARN
    return AuditVerdict.PASS


def _check_hooks_directories(root: Path) -> list[AuditFinding]:
    """Check for hooks/ directories containing executable scripts."""
    findings: list[AuditFinding] = []
    for hooks_dir in root.rglob("hooks"):
        if not hooks_dir.is_dir():
            continue
        for child in hooks_dir.iterdir():
            if child.is_file():
                findings.append(
                    AuditFinding(
                        file_path=str(child.relative_to(root)),
                        risk_type="hooks_executable",
                        severity=AuditVerdict.BLOCK,
                        description=f"Executable script in hooks/ directory: {child.name}",
                    )
                )
    return findings


def _check_setup_scripts(root: Path) -> list[AuditFinding]:
    """Check for init/setup scripts that modify the host environment."""
    findings: list[AuditFinding] = []
    setup_names = ("setup.py", "setup.cfg", "install.py", "install.sh", "configure.sh")
    for script_name in setup_names:
        for script_path in root.rglob(script_name):
            if not script_path.is_file():
                continue
            try:
                content = script_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for pattern in _HOST_MODIFY_PATTERNS:
                match = pattern.search(content)
                if match:
                    findings.append(
                        AuditFinding(
                            file_path=str(script_path.relative_to(root)),
                            risk_type="host_modification",
                            severity=AuditVerdict.BLOCK,
                            description=(
                                f"Setup script contains host-modifying code: "
                                f"{match.group(0).strip()}"
                            ),
                        )
                    )
                    break
    return findings


def _check_event_triggers(discovered_files: list[DiscoveredFile]) -> list[AuditFinding]:
    """Check for event trigger patterns in discovered files."""
    findings: list[AuditFinding] = []
    for df in discovered_files:
        try:
            content = Path(df.absolute_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for pattern in _EVENT_TRIGGER_PATTERNS:
            match = pattern.search(content)
            if match:
                findings.append(
                    AuditFinding(
                        file_path=df.relative_path,
                        risk_type="event_trigger",
                        severity=AuditVerdict.WARN,
                        description=f"Event trigger pattern found: {match.group(0).strip()}",
                    )
                )
                break
    return findings


def _check_cross_imports(discovered_files: list[DiscoveredFile]) -> list[AuditFinding]:
    """Check for cross-file import chains pulling in non-skill code."""
    findings: list[AuditFinding] = []
    for df in discovered_files:
        if not df.relative_path.endswith(".py"):
            continue
        try:
            content = Path(df.absolute_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for pattern in _CROSS_IMPORT_PATTERNS:
            match = pattern.search(content)
            if match:
                findings.append(
                    AuditFinding(
                        file_path=df.relative_path,
                        risk_type="cross_import",
                        severity=AuditVerdict.WARN,
                        description=f"Non-skill import detected: {match.group(0).strip()}",
                    )
                )
                break
    return findings
