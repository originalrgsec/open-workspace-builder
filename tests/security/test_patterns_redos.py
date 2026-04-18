"""Tests for OWB-SEC-006: ReDoS defenses in the scanner pattern layer.

The existing scanner (``security/patterns.check_patterns``) already
iterates line-by-line, which caps per-match input implicitly. This
story adds explicit defenses for two remaining attack shapes:

1. Enormous single-line files (single 10 MiB line bypasses the
   line-by-line cadence).
2. Enormous files overall (total read swamps the scanner before any
   regex runs).

Both shapes now produce a ScanFlag warning rather than a silent hang
or timeout. A per-pattern timeout is deliberately out of scope — the
input-length caps neutralise the practical attack, and Python's
signal-based timeouts are Unix-only and not thread-safe.
"""

from __future__ import annotations

from pathlib import Path


from open_workspace_builder.security.patterns import (
    MAX_FILE_BYTES,
    MAX_LINE_CHARS,
    PatternRule,
    check_patterns,
)


def _rule(pattern: str, rule_id: str = "test-001") -> PatternRule:
    return PatternRule(
        id=rule_id,
        category="test",
        pattern=pattern,
        severity="warning",
        description="Test pattern",
        false_positive_hint="",
    )


class TestMaxLineChars:
    """AC-3: Per-line cap defuses single-giant-line ReDoS."""

    def test_normal_line_processed(self, tmp_path: Path) -> None:
        f = tmp_path / "normal.md"
        f.write_text("hello\nbackdoor\nworld\n", encoding="utf-8")
        flags = check_patterns(f, [_rule(r"\bbackdoor\b")])
        assert any("backdoor" in flag.evidence for flag in flags)

    def test_oversized_line_skipped_with_warning(self, tmp_path: Path) -> None:
        """A line over MAX_LINE_CHARS must not feed into regex.search."""
        f = tmp_path / "giant-line.md"
        giant = "a" * (MAX_LINE_CHARS + 100)
        f.write_text(f"{giant}\n", encoding="utf-8")
        flags = check_patterns(f, [_rule(r"(a+)+$")])  # classic evil regex
        # The evil regex must never have seen this line — assert no
        # pattern flag was produced, but a scan-warning flag was.
        assert not any(flag.category == "test" for flag in flags)
        assert any(flag.category == "scan_limit" and flag.severity == "warning" for flag in flags)

    def test_short_lines_in_big_file_still_scanned(self, tmp_path: Path) -> None:
        """A file with many short lines must still be scanned per-line."""
        f = tmp_path / "many-short.md"
        f.write_text("\n".join(["clean"] * 1000 + ["backdoor"]), encoding="utf-8")
        flags = check_patterns(f, [_rule(r"\bbackdoor\b")])
        assert any("backdoor" in flag.evidence for flag in flags)


class TestMaxFileBytes:
    """AC-3: Total-file-size cap defuses whole-file ReDoS."""

    def test_oversized_file_short_circuits(self, tmp_path: Path) -> None:
        f = tmp_path / "huge.md"
        f.write_text("x" * (MAX_FILE_BYTES + 1), encoding="utf-8")
        flags = check_patterns(f, [_rule(r"\bbackdoor\b")])
        # No pattern flags because scanner never reached pattern eval.
        assert not any(flag.category == "test" for flag in flags)
        # Scan-warning flag explicitly produced.
        assert any(
            flag.category == "scan_limit" and "file size" in flag.description.lower()
            for flag in flags
        )

    def test_at_cap_file_still_scanned(self, tmp_path: Path) -> None:
        f = tmp_path / "at-cap.md"
        f.write_text(("x" * (MAX_FILE_BYTES - 20)) + "\nbackdoor\n", encoding="utf-8")
        flags = check_patterns(f, [_rule(r"\bbackdoor\b")])
        assert any("backdoor" in flag.evidence for flag in flags)


class TestEvilRegexProtection:
    """AC-5: Known-bad inputs must not hang the scanner.

    This is a property test — the existing `(a+)+` evil regex is
    defused by the per-line cap above, but we assert the combination
    end-to-end here so a future refactor that removes the per-line
    cap cannot silently reintroduce the vulnerability.
    """

    def test_evil_regex_defused_by_line_cap(self, tmp_path: Path) -> None:
        import time

        f = tmp_path / "boom.md"
        f.write_text("a" * (MAX_LINE_CHARS + 1) + "\n", encoding="utf-8")
        start = time.perf_counter()
        check_patterns(f, [_rule(r"(a+)+$", "evil-001")])
        elapsed = time.perf_counter() - start
        # Must finish well under a second. A missing cap would take
        # many seconds (or hang indefinitely) on this input.
        assert elapsed < 1.0, f"scan took {elapsed:.3f}s, ReDoS not defused"


class TestCapsAreDocumented:
    """AC-6: Make the caps visible and auditable."""

    def test_line_cap_is_positive_integer(self) -> None:
        assert isinstance(MAX_LINE_CHARS, int)
        assert MAX_LINE_CHARS > 0

    def test_file_cap_is_positive_integer(self) -> None:
        assert isinstance(MAX_FILE_BYTES, int)
        assert MAX_FILE_BYTES > 0

    def test_file_cap_exceeds_line_cap(self) -> None:
        """File cap must be larger than line cap or the line cap is
        unreachable. Sanity check for future tuning."""
        assert MAX_FILE_BYTES > MAX_LINE_CHARS
