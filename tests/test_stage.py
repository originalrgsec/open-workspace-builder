"""Tests for stage assessment and promotion logic."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from open_workspace_builder.config import Config, StageConfig
from open_workspace_builder.stage import (
    CriterionResult,
    StageAssessment,
    StageEvaluator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_vault(tmp_path: Path) -> Path:
    """Create a minimal vault directory structure."""
    vault = tmp_path / "Obsidian"
    vault.mkdir()
    return vault


def _write_vault_meta(vault: Path, stage: int = 0) -> None:
    """Write a vault-meta.json with the given stage."""
    meta = {"version": "0.8.2", "stage": stage}
    (vault / "vault-meta.json").write_text(
        json.dumps(meta), encoding="utf-8"
    )


def _populate_stage0_exit_criteria(vault: Path) -> None:
    """Populate a vault so it passes all Stage 0 → 1 exit criteria."""
    # _index.md and _bootstrap.md (structural files)
    (vault / "_index.md").write_text("# Index\nContent here.", encoding="utf-8")
    (vault / "_bootstrap.md").write_text("# Bootstrap\nContent here.", encoding="utf-8")

    # Context files populated (not stubs)
    self_dir = vault / "self"
    self_dir.mkdir(exist_ok=True)
    (self_dir / "_index.md").write_text("# Self\nReal content about the user.", encoding="utf-8")

    # At least one project with status file
    proj_dir = vault / "projects" / "MyProject"
    proj_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "status.md").write_text("# Status\nActive.", encoding="utf-8")


# ---------------------------------------------------------------------------
# CriterionResult
# ---------------------------------------------------------------------------


class TestCriterionResult:
    """CriterionResult is a frozen dataclass with expected fields."""

    def test_passed_criterion(self) -> None:
        cr = CriterionResult(name="test", passed=True, detail="All good")
        assert cr.passed is True
        assert cr.name == "test"
        assert cr.detail == "All good"

    def test_failed_criterion(self) -> None:
        cr = CriterionResult(name="test", passed=False, detail="Missing file")
        assert cr.passed is False

    def test_is_frozen(self) -> None:
        cr = CriterionResult(name="test", passed=True, detail="ok")
        with pytest.raises(AttributeError):
            cr.passed = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# StageAssessment
# ---------------------------------------------------------------------------


class TestStageAssessment:
    """StageAssessment summarizes evaluation results."""

    def test_all_passed(self) -> None:
        criteria = (
            CriterionResult(name="a", passed=True, detail="ok"),
            CriterionResult(name="b", passed=True, detail="ok"),
        )
        sa = StageAssessment(current_stage=0, target_stage=1, criteria=criteria)
        assert sa.can_promote is True
        assert sa.current_stage == 0
        assert sa.target_stage == 1

    def test_any_failed_blocks_promotion(self) -> None:
        criteria = (
            CriterionResult(name="a", passed=True, detail="ok"),
            CriterionResult(name="b", passed=False, detail="missing"),
        )
        sa = StageAssessment(current_stage=0, target_stage=1, criteria=criteria)
        assert sa.can_promote is False

    def test_empty_criteria_allows_promotion(self) -> None:
        sa = StageAssessment(current_stage=0, target_stage=1, criteria=())
        assert sa.can_promote is True

    def test_is_frozen(self) -> None:
        sa = StageAssessment(current_stage=0, target_stage=1, criteria=())
        with pytest.raises(AttributeError):
            sa.current_stage = 1  # type: ignore[misc]


# ---------------------------------------------------------------------------
# StageEvaluator — construction
# ---------------------------------------------------------------------------


class TestStageEvaluatorConstruction:
    """StageEvaluator requires a vault path and config."""

    def test_creates_with_vault_path(self, tmp_path: Path) -> None:
        vault = _make_vault(tmp_path)
        config = Config(stage=StageConfig(current_stage=0))
        evaluator = StageEvaluator(vault_path=vault, config=config)
        assert evaluator.current_stage == 0

    def test_reads_stage_from_config(self, tmp_path: Path) -> None:
        vault = _make_vault(tmp_path)
        config = Config(stage=StageConfig(current_stage=2))
        evaluator = StageEvaluator(vault_path=vault, config=config)
        assert evaluator.current_stage == 2

    def test_nonexistent_vault_raises(self, tmp_path: Path) -> None:
        config = Config()
        with pytest.raises(FileNotFoundError):
            StageEvaluator(vault_path=tmp_path / "nope", config=config)


# ---------------------------------------------------------------------------
# StageEvaluator — Stage 0 → 1 exit criteria
# ---------------------------------------------------------------------------


class TestStage0To1Criteria:
    """Stage 0 → 1 requires vault structure, context, projects, and scanner."""

    def test_empty_vault_fails_all(self, tmp_path: Path) -> None:
        vault = _make_vault(tmp_path)
        config = Config(stage=StageConfig(current_stage=0))
        evaluator = StageEvaluator(vault_path=vault, config=config)
        assessment = evaluator.assess(target_stage=1)
        assert assessment.can_promote is False
        assert assessment.current_stage == 0
        assert assessment.target_stage == 1
        # At least some criteria should have failed
        failed = [c for c in assessment.criteria if not c.passed]
        assert len(failed) > 0

    def test_populated_vault_passes(self, tmp_path: Path) -> None:
        vault = _make_vault(tmp_path)
        _populate_stage0_exit_criteria(vault)
        config = Config(stage=StageConfig(current_stage=0))
        evaluator = StageEvaluator(vault_path=vault, config=config)
        assessment = evaluator.assess(target_stage=1)
        assert assessment.can_promote is True

    def test_missing_structural_files_fails(self, tmp_path: Path) -> None:
        vault = _make_vault(tmp_path)
        # Add projects but no structural files
        proj = vault / "projects" / "Test"
        proj.mkdir(parents=True)
        (proj / "status.md").write_text("# Status", encoding="utf-8")
        config = Config(stage=StageConfig(current_stage=0))
        evaluator = StageEvaluator(vault_path=vault, config=config)
        assessment = evaluator.assess(target_stage=1)
        structural = next(
            c for c in assessment.criteria if "structural" in c.name.lower()
        )
        assert structural.passed is False

    def test_missing_project_fails(self, tmp_path: Path) -> None:
        vault = _make_vault(tmp_path)
        (vault / "_index.md").write_text("# Index\nContent.", encoding="utf-8")
        (vault / "_bootstrap.md").write_text("# Bootstrap\nContent.", encoding="utf-8")
        (vault / "self").mkdir()
        (vault / "self" / "_index.md").write_text("# Self\nContent.", encoding="utf-8")
        config = Config(stage=StageConfig(current_stage=0))
        evaluator = StageEvaluator(vault_path=vault, config=config)
        assessment = evaluator.assess(target_stage=1)
        project_criterion = next(
            c for c in assessment.criteria if "project" in c.name.lower()
        )
        assert project_criterion.passed is False


# ---------------------------------------------------------------------------
# StageEvaluator — cannot skip stages
# ---------------------------------------------------------------------------


class TestStageSkipPrevention:
    """Promotion cannot skip stages."""

    def test_cannot_skip_from_0_to_2(self, tmp_path: Path) -> None:
        vault = _make_vault(tmp_path)
        config = Config(stage=StageConfig(current_stage=0))
        evaluator = StageEvaluator(vault_path=vault, config=config)
        with pytest.raises(ValueError, match="Cannot skip"):
            evaluator.assess(target_stage=2)

    def test_cannot_promote_backwards(self, tmp_path: Path) -> None:
        vault = _make_vault(tmp_path)
        config = Config(stage=StageConfig(current_stage=2))
        evaluator = StageEvaluator(vault_path=vault, config=config)
        with pytest.raises(ValueError, match="Cannot promote backwards"):
            evaluator.assess(target_stage=1)

    def test_cannot_promote_to_same(self, tmp_path: Path) -> None:
        vault = _make_vault(tmp_path)
        config = Config(stage=StageConfig(current_stage=1))
        evaluator = StageEvaluator(vault_path=vault, config=config)
        with pytest.raises(ValueError, match="Already at stage"):
            evaluator.assess(target_stage=1)


# ---------------------------------------------------------------------------
# StageEvaluator — assess_current (no target, just report)
# ---------------------------------------------------------------------------


class TestAssessCurrent:
    """assess_current reports status without requiring a target."""

    def test_reports_current_stage(self, tmp_path: Path) -> None:
        vault = _make_vault(tmp_path)
        config = Config(stage=StageConfig(current_stage=0))
        evaluator = StageEvaluator(vault_path=vault, config=config)
        assessment = evaluator.assess_current()
        assert assessment.current_stage == 0
        assert assessment.target_stage == 1  # next stage

    def test_stage_3_has_no_next(self, tmp_path: Path) -> None:
        vault = _make_vault(tmp_path)
        config = Config(stage=StageConfig(current_stage=3))
        evaluator = StageEvaluator(vault_path=vault, config=config)
        assessment = evaluator.assess_current()
        assert assessment.current_stage == 3
        assert assessment.target_stage == 3  # max stage, no next
        assert assessment.criteria == ()  # nothing to check
