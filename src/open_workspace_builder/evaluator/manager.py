"""Evaluation manager — top-level orchestrator for the full evaluation pipeline."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from open_workspace_builder.evaluator.classifier import (
    ClassificationResult,
    SkillClassifier,
    load_weight_vectors,
)
from open_workspace_builder.evaluator.generator import TestSuiteGenerator
from open_workspace_builder.evaluator.judge import QualityJudge
from open_workspace_builder.evaluator.persistence import TestSuitePersistence
from open_workspace_builder.evaluator.scorer import ScoringResult, SkillScorer
from open_workspace_builder.evaluator.types import TestExecutionResult

if TYPE_CHECKING:
    from open_workspace_builder.llm.backend import ModelBackend


class EvaluationDecision(enum.Enum):
    """Decision outcome from an evaluation."""

    INCORPORATE = "incorporate"
    REJECT = "reject"
    DEPRECATE_AND_REPLACE = "deprecate_and_replace"


@dataclass(frozen=True)
class EvaluationConfig:
    """Configuration for evaluation thresholds."""

    incorporation_threshold: float = 1.0
    min_test_cases: int = 8


@dataclass(frozen=True)
class EvaluationResult:
    """Complete result from evaluating a skill."""

    skill_name: str
    skill_type: str
    decision: EvaluationDecision
    candidate_scores: ScoringResult
    baseline_scores: ScoringResult | None
    delta_vs_baseline: float
    existing_scores: ScoringResult | None
    delta_vs_existing: float | None
    reasoning: str
    evaluated_at: str


def _execute_test_suite(
    model_backend: ModelBackend,
    prompts: list[tuple[str, str]],
    skill_content: str | None,
) -> list[TestExecutionResult]:
    """Execute test prompts against the model, optionally prepending skill content.

    Each entry in prompts is (test_case_id, prompt_text).
    If skill_content is provided, it is prepended to each prompt as context.
    """
    results: list[TestExecutionResult] = []
    for test_case_id, prompt_text in prompts:
        if skill_content:
            user_message = (
                f"You are operating with the following skill instructions:\n\n"
                f"<skill_instructions>\n{skill_content}\n</skill_instructions>\n\n"
                f"Now respond to this request:\n\n{prompt_text}"
            )
        else:
            user_message = prompt_text

        response = model_backend.completion(
            operation="generate",
            system_prompt="You are a helpful AI assistant.",
            user_message=user_message,
            max_tokens=2048,
        )
        results.append(
            TestExecutionResult(
                test_case_id=test_case_id,
                prompt_sent=prompt_text,
                response_text=response,
            )
        )
    return results


class EvaluationManager:
    """Top-level orchestrator that chains the full evaluation pipeline."""

    def __init__(
        self,
        model_backend: ModelBackend,
        persistence: TestSuitePersistence,
        eval_config: EvaluationConfig | None = None,
    ) -> None:
        self._backend = model_backend
        self._persistence = persistence
        self._config = eval_config or EvaluationConfig()
        self._classifier = SkillClassifier(model_backend)
        self._generator = TestSuiteGenerator(model_backend)
        self._scorer = SkillScorer(model_backend)
        self._judge = QualityJudge(model_backend)
        self._weight_vectors = load_weight_vectors()

    def evaluate_new(self, skill_path: str, source: str = "default") -> EvaluationResult:
        """Evaluate a brand-new skill (UC-1).

        Pipeline: validate -> classify -> generate tests -> execute baseline
        -> execute with skill -> score both -> compare -> decide.
        """
        from open_workspace_builder.evaluator.spec_validator import validate_skill

        skill_dir = Path(skill_path)
        if skill_dir.is_file():
            skill_dir = skill_dir.parent
        validation = validate_skill(str(skill_dir))
        if not validation.valid:
            return EvaluationResult(
                skill_name=skill_dir.name,
                skill_type="unknown",
                decision=EvaluationDecision.REJECT,
                candidate_scores=ScoringResult(
                    skill_name=skill_dir.name,
                    dimension_scores=(),
                    composite_score=0.0,
                    weight_vector={},
                    scored_at="",
                ),
                baseline_scores=None,
                delta_vs_baseline=0.0,
                existing_scores=None,
                delta_vs_existing=None,
                reasoning=f"Spec validation failed: {'; '.join(validation.errors)}",
                evaluated_at=datetime.now(timezone.utc).isoformat(),
            )

        skill_content = Path(skill_path).read_text(encoding="utf-8")

        classification = self._classifier.classify(skill_content)
        weight_vector = self._resolve_weight_vector(classification)

        suite = self._generator.generate(skill_content, classification)

        prompts = [(tc.id, tc.prompt) for tc in suite.test_cases]

        baseline_results = _execute_test_suite(self._backend, prompts, skill_content=None)
        candidate_results = _execute_test_suite(self._backend, prompts, skill_content=skill_content)

        baseline_scores = self._scorer.score(
            f"{suite.skill_name}-baseline", baseline_results, weight_vector
        )
        candidate_scores = self._scorer.score(suite.skill_name, candidate_results, weight_vector)

        delta = round(candidate_scores.composite_score - baseline_scores.composite_score, 4)

        if delta >= self._config.incorporation_threshold:
            decision = EvaluationDecision.INCORPORATE
            reasoning = (
                f"Candidate composite ({candidate_scores.composite_score:.2f}) exceeds "
                f"baseline ({baseline_scores.composite_score:.2f}) by {delta:.2f}, "
                f"meeting threshold of {self._config.incorporation_threshold:.2f}."
            )
        else:
            decision = EvaluationDecision.REJECT
            reasoning = (
                f"Candidate composite ({candidate_scores.composite_score:.2f}) vs "
                f"baseline ({baseline_scores.composite_score:.2f}): delta {delta:.2f} "
                f"below threshold of {self._config.incorporation_threshold:.2f}."
            )

        self._persistence.save_suite(suite, source)

        result = EvaluationResult(
            skill_name=suite.skill_name,
            skill_type=classification.skill_type,
            decision=decision,
            candidate_scores=candidate_scores,
            baseline_scores=baseline_scores,
            delta_vs_baseline=delta,
            existing_scores=None,
            delta_vs_existing=None,
            reasoning=reasoning,
            evaluated_at=datetime.now(timezone.utc).isoformat(),
        )

        self._persistence.save_result(suite.skill_name, source, _result_to_dict(result))

        return result

    def evaluate_update(self, skill_path: str, source: str = "default") -> EvaluationResult:
        """Evaluate an updated version of an existing skill (UC-2).

        Pipeline: load existing suite -> execute against new version -> score
        -> compare with stored scores -> decide.
        """
        skill_content = Path(skill_path).read_text(encoding="utf-8")

        classification = self._classifier.classify(skill_content)
        weight_vector = self._resolve_weight_vector(classification)

        skill_name = _extract_skill_name_from_content(skill_content)
        existing_suite = self._persistence.load_suite(skill_name, source)
        if existing_suite is None:
            return self.evaluate_new(skill_path, source)

        existing_result_dict = self._persistence.load_result(skill_name, source)
        existing_composite = _extract_composite_from_result(existing_result_dict)

        prompts = [(tc.id, tc.prompt) for tc in existing_suite.test_cases]
        candidate_results = _execute_test_suite(self._backend, prompts, skill_content=skill_content)
        candidate_scores = self._scorer.score(skill_name, candidate_results, weight_vector)

        existing_scores = (
            ScoringResult(
                skill_name=skill_name,
                dimension_scores=(),
                composite_score=existing_composite,
                weight_vector=weight_vector,
                scored_at="",
            )
            if existing_composite is not None
            else None
        )

        delta_vs_existing = (
            round(candidate_scores.composite_score - existing_composite, 4)
            if existing_composite is not None
            else None
        )

        threshold = self._config.incorporation_threshold

        if delta_vs_existing is not None and delta_vs_existing >= threshold:
            decision = EvaluationDecision.DEPRECATE_AND_REPLACE
            reasoning = (
                f"New version ({candidate_scores.composite_score:.2f}) exceeds "
                f"existing ({existing_composite:.2f}) by {delta_vs_existing:.2f}, "
                f"meeting replacement threshold."
            )
        elif delta_vs_existing is not None and delta_vs_existing < -threshold:
            decision = EvaluationDecision.REJECT
            reasoning = (
                f"New version ({candidate_scores.composite_score:.2f}) scored below "
                f"existing ({existing_composite:.2f}) by {abs(delta_vs_existing):.2f}."
            )
        else:
            decision = EvaluationDecision.REJECT
            reasoning = (
                f"New version ({candidate_scores.composite_score:.2f}) is within "
                f"threshold of existing. Keeping current version."
            )

        result = EvaluationResult(
            skill_name=skill_name,
            skill_type=classification.skill_type,
            decision=decision,
            candidate_scores=candidate_scores,
            baseline_scores=None,
            delta_vs_baseline=0.0,
            existing_scores=existing_scores,
            delta_vs_existing=delta_vs_existing,
            reasoning=reasoning,
            evaluated_at=datetime.now(timezone.utc).isoformat(),
        )

        if decision == EvaluationDecision.DEPRECATE_AND_REPLACE:
            self._persistence.save_result(skill_name, source, _result_to_dict(result))

        return result

    def evaluate_overlap(
        self,
        skill_path: str,
        existing_skill: str,
        new_capabilities: list[str],
        source: str = "default",
    ) -> EvaluationResult:
        """Evaluate a skill with overlapping functionality (UC-3).

        Pipeline: load existing tests -> run against candidate -> generate incremental
        tests for new capabilities -> run those too -> score combined -> decide.
        """
        skill_content = Path(skill_path).read_text(encoding="utf-8")

        classification = self._classifier.classify(skill_content)
        weight_vector = self._resolve_weight_vector(classification)

        existing_suite = self._persistence.load_suite(existing_skill, source)
        if existing_suite is None:
            return self.evaluate_new(skill_path, source)

        merged_suite = self._generator.generate_incremental(
            skill_content, classification, existing_suite, new_capabilities
        )

        prompts = [(tc.id, tc.prompt) for tc in merged_suite.test_cases]
        candidate_results = _execute_test_suite(self._backend, prompts, skill_content=skill_content)
        baseline_results = _execute_test_suite(self._backend, prompts, skill_content=None)

        candidate_scores = self._scorer.score(
            merged_suite.skill_name, candidate_results, weight_vector
        )
        baseline_scores = self._scorer.score(
            f"{merged_suite.skill_name}-baseline", baseline_results, weight_vector
        )

        delta = round(candidate_scores.composite_score - baseline_scores.composite_score, 4)

        if delta >= self._config.incorporation_threshold:
            decision = EvaluationDecision.INCORPORATE
            reasoning = (
                f"Candidate with overlapping capabilities scored {candidate_scores.composite_score:.2f} "
                f"vs baseline {baseline_scores.composite_score:.2f} (delta {delta:.2f}), "
                f"meeting threshold."
            )
        else:
            decision = EvaluationDecision.REJECT
            reasoning = (
                f"Candidate delta {delta:.2f} below threshold "
                f"of {self._config.incorporation_threshold:.2f}."
            )

        self._persistence.save_suite(merged_suite, source)

        result = EvaluationResult(
            skill_name=merged_suite.skill_name,
            skill_type=classification.skill_type,
            decision=decision,
            candidate_scores=candidate_scores,
            baseline_scores=baseline_scores,
            delta_vs_baseline=delta,
            existing_scores=None,
            delta_vs_existing=None,
            reasoning=reasoning,
            evaluated_at=datetime.now(timezone.utc).isoformat(),
        )

        self._persistence.save_result(merged_suite.skill_name, source, _result_to_dict(result))
        return result

    def _resolve_weight_vector(self, classification: ClassificationResult) -> dict[str, float]:
        """Resolve weight vector for a classification, falling back to 'general'."""
        wv = self._weight_vectors.get(classification.skill_type)
        if wv is None:
            wv = self._weight_vectors.get(
                "general",
                {
                    "novelty": 0.25,
                    "efficiency": 0.25,
                    "precision": 0.25,
                    "defect_rate": 0.25,
                },
            )
        return wv


def _extract_skill_name_from_content(content: str) -> str:
    """Extract skill name from SKILL.md content."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip().lower().replace(" ", "-")
    return "unknown"


def _extract_composite_from_result(result_dict: dict[str, object] | None) -> float | None:
    """Extract composite score from a persisted result dict."""
    if result_dict is None:
        return None
    candidate = result_dict.get("candidate_scores")
    if isinstance(candidate, dict):
        score = candidate.get("composite_score")
        if score is not None:
            return float(score)
    return None


def _result_to_dict(result: EvaluationResult) -> dict[str, object]:
    """Serialize an EvaluationResult to a JSON-compatible dict."""
    return {
        "skill_name": result.skill_name,
        "skill_type": result.skill_type,
        "decision": result.decision.value,
        "candidate_scores": {
            "skill_name": result.candidate_scores.skill_name,
            "composite_score": result.candidate_scores.composite_score,
            "weight_vector": result.candidate_scores.weight_vector,
            "scored_at": result.candidate_scores.scored_at,
            "dimension_scores": [
                {
                    "dimension": ds.dimension,
                    "raw_score": ds.raw_score,
                    "weighted_score": ds.weighted_score,
                }
                for ds in result.candidate_scores.dimension_scores
            ],
        },
        "baseline_scores": {
            "composite_score": result.baseline_scores.composite_score,
        }
        if result.baseline_scores
        else None,
        "delta_vs_baseline": result.delta_vs_baseline,
        "existing_scores": {
            "composite_score": result.existing_scores.composite_score,
        }
        if result.existing_scores
        else None,
        "delta_vs_existing": result.delta_vs_existing,
        "reasoning": result.reasoning,
        "evaluated_at": result.evaluated_at,
    }
