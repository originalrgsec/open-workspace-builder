"""S010 — Layer 2: Pattern-based content scanning."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from open_workspace_builder.security.scanner import ScanFlag

_DEFAULT_PATTERNS_PATH = Path(__file__).parent / "data" / "patterns.yaml"


@dataclass(frozen=True)
class PatternRule:
    """A single pattern rule loaded from YAML."""

    id: str
    category: str
    pattern: str  # regex
    severity: str
    description: str
    false_positive_hint: str


def load_patterns(patterns_path: Path | None = None) -> list[PatternRule]:
    """Load pattern rules from YAML file."""
    path = patterns_path or _DEFAULT_PATTERNS_PATH

    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError(
            "PyYAML is required for pattern scanning. Install with: pip install pyyaml"
        ) from exc

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    categories = raw.get("categories", {})

    rules: list[PatternRule] = []
    for cat_name, cat_data in categories.items():
        for p in cat_data.get("patterns", []):
            rules.append(PatternRule(
                id=p["id"],
                category=cat_name,
                pattern=p["pattern"],
                severity=p["severity"],
                description=p["description"],
                false_positive_hint=p.get("false_positive_hint", ""),
            ))
    return rules


def check_patterns(path: Path, patterns: list[PatternRule]) -> list[ScanFlag]:
    """Match file content line-by-line against all patterns, return flags."""
    flags: list[ScanFlag] = []
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return flags

    lines = content.splitlines()
    compiled: list[tuple[PatternRule, re.Pattern[str]]] = []
    for rule in patterns:
        try:
            compiled.append((rule, re.compile(rule.pattern)))
        except re.error:
            continue  # Skip invalid patterns.

    for line_num, line in enumerate(lines, start=1):
        for rule, regex in compiled:
            match = regex.search(line)
            if match:
                flags.append(ScanFlag(
                    category=rule.category,
                    severity=rule.severity,
                    evidence=f"Line {line_num}: {match.group()!r} (pattern: {rule.id})",
                    description=rule.description,
                    line_number=line_num,
                    layer=2,
                ))

    return flags
