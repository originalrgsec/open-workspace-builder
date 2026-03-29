"""Stage assessment and promotion logic (PRD stages 0-3)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from open_workspace_builder.config import Config

MAX_STAGE = 3

# Structural files that must exist for Stage 0 → 1
_REQUIRED_STRUCTURAL_FILES = ("_index.md", "_bootstrap.md")


@dataclass(frozen=True)
class CriterionResult:
    """Result of evaluating a single exit criterion."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class StageAssessment:
    """Summary of stage evaluation."""

    current_stage: int
    target_stage: int
    criteria: tuple[CriterionResult, ...]

    @property
    def can_promote(self) -> bool:
        return all(c.passed for c in self.criteria)


class StageEvaluator:
    """Evaluates workspace stage and checks exit criteria for promotion."""

    def __init__(self, vault_path: Path, config: Config) -> None:
        if not vault_path.is_dir():
            raise FileNotFoundError(
                f"Vault path does not exist or is not a directory: {vault_path}"
            )
        self._vault_path = vault_path
        self._config = config

    @property
    def current_stage(self) -> int:
        return self._config.stage.current_stage

    def assess(self, target_stage: int) -> StageAssessment:
        """Assess whether the workspace can promote to target_stage."""
        current = self.current_stage

        if target_stage == current:
            raise ValueError(f"Already at stage {current}")
        if target_stage < current:
            raise ValueError(
                f"Cannot promote backwards from stage {current} to {target_stage}"
            )
        if target_stage > current + 1:
            raise ValueError(
                f"Cannot skip from stage {current} to {target_stage}. "
                f"Promote to stage {current + 1} first."
            )

        criteria = self._check_exit_criteria(current, target_stage)
        return StageAssessment(
            current_stage=current,
            target_stage=target_stage,
            criteria=criteria,
        )

    def assess_current(self) -> StageAssessment:
        """Report current stage status and readiness for next stage."""
        current = self.current_stage
        if current >= MAX_STAGE:
            return StageAssessment(
                current_stage=current,
                target_stage=current,
                criteria=(),
            )

        target = current + 1
        criteria = self._check_exit_criteria(current, target)
        return StageAssessment(
            current_stage=current,
            target_stage=target,
            criteria=criteria,
        )

    def _check_exit_criteria(
        self, current: int, target: int
    ) -> tuple[CriterionResult, ...]:
        """Dispatch to stage-specific criterion checks."""
        if current == 0 and target == 1:
            return self._check_stage_0_to_1()
        if current == 1 and target == 2:
            return self._check_stage_1_to_2()
        if current == 2 and target == 3:
            return self._check_stage_2_to_3()
        return ()

    # ------------------------------------------------------------------
    # Stage 0 → 1: Cold Start → Interactive Operation
    # ------------------------------------------------------------------

    def _check_stage_0_to_1(self) -> tuple[CriterionResult, ...]:
        results: list[CriterionResult] = []
        results.append(self._check_structural_files())
        results.append(self._check_context_populated())
        results.append(self._check_project_scaffolded())
        return tuple(results)

    def _check_structural_files(self) -> CriterionResult:
        """Vault must have core structural files (_index.md, _bootstrap.md)."""
        missing = [
            f for f in _REQUIRED_STRUCTURAL_FILES
            if not (self._vault_path / f).is_file()
        ]
        if missing:
            return CriterionResult(
                name="Structural files present",
                passed=False,
                detail=f"Missing: {', '.join(missing)}",
            )
        return CriterionResult(
            name="Structural files present",
            passed=True,
            detail="All required structural files exist",
        )

    def _check_context_populated(self) -> CriterionResult:
        """Context files must be populated (not empty stubs)."""
        self_dir = self._vault_path / "self"
        if not self_dir.is_dir():
            return CriterionResult(
                name="Context files populated",
                passed=False,
                detail="self/ directory does not exist",
            )
        # Check that at least one file in self/ has non-trivial content
        try:
            has_content = any(
                f.is_file() and len(f.read_text(encoding="utf-8").strip()) > 20
                for f in self_dir.iterdir()
            )
        except OSError as exc:
            return CriterionResult(
                name="Context files populated",
                passed=False,
                detail=f"Error reading self/ directory: {exc}",
            )
        if not has_content:
            return CriterionResult(
                name="Context files populated",
                passed=False,
                detail="self/ directory has no populated files (content > 20 chars)",
            )
        return CriterionResult(
            name="Context files populated",
            passed=True,
            detail="Context files contain content",
        )

    def _check_project_scaffolded(self) -> CriterionResult:
        """At least one project must be scaffolded with a status file."""
        projects_dir = self._vault_path / "projects"
        if not projects_dir.is_dir():
            return CriterionResult(
                name="Project scaffolded",
                passed=False,
                detail="projects/ directory does not exist",
            )
        # Walk projects looking for any status.md
        has_project = any(
            f.is_file() for f in projects_dir.rglob("status.md")
        )
        if not has_project:
            return CriterionResult(
                name="Project scaffolded",
                passed=False,
                detail="No project with status.md found under projects/",
            )
        return CriterionResult(
            name="Project scaffolded",
            passed=True,
            detail="At least one project with status.md found",
        )

    # ------------------------------------------------------------------
    # Stage 1 → 2: Interactive Operation → Build Farm
    # ------------------------------------------------------------------

    def _check_stage_1_to_2(self) -> tuple[CriterionResult, ...]:
        """Stage 1 → 2 criteria are checked but not yet fully automatable.

        Returns placeholder criteria that require manual verification.
        """
        return (
            CriterionResult(
                name="Minimum 3 sprint cycles",
                passed=False,
                detail="Manual verification required: check vault sprint metadata",
            ),
            CriterionResult(
                name="Vault policies passing",
                passed=False,
                detail="Manual verification required: run policy compliance checks",
            ),
            CriterionResult(
                name="Scanner tested on 50+ files",
                passed=False,
                detail="Manual verification required: check scan history",
            ),
            CriterionResult(
                name="Dependency SCA in CI",
                passed=False,
                detail="Manual verification required: check CI configuration",
            ),
            CriterionResult(
                name="Delegation policy defined",
                passed=False,
                detail="Manual verification required: delegation policy artifact needed",
            ),
        )

    # ------------------------------------------------------------------
    # Stage 2 → 3: Build Farm → Director Model
    # ------------------------------------------------------------------

    def _check_stage_2_to_3(self) -> tuple[CriterionResult, ...]:
        """Stage 2 → 3 criteria are future work.

        Returns placeholder criteria that require manual verification.
        """
        return (
            CriterionResult(
                name="Orchestrator operational",
                passed=False,
                detail="Manual verification required: 2+ unattended sprints",
            ),
            CriterionResult(
                name="Sandbox policy enforced",
                passed=False,
                detail="Manual verification required: sandbox testing evidence",
            ),
            CriterionResult(
                name="Delegation policy calibrated",
                passed=False,
                detail="Manual verification required: zero escalation failures",
            ),
            CriterionResult(
                name="Session audit log complete",
                passed=False,
                detail="Manual verification required: queryable audit log",
            ),
        )
