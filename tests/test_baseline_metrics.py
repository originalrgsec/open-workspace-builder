"""Tests for baseline metrics collection (OWB-S049).

TDD: tests written first, then implementation.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from open_workspace_builder.cli import owb
from open_workspace_builder.metrics.baseline import (
    BaselineMetrics,
    ModuleMetric,
    collect_baseline,
    render_baseline_summary,
    write_baseline,
)


# ── Dataclass tests ─────────────────────────────────────────────────────


class TestModuleMetricDataclass:
    """Verify ModuleMetric is frozen and holds expected fields."""

    def test_creation(self) -> None:
        m = ModuleMetric(name="engine", loc=150, path="src/open_workspace_builder/engine")
        assert m.name == "engine"
        assert m.loc == 150
        assert m.path == "src/open_workspace_builder/engine"

    def test_frozen(self) -> None:
        m = ModuleMetric(name="engine", loc=150, path="src/foo")
        with pytest.raises(AttributeError):
            m.name = "changed"  # type: ignore[misc]


class TestBaselineMetricsDataclass:
    """Verify BaselineMetrics is frozen and holds expected fields."""

    def test_creation(self) -> None:
        metrics = BaselineMetrics(
            source_loc=1000,
            test_loc=500,
            test_count=42,
            commit_count=100,
            date_range=("2025-01-01", "2026-04-01"),
            modules=(ModuleMetric(name="core", loc=200, path="src/core"),),
        )
        assert metrics.source_loc == 1000
        assert metrics.test_count == 42
        assert metrics.commit_count == 100
        assert len(metrics.modules) == 1

    def test_frozen(self) -> None:
        metrics = BaselineMetrics(
            source_loc=1000,
            test_loc=500,
            test_count=42,
            commit_count=100,
            date_range=("2025-01-01", "2026-04-01"),
            modules=(),
        )
        with pytest.raises(AttributeError):
            metrics.source_loc = 999  # type: ignore[misc]


# ── Collection tests ─────────────────────────────────────────────────────


class TestCollectBaseline:
    """Test baseline collection against the real OWB repo."""

    def test_collect_baseline_real_repo(self) -> None:
        """Run against the OWB repo itself — it is a git repo with source and tests."""
        repo_root = Path(__file__).resolve().parent.parent
        metrics = collect_baseline(repo_root)

        assert metrics.source_loc > 0
        assert metrics.test_loc > 0
        assert metrics.test_count > 0
        assert metrics.commit_count > 0
        assert len(metrics.date_range) == 2
        assert metrics.date_range[0] <= metrics.date_range[1]
        assert len(metrics.modules) > 0

    def test_collect_baseline_with_tag_range(self) -> None:
        """Mock git subprocess calls to test tag range filtering."""
        repo_root = Path(__file__).resolve().parent.parent
        # Use a mock that simulates a tag range — git log returns fewer commits
        fake_log = "abc1234 commit one\ndef5678 commit two\n"
        # git log outputs newest first
        fake_dates = "2025-07-01T00:00:00+00:00\n2025-06-01T00:00:00+00:00\n"

        with (
            patch("open_workspace_builder.metrics.baseline._git_log_oneline") as mock_log,
            patch("open_workspace_builder.metrics.baseline._git_log_dates") as mock_dates,
        ):
            mock_log.return_value = fake_log
            mock_dates.return_value = fake_dates
            metrics = collect_baseline(repo_root, tag_range="v0.1.0..v0.2.0")

        assert metrics.commit_count == 2
        assert metrics.date_range == ("2025-06-01T00:00:00+00:00", "2025-07-01T00:00:00+00:00")
        # Source/test LOC still come from filesystem, not git
        assert metrics.source_loc > 0


# ── Render tests ─────────────────────────────────────────────────────────


class TestRenderBaselineSummary:
    """Verify markdown rendering of baseline metrics."""

    @pytest.fixture()
    def sample_metrics(self) -> BaselineMetrics:
        return BaselineMetrics(
            source_loc=2000,
            test_loc=800,
            test_count=55,
            commit_count=120,
            date_range=("2025-01-15", "2026-03-30"),
            modules=(
                ModuleMetric(name="engine", loc=500, path="src/engine"),
                ModuleMetric(name="cli", loc=300, path="src/cli"),
            ),
        )

    def test_render_contains_header(self, sample_metrics: BaselineMetrics) -> None:
        md = render_baseline_summary(sample_metrics)
        assert "# Baseline Metrics" in md

    def test_render_contains_loc(self, sample_metrics: BaselineMetrics) -> None:
        md = render_baseline_summary(sample_metrics)
        assert "2,000" in md or "2000" in md
        assert "800" in md

    def test_render_contains_test_count(self, sample_metrics: BaselineMetrics) -> None:
        md = render_baseline_summary(sample_metrics)
        assert "55" in md

    def test_render_contains_commit_count(self, sample_metrics: BaselineMetrics) -> None:
        md = render_baseline_summary(sample_metrics)
        assert "120" in md

    def test_render_contains_date_range(self, sample_metrics: BaselineMetrics) -> None:
        md = render_baseline_summary(sample_metrics)
        assert "2025-01-15" in md
        assert "2026-03-30" in md

    def test_render_contains_module_breakdown(self, sample_metrics: BaselineMetrics) -> None:
        md = render_baseline_summary(sample_metrics)
        assert "engine" in md
        assert "cli" in md


# ── Write tests ──────────────────────────────────────────────────────────


class TestWriteBaseline:
    """Verify file creation in output directory."""

    def test_write_baseline(self, tmp_path: Path) -> None:
        metrics = BaselineMetrics(
            source_loc=100,
            test_loc=50,
            test_count=10,
            commit_count=20,
            date_range=("2025-01-01", "2025-12-31"),
            modules=(ModuleMetric(name="core", loc=100, path="src/core"),),
        )
        paths = write_baseline(metrics, tmp_path)

        assert len(paths) >= 1
        md_path = tmp_path / "metrics" / "baseline-summary.md"
        assert md_path.exists()
        content = md_path.read_text()
        assert "# Baseline Metrics" in content

    def test_write_baseline_creates_json(self, tmp_path: Path) -> None:
        metrics = BaselineMetrics(
            source_loc=100,
            test_loc=50,
            test_count=10,
            commit_count=20,
            date_range=("2025-01-01", "2025-12-31"),
            modules=(),
        )
        write_baseline(metrics, tmp_path)

        json_path = tmp_path / "metrics" / "baseline.json"
        assert json_path.exists()
        data = json.loads(json_path.read_text())
        assert data["source_loc"] == 100
        assert data["test_count"] == 10


# ── CLI tests ────────────────────────────────────────────────────────────


class TestCliBaselineCommand:
    """CLI contract and integration tests for 'owb metrics baseline'."""

    @pytest.fixture()
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_cli_baseline_help(self, runner: CliRunner) -> None:
        result = runner.invoke(owb, ["metrics", "baseline", "--help"])
        assert result.exit_code == 0
        assert "baseline" in result.output.lower()

    def test_cli_baseline_command(self, runner: CliRunner, tmp_path: Path) -> None:
        """Run baseline against the OWB repo with --non-interactive."""
        repo_root = str(Path(__file__).resolve().parent.parent)
        result = runner.invoke(
            owb,
            [
                "metrics",
                "baseline",
                repo_root,
                "--output-dir",
                str(tmp_path),
                "--non-interactive",
            ],
        )
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert (tmp_path / "metrics" / "baseline-summary.md").exists()

    def test_cli_baseline_json(self, runner: CliRunner) -> None:
        """Verify --json outputs parseable JSON."""
        repo_root = str(Path(__file__).resolve().parent.parent)
        result = runner.invoke(
            owb,
            [
                "metrics",
                "baseline",
                repo_root,
                "--json",
                "--non-interactive",
            ],
        )
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        data = json.loads(result.output)
        assert "source_loc" in data
        assert "test_loc" in data
        assert "test_count" in data
        assert "commit_count" in data
