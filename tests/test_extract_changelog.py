"""Tests for scripts/extract_changelog.py (AD-17, OWB-S118)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import load_script

extract_changelog = load_script("extract_changelog")


SAMPLE_CHANGELOG = """# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [1.9.0] - 2026-04-18

### Added
- GitHub Releases workflow (OWB-S118).

### Fixed
- Something unrelated.

## [1.8.1] - 2026-04-15

### Security
- Bump cryptography to 46.0.7 (CVE-2026-39892).

## [1.8.0] - 2026-04-11

### Added
- SBOM operational commands.
"""


class TestExtractSection:
    def test_happy_path_returns_body_without_header(self) -> None:
        body = extract_changelog.extract_section(SAMPLE_CHANGELOG, "1.9.0")
        assert "### Added" in body
        assert "GitHub Releases workflow (OWB-S118)." in body
        assert "### Fixed" in body
        assert "## [1.9.0]" not in body
        assert "## [1.8.1]" not in body

    def test_trailing_section_header_excluded(self) -> None:
        body = extract_changelog.extract_section(SAMPLE_CHANGELOG, "1.9.0")
        assert "cryptography" not in body

    def test_intermediate_section_extracted_cleanly(self) -> None:
        body = extract_changelog.extract_section(SAMPLE_CHANGELOG, "1.8.1")
        assert "cryptography" in body
        assert "SBOM operational commands" not in body

    def test_trailing_whitespace_stripped(self) -> None:
        body = extract_changelog.extract_section(SAMPLE_CHANGELOG, "1.8.0")
        assert body.endswith("SBOM operational commands.\n")
        assert not body.endswith("\n\n")

    def test_leading_whitespace_stripped(self) -> None:
        body = extract_changelog.extract_section(SAMPLE_CHANGELOG, "1.9.0")
        assert not body.startswith("\n")
        assert body.startswith("### Added")

    def test_missing_section_raises(self) -> None:
        with pytest.raises(ValueError, match=r"\[9.9.9\] not found"):
            extract_changelog.extract_section(SAMPLE_CHANGELOG, "9.9.9")

    def test_empty_unreleased_section_raises(self) -> None:
        with pytest.raises(ValueError, match=r"\[Unreleased\] is empty"):
            extract_changelog.extract_section(SAMPLE_CHANGELOG, "Unreleased")

    def test_whitespace_only_section_raises(self) -> None:
        changelog = "## [1.9.0] - 2026-04-18\n\n   \n\t\n\n## [1.8.1] - 2026-04-15\n\n- patch\n"
        with pytest.raises(ValueError, match=r"\[1.9.0\] is empty"):
            extract_changelog.extract_section(changelog, "1.9.0")

    def test_prerelease_version_requires_own_section(self) -> None:
        with pytest.raises(ValueError, match=r"\[1.9.0-rc.1\] not found"):
            extract_changelog.extract_section(SAMPLE_CHANGELOG, "1.9.0-rc.1")

    def test_prerelease_section_matches_when_present(self) -> None:
        changelog = SAMPLE_CHANGELOG + "\n## [1.9.0-rc.1] - 2026-04-12\n\n- rehearsal\n"
        body = extract_changelog.extract_section(changelog, "1.9.0-rc.1")
        assert "rehearsal" in body

    def test_pep440_prerelease_section_matches(self) -> None:
        # Canonical PEP 440 form used by Python packaging tools
        changelog = SAMPLE_CHANGELOG + "\n## [1.9.0rc1] - 2026-04-12\n\n- rc rehearsal\n"
        body = extract_changelog.extract_section(changelog, "1.9.0rc1")
        assert "rc rehearsal" in body


class TestMainCli:
    def test_main_happy_path(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(SAMPLE_CHANGELOG, encoding="utf-8")
        rc = extract_changelog.main(["extract_changelog.py", str(changelog), "1.9.0"])
        captured = capsys.readouterr()
        assert rc == 0
        assert "GitHub Releases workflow" in captured.out

    def test_main_missing_section_returns_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(SAMPLE_CHANGELOG, encoding="utf-8")
        rc = extract_changelog.main(["extract_changelog.py", str(changelog), "9.9.9"])
        captured = capsys.readouterr()
        assert rc == 1
        assert "not found" in captured.err

    def test_main_missing_file_returns_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = extract_changelog.main(["extract_changelog.py", str(tmp_path / "nope.md"), "1.9.0"])
        captured = capsys.readouterr()
        assert rc == 1
        assert "not found" in captured.err

    def test_main_wrong_argc_returns_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = extract_changelog.main(["extract_changelog.py"])
        captured = capsys.readouterr()
        assert rc == 1
        assert "usage" in captured.err
