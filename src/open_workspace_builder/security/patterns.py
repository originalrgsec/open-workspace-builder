"""S010 — Layer 2: Pattern-based content scanning."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from open_workspace_builder.security.scanner import ScanFlag

if TYPE_CHECKING:
    from open_workspace_builder.registry.registry import Registry

_DEFAULT_PATTERNS_PATH = Path(__file__).parent / "data" / "patterns.yaml"

# OWB-SEC-006: ReDoS defenses. Both caps are ceilings, not targets:
# normal skill / agent / command content is well under both limits.
# Files or lines over the cap emit a `scan_limit` warning flag rather
# than feeding attacker-controlled content into potentially pathological
# regex patterns. The caps are sized to accept every file currently in
# content/skills/ and vendor/ecc/ with a comfortable margin.
MAX_FILE_BYTES: int = 1024 * 1024  # 1 MiB
MAX_LINE_CHARS: int = 16 * 1024  # 16 KiB


@dataclass(frozen=True)
class PatternRule:
    """A single pattern rule loaded from YAML."""

    id: str
    category: str
    pattern: str  # regex
    severity: str
    description: str
    false_positive_hint: str


def _load_patterns_from_registry(
    registry: Registry,
    active_patterns: tuple[str, ...] = ("owb-default",),
) -> list[PatternRule]:
    """Load pattern rules from registry items matching active_patterns config."""
    items = registry.get_active_items("pattern", active_patterns)
    rules: list[PatternRule] = []
    for item in items:
        # Category name derived from item id (e.g. "owb-self-modification" -> "self_modification").
        # Normalize hyphens to underscores so registry path matches monolithic YAML category names.
        cat_name = (
            item.id.removeprefix("owb-").replace("-", "_")
            if item.id.startswith("owb-")
            else item.id.replace("-", "_")
        )
        for p in item.payload.get("patterns", []):
            rules.append(
                PatternRule(
                    id=p["id"],
                    category=cat_name,
                    pattern=p["pattern"],
                    severity=p["severity"],
                    description=p["description"],
                    false_positive_hint=p.get("false_positive_hint", ""),
                )
            )
    return rules


def load_patterns(
    patterns_path: Path | None = None,
    registry: Registry | None = None,
    active_patterns: tuple[str, ...] = ("owb-default",),
) -> list[PatternRule]:
    """Load pattern rules from registry or YAML file.

    When a registry is provided, patterns are loaded from registry items
    matching active_patterns. Otherwise falls back to the monolithic YAML file.
    """
    if registry is not None:
        return _load_patterns_from_registry(registry, active_patterns)

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
            rules.append(
                PatternRule(
                    id=p["id"],
                    category=cat_name,
                    pattern=p["pattern"],
                    severity=p["severity"],
                    description=p["description"],
                    false_positive_hint=p.get("false_positive_hint", ""),
                )
            )
    return rules


def check_patterns(path: Path, patterns: list[PatternRule]) -> list[ScanFlag]:
    """Match file content line-by-line against all patterns, return flags.

    OWB-SEC-006: two ReDoS defenses apply before any regex runs.

    1. ``MAX_FILE_BYTES`` — files larger than the cap short-circuit
       to a ``scan_limit`` warning. This defuses whole-file
       catastrophic-backtracking attacks regardless of pattern
       quality.
    2. ``MAX_LINE_CHARS`` — any individual line longer than the cap
       is replaced in-flight by a ``scan_limit`` warning. Keeps
       single-giant-line attacks (which bypass the line-by-line
       cadence) bounded.

    Both shapes produce a flag rather than silent truncation so the
    operator knows the scanner did not see full content.
    """
    flags: list[ScanFlag] = []
    try:
        size = path.stat().st_size
    except OSError:
        return flags

    if size > MAX_FILE_BYTES:
        flags.append(
            ScanFlag(
                category="scan_limit",
                severity="warning",
                evidence=f"file size {size} bytes exceeds cap {MAX_FILE_BYTES}",
                description=(
                    "File size exceeds scanner cap; pattern layer skipped "
                    "to prevent ReDoS. Split the file or lower content size."
                ),
                layer=2,
            )
        )
        return flags

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
        if len(line) > MAX_LINE_CHARS:
            flags.append(
                ScanFlag(
                    category="scan_limit",
                    severity="warning",
                    evidence=(
                        f"Line {line_num}: length {len(line)} chars exceeds cap "
                        f"{MAX_LINE_CHARS}; pattern match skipped"
                    ),
                    description=(
                        "Line length exceeds scanner cap; pattern match skipped "
                        "to prevent ReDoS catastrophic backtracking."
                    ),
                    line_number=line_num,
                    layer=2,
                )
            )
            continue
        for rule, regex in compiled:
            match = regex.search(line)
            if match:
                flags.append(
                    ScanFlag(
                        category=rule.category,
                        severity=rule.severity,
                        evidence=f"Line {line_num}: {match.group()!r} (pattern: {rule.id})",
                        description=rule.description,
                        line_number=line_num,
                        layer=2,
                    )
                )

    return flags
