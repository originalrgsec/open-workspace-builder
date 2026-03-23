"""Tests for engine/differ.py — workspace diff functionality."""

from __future__ import annotations

from pathlib import Path

import pytest

from open_workspace_builder.config import Config, load_config
from open_workspace_builder.engine.builder import WorkspaceBuilder
from open_workspace_builder.engine.differ import (
    DiffReport,
    FileGap,
    diff_report_to_dict,
    diff_workspace,
    format_diff_report,
)


@pytest.fixture
def content_root() -> Path:
    """Return the project content root (repo root with content/ and vendor/)."""
    root = Path(__file__).resolve().parent.parent
    assert (root / "content").is_dir(), f"content/ not found at {root}"
    assert (root / "vendor").is_dir(), f"vendor/ not found at {root}"
    return root


@pytest.fixture
def default_config() -> Config:
    """Return a default config."""
    return load_config()


@pytest.fixture
def minimal_workspace(tmp_path: Path, content_root: Path, default_config: Config) -> Path:
    """Build a valid workspace using owb init — represents zero drift."""
    ws = tmp_path / "minimal"
    builder = WorkspaceBuilder(default_config, content_root, dry_run=False)
    builder.build(ws)
    return ws


@pytest.fixture
def drifted_workspace(tmp_path: Path, content_root: Path, default_config: Config) -> Path:
    """Build a workspace with known drift.

    Creates:
    - 2 missing files (deleted from the built workspace)
    - 1 outdated template (content replaced with shorter content)
    - 1 user-modified file (content expanded with user additions)
    - 2 extra user files (not in reference)
    """
    ws = tmp_path / "drifted"
    builder = WorkspaceBuilder(default_config, content_root, dry_run=False)
    builder.build(ws)

    # Collect all files to find valid targets
    all_files = sorted(ws.rglob("*"))
    real_files = [f for f in all_files if f.is_file()]
    assert len(real_files) > 5, f"Expected more than 5 files, got {len(real_files)}"

    # Delete 2 files → "missing" gaps
    deleted_files = real_files[:2]
    for f in deleted_files:
        f.unlink()

    # Replace 1 file with shorter content → "outdated" gap
    outdated_file = real_files[2]
    outdated_file.write_text("outdated content\n", encoding="utf-8")

    # Expand 1 file with user additions → "modified" gap
    modified_file = real_files[3]
    original_content = modified_file.read_text(encoding="utf-8")
    modified_file.write_text(
        original_content + "\n\n## User additions\nCustom section added by user.\n",
        encoding="utf-8",
    )

    # Add 2 extra user files
    (ws / "my-notes.md").write_text("Personal notes\n", encoding="utf-8")
    (ws / "custom-project.md").write_text("Custom project doc\n", encoding="utf-8")

    return ws


class TestDiffMinimalWorkspace:
    """Diff against a clean workspace should show zero actionable gaps."""

    def test_no_actionable_gaps(
        self, minimal_workspace: Path, content_root: Path, default_config: Config
    ) -> None:
        report = diff_workspace(
            minimal_workspace, config=default_config, content_root=content_root
        )
        actionable = [
            g for g in report.gaps if g.category in ("missing", "outdated", "modified")
        ]
        assert len(actionable) == 0

    def test_summary_counts(
        self, minimal_workspace: Path, content_root: Path, default_config: Config
    ) -> None:
        report = diff_workspace(
            minimal_workspace, config=default_config, content_root=content_root
        )
        assert report.summary["missing"] == 0
        assert report.summary["outdated"] == 0
        assert report.summary["modified"] == 0


class TestDiffDriftedWorkspace:
    """Diff against a drifted workspace should correctly categorize all gaps."""

    def test_missing_files_detected(
        self, drifted_workspace: Path, content_root: Path, default_config: Config
    ) -> None:
        report = diff_workspace(
            drifted_workspace, config=default_config, content_root=content_root
        )
        assert report.summary["missing"] == 2

    def test_outdated_files_detected(
        self, drifted_workspace: Path, content_root: Path, default_config: Config
    ) -> None:
        report = diff_workspace(
            drifted_workspace, config=default_config, content_root=content_root
        )
        assert report.summary["outdated"] == 1

    def test_modified_files_detected(
        self, drifted_workspace: Path, content_root: Path, default_config: Config
    ) -> None:
        report = diff_workspace(
            drifted_workspace, config=default_config, content_root=content_root
        )
        assert report.summary["modified"] == 1

    def test_extra_files_detected(
        self, drifted_workspace: Path, content_root: Path, default_config: Config
    ) -> None:
        report = diff_workspace(
            drifted_workspace, config=default_config, content_root=content_root
        )
        assert report.summary["extra"] == 2

    def test_extra_never_recommended_for_deletion(
        self, drifted_workspace: Path, content_root: Path, default_config: Config
    ) -> None:
        report = diff_workspace(
            drifted_workspace, config=default_config, content_root=content_root
        )
        extra_gaps = [g for g in report.gaps if g.category == "extra"]
        for gap in extra_gaps:
            assert "delete" not in gap.recommendation.lower()
            assert "remove" not in gap.recommendation.lower()

    def test_total_gap_count(
        self, drifted_workspace: Path, content_root: Path, default_config: Config
    ) -> None:
        report = diff_workspace(
            drifted_workspace, config=default_config, content_root=content_root
        )
        total = sum(report.summary.values())
        assert total == 6  # 2 missing + 1 outdated + 1 modified + 2 extra

    def test_gap_dataclass_fields(
        self, drifted_workspace: Path, content_root: Path, default_config: Config
    ) -> None:
        report = diff_workspace(
            drifted_workspace, config=default_config, content_root=content_root
        )
        for gap in report.gaps:
            assert isinstance(gap.path, str)
            assert gap.category in ("missing", "outdated", "modified", "extra")
            assert isinstance(gap.recommendation, str)
            if gap.category == "missing":
                assert gap.reference_hash is not None
                assert gap.actual_hash is None
            elif gap.category == "extra":
                assert gap.reference_hash is None
                assert gap.actual_hash is not None
            else:
                assert gap.reference_hash is not None
                assert gap.actual_hash is not None


class TestDiffErrors:
    """Diff with invalid vault path should raise."""

    def test_missing_vault_path(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "does-not-exist"
        with pytest.raises(FileNotFoundError, match="does not exist"):
            diff_workspace(nonexistent)

    def test_file_instead_of_directory(self, tmp_path: Path) -> None:
        file_path = tmp_path / "not-a-dir.txt"
        file_path.write_text("hello", encoding="utf-8")
        with pytest.raises(FileNotFoundError, match="not a directory"):
            diff_workspace(file_path)


class TestDiffReportFormatting:
    """Test report formatting and serialization."""

    def test_format_no_gaps(self) -> None:
        report = DiffReport(
            gaps=(), summary={"missing": 0, "outdated": 0, "modified": 0, "extra": 0}
        )
        text = format_diff_report(report)
        assert "up to date" in text

    def test_format_with_gaps(self) -> None:
        report = DiffReport(
            gaps=(
                FileGap(
                    path="foo.md",
                    category="missing",
                    reference_hash="abc",
                    actual_hash=None,
                    recommendation="Create foo.md",
                ),
            ),
            summary={"missing": 1, "outdated": 0, "modified": 0, "extra": 0},
        )
        text = format_diff_report(report)
        assert "MISSING" in text
        assert "foo.md" in text

    def test_to_dict_roundtrip(self) -> None:
        report = DiffReport(
            gaps=(
                FileGap(
                    path="bar.md",
                    category="extra",
                    reference_hash=None,
                    actual_hash="def",
                    recommendation="No action",
                ),
            ),
            summary={"missing": 0, "outdated": 0, "modified": 0, "extra": 1},
        )
        d = diff_report_to_dict(report)
        assert len(d["gaps"]) == 1
        assert d["gaps"][0]["category"] == "extra"
        assert d["summary"]["extra"] == 1
