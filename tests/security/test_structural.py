"""Tests for S009 — Layer 1 structural checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from open_workspace_builder.security.structural import (
    check_encoding,
    check_file_size,
    check_file_type,
    check_structural,
)


class TestCheckFileType:
    """Tests for check_file_type."""

    def test_markdown_file_no_flags(self, tmp_path: Path) -> None:
        f = tmp_path / "good.md"
        f.write_text("# Hello", encoding="utf-8")
        assert check_file_type(f) == []

    def test_binary_extension_flagged(self, tmp_path: Path) -> None:
        f = tmp_path / "payload.exe"
        f.write_bytes(b"\x00")
        flags = check_file_type(f)
        assert len(flags) == 1
        assert flags[0].severity == "critical"
        assert flags[0].category == "structural"

    def test_non_markdown_info(self, tmp_path: Path) -> None:
        f = tmp_path / "data.json"
        f.write_text("{}", encoding="utf-8")
        flags = check_file_type(f)
        assert len(flags) == 1
        assert flags[0].severity == "info"

    def test_symlink_flagged(self, tmp_path: Path) -> None:
        target = tmp_path / "real.md"
        target.write_text("# Real", encoding="utf-8")
        link = tmp_path / "link.md"
        link.symlink_to(target)
        flags = check_file_type(link)
        assert any(f.severity == "warning" and "symlink" in f.description.lower() for f in flags)

    @pytest.mark.parametrize("ext", [".sh", ".bat", ".dll", ".pyc"])
    def test_various_binary_extensions(self, tmp_path: Path, ext: str) -> None:
        f = tmp_path / f"file{ext}"
        f.write_bytes(b"\x00")
        flags = check_file_type(f)
        assert any(f.severity == "critical" for f in flags)


class TestCheckFileSize:
    """Tests for check_file_size."""

    def test_small_file_no_flags(self, tmp_path: Path) -> None:
        f = tmp_path / "small.md"
        f.write_text("hello", encoding="utf-8")
        assert check_file_size(f) == []

    def test_oversized_file_flagged(self, tmp_path: Path) -> None:
        f = tmp_path / "big.md"
        f.write_text("x" * (600 * 1024), encoding="utf-8")
        flags = check_file_size(f, max_kb=500)
        assert len(flags) == 1
        assert flags[0].severity == "warning"

    def test_custom_limit(self, tmp_path: Path) -> None:
        f = tmp_path / "medium.md"
        f.write_text("x" * 2048, encoding="utf-8")
        assert check_file_size(f, max_kb=1) != []
        assert check_file_size(f, max_kb=10) == []

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        f = tmp_path / "gone.md"
        flags = check_file_size(f)
        assert len(flags) == 1
        assert flags[0].severity == "warning"


class TestCheckEncoding:
    """Tests for check_encoding."""

    def test_clean_file_no_flags(self, tmp_path: Path) -> None:
        f = tmp_path / "clean.md"
        f.write_text("# Normal markdown content\n\nAll good here.", encoding="utf-8")
        assert check_encoding(f) == []

    def test_zero_width_space_detected(self, tmp_path: Path) -> None:
        f = tmp_path / "zwsp.md"
        f.write_text("hello\u200bworld", encoding="utf-8")
        flags = check_encoding(f)
        assert any("U+200B" in fl.evidence for fl in flags)

    def test_zero_width_joiner_detected(self, tmp_path: Path) -> None:
        f = tmp_path / "zwj.md"
        f.write_text("test\u200dtext", encoding="utf-8")
        flags = check_encoding(f)
        assert any("U+200D" in fl.evidence for fl in flags)

    def test_bom_detected(self, tmp_path: Path) -> None:
        f = tmp_path / "bom.md"
        f.write_text("content with \ufeff BOM", encoding="utf-8")
        flags = check_encoding(f)
        assert any("U+FEFF" in fl.evidence for fl in flags)

    def test_rtl_override_critical(self, tmp_path: Path) -> None:
        f = tmp_path / "rtl.md"
        f.write_text("normal \u202e reversed", encoding="utf-8")
        flags = check_encoding(f)
        rtl_flags = [fl for fl in flags if "RTL" in fl.description]
        assert len(rtl_flags) >= 1
        assert rtl_flags[0].severity == "critical"

    def test_line_numbers_reported(self, tmp_path: Path) -> None:
        f = tmp_path / "lines.md"
        f.write_text("line 1\nline 2\nline \u200b three\n", encoding="utf-8")
        flags = check_encoding(f)
        assert any(fl.line_number == 3 for fl in flags)

    def test_multiple_invisible_chars(self, tmp_path: Path) -> None:
        f = tmp_path / "multi.md"
        f.write_text("a\u200bb\u200cc\u200dd", encoding="utf-8")
        flags = check_encoding(f)
        assert len(flags) >= 3

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        f = tmp_path / "gone.md"
        flags = check_encoding(f)
        assert len(flags) == 1
        assert flags[0].severity == "warning"


class TestCheckStructural:
    """Tests for the combined check_structural function."""

    def test_clean_markdown_no_flags(self, tmp_path: Path) -> None:
        f = tmp_path / "ok.md"
        f.write_text("# Clean doc\n\nNothing wrong here.", encoding="utf-8")
        flags = check_structural(f)
        assert flags == []

    def test_combines_all_checks(self, tmp_path: Path) -> None:
        f = tmp_path / "payload.exe"
        # Binary extension + oversized + invisible char
        content = "x" * (600 * 1024) + "\u200b"
        f.write_text(content, encoding="utf-8")
        flags = check_structural(f)
        categories = {fl.category for fl in flags}
        assert "structural" in categories
        assert "encoding" in categories
