"""S012 — Scanner orchestrator: dataclasses, verdict logic, file/directory scanning."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_workspace_builder.config import SecurityConfig
    from open_workspace_builder.llm.backend import ModelBackend


@dataclass(frozen=True)
class ScanFlag:
    """A single finding from any scan layer."""

    category: str
    severity: str  # "info", "warning", "critical"
    evidence: str
    description: str
    line_number: int | None = None
    layer: int = 1


@dataclass(frozen=True)
class ScanVerdict:
    """Verdict for a single file."""

    file_path: str
    verdict: str  # "clean", "flagged", "malicious", "error"
    flags: tuple[ScanFlag, ...] = ()


@dataclass(frozen=True)
class ScanReport:
    """Aggregated report for a directory scan."""

    directory: str
    verdicts: tuple[ScanVerdict, ...] = ()
    summary: dict[str, int] = field(default_factory=dict)


def _compute_verdict(flags: tuple[ScanFlag, ...]) -> str:
    """Derive verdict from flags: critical→malicious, warning→flagged, else clean."""
    severities = {f.severity for f in flags}
    if "critical" in severities:
        return "malicious"
    if "warning" in severities:
        return "flagged"
    return "clean"


class Scanner:
    """Three-layer content security scanner."""

    def __init__(
        self,
        layers: tuple[int, ...] | None = None,
        backend: ModelBackend | None = None,
        patterns_path: Path | None = None,
        security_config: SecurityConfig | None = None,
    ) -> None:
        from open_workspace_builder.config import SecurityConfig as _SC

        self._security_config = security_config or _SC()
        # Explicit layers arg overrides config default.
        self._layers = layers if layers is not None else self._security_config.scanner_layers
        self._backend = backend
        self._patterns_path = patterns_path
        self._loaded_patterns: list | None = None

    def _get_patterns(self) -> list:
        """Lazy-load patterns for Layer 2."""
        if self._loaded_patterns is None:
            from open_workspace_builder.security.patterns import load_patterns

            self._loaded_patterns = load_patterns(self._patterns_path)
        return self._loaded_patterns

    def scan_file(self, path: Path) -> ScanVerdict:
        """Scan a single file through configured layers, return verdict."""
        all_flags: list[ScanFlag] = []

        if 1 in self._layers:
            from open_workspace_builder.security.structural import check_structural

            all_flags.extend(check_structural(path))

        if 2 in self._layers:
            from open_workspace_builder.security.patterns import check_patterns

            all_flags.extend(check_patterns(path, self._get_patterns()))

        if 3 in self._layers and self._backend is not None:
            from open_workspace_builder.security.semantic import analyze_content

            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                result = analyze_content(
                    content=content,
                    file_name=path.name,
                    backend=self._backend,
                )
                all_flags.extend(result)
            except Exception:
                all_flags.append(
                    ScanFlag(
                        category="semantic_error",
                        severity="warning",
                        evidence="Layer 3 analysis failed",
                        description="Semantic analysis encountered an error",
                        layer=3,
                    )
                )

        flags_tuple = tuple(all_flags)
        verdict = _compute_verdict(flags_tuple)
        return ScanVerdict(
            file_path=str(path),
            verdict=verdict,
            flags=flags_tuple,
        )

    def scan_directory(self, dir_path: Path, glob_pattern: str = "*.md") -> ScanReport:
        """Scan all matching files in a directory, return aggregated report."""
        verdicts: list[ScanVerdict] = []
        for file_path in sorted(dir_path.glob(glob_pattern)):
            if file_path.is_file():
                verdicts.append(self.scan_file(file_path))

        summary: dict[str, int] = {"clean": 0, "flagged": 0, "malicious": 0, "error": 0}
        for v in verdicts:
            summary[v.verdict] = summary.get(v.verdict, 0) + 1

        return ScanReport(
            directory=str(dir_path),
            verdicts=tuple(verdicts),
            summary=summary,
        )
