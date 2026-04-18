"""Evaluator scorer: per-dimension scoring and weighted composite calculation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from open_workspace_builder._llm_json import parse_json_object
from open_workspace_builder.evaluator.types import TestExecutionResult

if TYPE_CHECKING:
    from open_workspace_builder.llm.backend import ModelBackend

REQUIRED_DIMENSIONS = frozenset({"novelty", "efficiency", "precision", "defect_rate"})
_WEIGHT_SUM_TOLERANCE = 0.01

_SCORING_SYSTEM_PROMPT = """\
You are a skill quality evaluator. You will receive test execution results from \
an AI skill and must score the skill on exactly four dimensions.

Score each dimension from 1 to 10 (integers or one decimal place):

- **novelty**: How creative, original, and non-obvious are the responses? \
Do they go beyond template-like or boilerplate output?
- **efficiency**: How concise and well-structured are the responses? \
Do they achieve the goal without unnecessary verbosity or redundant steps?
- **precision**: How accurate, correct, and relevant are the responses? \
Do they address the prompt requirements without errors or hallucinations?
- **defect_rate**: How free of defects are the responses? Consider factual errors, \
logical inconsistencies, missing requirements, and formatting issues. \
10 means zero defects, 1 means pervasive defects.

Respond ONLY with valid JSON matching this schema:
{
  "scores": {
    "novelty": <number 1-10>,
    "efficiency": <number 1-10>,
    "precision": <number 1-10>,
    "defect_rate": <number 1-10>
  }
}
"""


@dataclass(frozen=True)
class DimensionScore:
    """Score for a single evaluation dimension."""

    dimension: str
    raw_score: float
    weighted_score: float


@dataclass(frozen=True)
class ScoringResult:
    """Complete scoring result for a skill."""

    skill_name: str
    dimension_scores: tuple[DimensionScore, ...]
    composite_score: float
    weight_vector: dict[str, float]
    scored_at: str


def validate_weight_vector(weight_vector: dict[str, float]) -> None:
    """Validate that a weight vector has the correct dimensions and sums to 1.0.

    Raises ValueError if the vector is malformed.
    """
    dimensions = set(weight_vector.keys())
    if dimensions != REQUIRED_DIMENSIONS:
        missing = REQUIRED_DIMENSIONS - dimensions
        extra = dimensions - REQUIRED_DIMENSIONS
        raise ValueError(
            f"Weight vector has invalid dimensions. Missing: {missing}, Extra: {extra}"
        )
    total = sum(weight_vector.values())
    if abs(total - 1.0) > _WEIGHT_SUM_TOLERANCE:
        raise ValueError(
            f"Weight vector sums to {total}, expected 1.0 (tolerance {_WEIGHT_SUM_TOLERANCE})"
        )


def _format_test_results(test_results: list[TestExecutionResult]) -> str:
    """Format test execution results as a structured string for the LLM."""
    parts: list[str] = []
    for r in test_results:
        part = f"### Test Case: {r.test_case_id}\n\n"
        part += f"**Prompt:**\n{r.prompt_sent}\n\n"
        part += f"**Response:**\n{r.response_text}\n"
        if r.token_count is not None:
            part += f"\nTokens: {r.token_count}"
        if r.latency_ms is not None:
            part += f"\nLatency: {r.latency_ms:.0f}ms"
        parts.append(part)
    return "\n---\n".join(parts)


def _parse_scores(response_text: str) -> dict[str, float]:
    """Parse dimension scores from LLM JSON response.

    Raises ValueError if parsing fails or scores are out of range.
    """
    data = parse_json_object(response_text, context="scoring response")

    scores = data.get("scores")
    if not isinstance(scores, dict):
        raise ValueError(f"Response missing 'scores' dict: {response_text[:200]}")

    parsed: dict[str, float] = {}
    for dim in REQUIRED_DIMENSIONS:
        val = scores.get(dim)
        if val is None:
            raise ValueError(f"Missing score for dimension '{dim}'")
        score = float(val)
        if score < 1.0 or score > 10.0:
            raise ValueError(f"Score for '{dim}' is {score}, must be between 1 and 10")
        parsed[dim] = score
    return parsed


class SkillScorer:
    """Scores skill test results across evaluation dimensions using an LLM judge."""

    def __init__(self, model_backend: ModelBackend) -> None:
        self._backend = model_backend

    def score(
        self,
        skill_name: str,
        test_results: list[TestExecutionResult],
        weight_vector: dict[str, float],
    ) -> ScoringResult:
        """Score test results and produce a weighted composite.

        Uses the 'judge' operation on the model backend to evaluate each dimension.
        Validates the weight vector before scoring.

        Raises ValueError if the weight vector is invalid or test_results is empty.
        Raises ModelBackendError if the LLM call fails.
        """
        if not test_results:
            raise ValueError("test_results must not be empty")
        validate_weight_vector(weight_vector)

        formatted = _format_test_results(test_results)
        user_message = (
            f"Score the following skill ({skill_name}) based on its test execution results.\n\n"
            f"{formatted}"
        )

        response = self._backend.completion(
            operation="judge",
            system_prompt=_SCORING_SYSTEM_PROMPT,
            user_message=user_message,
            max_tokens=512,
        )

        raw_scores = _parse_scores(response)

        dimension_scores: list[DimensionScore] = []
        composite = 0.0
        for dim in sorted(REQUIRED_DIMENSIONS):
            raw = raw_scores[dim]
            weight = weight_vector[dim]
            weighted = raw * weight
            composite += weighted
            dimension_scores.append(
                DimensionScore(dimension=dim, raw_score=raw, weighted_score=weighted)
            )

        return ScoringResult(
            skill_name=skill_name,
            dimension_scores=tuple(dimension_scores),
            composite_score=round(composite, 4),
            weight_vector=weight_vector,
            scored_at=datetime.now(timezone.utc).isoformat(),
        )
