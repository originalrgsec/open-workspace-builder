"""OWB-S107a — normalization algorithm tests.

The norm1 algorithm must produce stable content hashes across trivial formatting
changes so that `owb sbom verify` does not scream drift for cosmetic edits.

Rules:
1. Strip trailing whitespace from every line.
2. Normalize line endings to LF.
3. Strip the `updated:` frontmatter field (templates bump it on every save).
4. Hash normalized UTF-8 bytes with SHA-256.
5. Version the algorithm in the hash string: `sha256-norm1:<hex>`.
"""

from __future__ import annotations

import pytest

from open_workspace_builder.sbom.normalize import (
    NORM_VERSION,
    compute_hash,
    normalize_content,
)


class TestNormVersionTag:
    """The algorithm version must be embedded in every hash string."""

    def test_hash_string_starts_with_sha256_norm1(self) -> None:
        result = compute_hash("hello world")
        assert result.startswith("sha256-norm1:")

    def test_norm_version_constant_is_norm1(self) -> None:
        assert NORM_VERSION == "norm1"

    def test_hash_hex_portion_is_64_chars(self) -> None:
        result = compute_hash("hello world")
        _, hex_part = result.split(":", 1)
        assert len(hex_part) == 64
        int(hex_part, 16)  # must be valid hex


class TestTrailingWhitespace:
    """Rule 1: trailing whitespace stripped per line."""

    def test_trailing_spaces_stripped(self) -> None:
        assert normalize_content("hello   \nworld") == "hello\nworld"

    def test_trailing_tabs_stripped(self) -> None:
        assert normalize_content("hello\t\t\nworld") == "hello\nworld"

    def test_mixed_trailing_whitespace_stripped(self) -> None:
        assert normalize_content("hello \t \nworld  ") == "hello\nworld"

    def test_leading_whitespace_preserved(self) -> None:
        assert normalize_content("  hello\n    world") == "  hello\n    world"

    def test_hash_stable_across_trailing_whitespace(self) -> None:
        h1 = compute_hash("hello\nworld")
        h2 = compute_hash("hello   \nworld  ")
        assert h1 == h2


class TestLineEndings:
    """Rule 2: all line endings normalized to LF."""

    def test_crlf_normalized_to_lf(self) -> None:
        assert normalize_content("a\r\nb\r\nc") == "a\nb\nc"

    def test_cr_normalized_to_lf(self) -> None:
        assert normalize_content("a\rb\rc") == "a\nb\nc"

    def test_mixed_endings_normalized(self) -> None:
        assert normalize_content("a\r\nb\nc\rd") == "a\nb\nc\nd"

    def test_hash_stable_across_line_endings(self) -> None:
        h_lf = compute_hash("a\nb\nc")
        h_crlf = compute_hash("a\r\nb\r\nc")
        h_cr = compute_hash("a\rb\rc")
        assert h_lf == h_crlf == h_cr


class TestUpdatedFrontmatterStripping:
    """Rule 3: the `updated:` frontmatter field is stripped before hashing.

    Templates bump `updated:` on every save. Without stripping, every
    re-save of a skill would look like content drift.
    """

    def test_updated_line_stripped_between_frontmatter_delimiters(self) -> None:
        content = "---\nname: xlsx\nupdated: 2026-04-10\nversion: 1.0\n---\n# Body\n"
        normalized = normalize_content(content)
        assert "updated:" not in normalized
        assert "name: xlsx" in normalized
        assert "version: 1.0" in normalized
        assert "# Body" in normalized

    def test_hash_stable_when_updated_field_changes(self) -> None:
        base = "---\nname: xlsx\nupdated: {date}\nversion: 1.0\n---\n# Body\n"
        h1 = compute_hash(base.format(date="2026-04-10"))
        h2 = compute_hash(base.format(date="2099-01-01"))
        assert h1 == h2

    def test_updated_field_outside_frontmatter_is_preserved(self) -> None:
        content = "---\nname: xlsx\n---\n# Body\nupdated: this is body text, not frontmatter\n"
        normalized = normalize_content(content)
        assert "updated: this is body text" in normalized

    def test_no_frontmatter_content_unchanged(self) -> None:
        content = "plain content\nno frontmatter\n"
        assert normalize_content(content) == "plain content\nno frontmatter"

    def test_frontmatter_without_updated_preserved(self) -> None:
        content = "---\nname: xlsx\nversion: 1.0\n---\nbody\n"
        normalized = normalize_content(content)
        assert "name: xlsx" in normalized
        assert "version: 1.0" in normalized


class TestHashDeterminism:
    """Rules 4 and 5 composed: hash is deterministic and stable across all three rules."""

    def test_identical_content_same_hash(self) -> None:
        assert compute_hash("abc") == compute_hash("abc")

    def test_different_content_different_hash(self) -> None:
        assert compute_hash("abc") != compute_hash("abd")

    def test_combined_stability(self) -> None:
        """Whitespace + line endings + updated field all change; hash stable."""
        original = "---\nname: xlsx\nupdated: 2026-04-10\n---\n# Body\n"
        messy = "---\r\nname: xlsx   \r\nupdated: 2099-12-31\r\n---\r\n# Body\t\r\n"
        assert compute_hash(original) == compute_hash(messy)


class TestEdgeCases:
    """Defensive cases."""

    def test_empty_string(self) -> None:
        result = normalize_content("")
        assert result == ""
        # Empty string still produces a valid norm1 hash.
        h = compute_hash("")
        assert h.startswith("sha256-norm1:")

    def test_single_newline(self) -> None:
        assert normalize_content("\n") == ""

    def test_unicode_content_preserved(self) -> None:
        content = "日本語 ✓\n"
        normalized = normalize_content(content)
        assert "日本語" in normalized
        assert "✓" in normalized

    def test_bytes_input_accepted(self) -> None:
        """compute_hash should accept both str and bytes for convenience."""
        h_str = compute_hash("hello")
        h_bytes = compute_hash(b"hello")
        assert h_str == h_bytes

    @pytest.mark.parametrize(
        ("a", "b"),
        [
            ("x\ny", "x\ny\n"),  # trailing newline difference
            ("x  \ny", "x\ny"),  # trailing spaces
            ("x\r\ny", "x\ny"),  # CRLF vs LF
        ],
    )
    def test_hash_stable_parametrized(self, a: str, b: str) -> None:
        assert compute_hash(a) == compute_hash(b)
