"""Tests for evaluator scorer: dimension scoring and weighted composite."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from open_workspace_builder.evaluator.scorer import (
    REQUIRED_DIMENSIONS,
    DimensionScore,
    ScoringResult,
    SkillScorer,
    _format_test_results,
    _parse_scores,
    validate_weight_vector,
)
from open_workspace_builder.evaluator.types import TestExecutionResult


VALID_WEIGHT_VECTOR = {
    "novelty": 0.25,
    "efficiency": 0.25,
    "precision": 0.25,
    "defect_rate": 0.25,
}

SAMPLE_SCORES = {"novelty": 8.0, "efficiency": 7.0, "precision": 9.0, "defect_rate": 6.0}


def _make_mock_backend(scores: dict[str, float]) -> MagicMock:
    """Create a mock ModelBackend returning the given scores as JSON."""
    backend = MagicMock()
    backend.completion.return_value = json.dumps({"scores": scores})
    return backend


def _make_test_results(n: int = 2) -> list[TestExecutionResult]:
    """Create n sample TestExecutionResult objects."""
    return [
        TestExecutionResult(
            test_case_id=f"TC-{i:03d}",
            prompt_sent=f"Test prompt {i}",
            response_text=f"Test response {i}",
            token_count=100 + i,
            latency_ms=50.0 + i,
        )
        for i in range(1, n + 1)
    ]


# ── TestExecutionResult ───────────────────────────────────────────────────


class TestTestExecutionResult:
    def test_frozen(self) -> None:
        r = TestExecutionResult("t1", "p", "r")
        with pytest.raises(AttributeError):
            r.test_case_id = "changed"  # type: ignore[misc]

    def test_optional_fields_default_none(self) -> None:
        r = TestExecutionResult("t1", "p", "r")
        assert r.token_count is None
        assert r.latency_ms is None

    def test_all_fields_set(self) -> None:
        r = TestExecutionResult("t1", "p", "r", token_count=42, latency_ms=12.5)
        assert r.token_count == 42
        assert r.latency_ms == 12.5


# ── DimensionScore ────────────────────────────────────────────────────────


class TestDimensionScore:
    def test_frozen(self) -> None:
        ds = DimensionScore(dimension="novelty", raw_score=8.0, weighted_score=2.0)
        with pytest.raises(AttributeError):
            ds.raw_score = 5.0  # type: ignore[misc]

    def test_fields(self) -> None:
        ds = DimensionScore(dimension="precision", raw_score=9.5, weighted_score=3.325)
        assert ds.dimension == "precision"
        assert ds.raw_score == 9.5
        assert ds.weighted_score == 3.325


# ── ScoringResult ─────────────────────────────────────────────────────────


class TestScoringResult:
    def test_frozen(self) -> None:
        sr = ScoringResult(
            skill_name="test",
            dimension_scores=(),
            composite_score=7.5,
            weight_vector=VALID_WEIGHT_VECTOR,
            scored_at="2026-01-01T00:00:00Z",
        )
        with pytest.raises(AttributeError):
            sr.composite_score = 0.0  # type: ignore[misc]


# ── validate_weight_vector ────────────────────────────────────────────────


class TestValidateWeightVector:
    def test_valid_vector_passes(self) -> None:
        validate_weight_vector(VALID_WEIGHT_VECTOR)

    def test_unequal_weights_summing_to_one(self) -> None:
        wv = {"novelty": 0.40, "efficiency": 0.15, "precision": 0.25, "defect_rate": 0.20}
        validate_weight_vector(wv)

    def test_missing_dimension_raises(self) -> None:
        wv = {"novelty": 0.34, "efficiency": 0.33, "precision": 0.33}
        with pytest.raises(ValueError, match="Missing"):
            validate_weight_vector(wv)

    def test_extra_dimension_raises(self) -> None:
        wv = {**VALID_WEIGHT_VECTOR, "extra": 0.0}
        with pytest.raises(ValueError, match="Extra"):
            validate_weight_vector(wv)

    def test_wrong_sum_raises(self) -> None:
        wv = {"novelty": 0.5, "efficiency": 0.5, "precision": 0.5, "defect_rate": 0.5}
        with pytest.raises(ValueError, match="sums to"):
            validate_weight_vector(wv)

    def test_tolerance_accepts_near_one(self) -> None:
        wv = {"novelty": 0.251, "efficiency": 0.249, "precision": 0.25, "defect_rate": 0.25}
        validate_weight_vector(wv)


# ── _format_test_results ──────────────────────────────────────────────────


class TestFormatTestResults:
    def test_includes_test_case_id(self) -> None:
        results = _make_test_results(1)
        formatted = _format_test_results(results)
        assert "TC-001" in formatted

    def test_includes_prompt_and_response(self) -> None:
        results = _make_test_results(1)
        formatted = _format_test_results(results)
        assert "Test prompt 1" in formatted
        assert "Test response 1" in formatted

    def test_includes_token_count(self) -> None:
        results = _make_test_results(1)
        formatted = _format_test_results(results)
        assert "101" in formatted

    def test_multiple_results_separated(self) -> None:
        results = _make_test_results(3)
        formatted = _format_test_results(results)
        assert "TC-001" in formatted
        assert "TC-002" in formatted
        assert "TC-003" in formatted

    def test_optional_fields_omitted_when_none(self) -> None:
        results = [TestExecutionResult("t1", "p", "r")]
        formatted = _format_test_results(results)
        assert "Tokens" not in formatted
        assert "Latency" not in formatted


# ── _parse_scores ─────────────────────────────────────────────────────────


class TestParseScores:
    def test_valid_json(self) -> None:
        resp = json.dumps({"scores": SAMPLE_SCORES})
        scores = _parse_scores(resp)
        assert scores == SAMPLE_SCORES

    def test_json_in_code_fence(self) -> None:
        resp = f"```json\n{json.dumps({'scores': SAMPLE_SCORES})}\n```"
        scores = _parse_scores(resp)
        assert scores == SAMPLE_SCORES

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(ValueError, match="Could not parse"):
            _parse_scores("not json")

    def test_missing_scores_key_raises(self) -> None:
        with pytest.raises(ValueError, match="missing 'scores'"):
            _parse_scores(json.dumps({"result": {}}))

    def test_missing_dimension_raises(self) -> None:
        incomplete = {"novelty": 8, "efficiency": 7, "precision": 9}
        with pytest.raises(ValueError, match="Missing score"):
            _parse_scores(json.dumps({"scores": incomplete}))

    def test_score_below_one_raises(self) -> None:
        bad = {**SAMPLE_SCORES, "novelty": 0.5}
        with pytest.raises(ValueError, match="must be between 1 and 10"):
            _parse_scores(json.dumps({"scores": bad}))

    def test_score_above_ten_raises(self) -> None:
        bad = {**SAMPLE_SCORES, "precision": 11}
        with pytest.raises(ValueError, match="must be between 1 and 10"):
            _parse_scores(json.dumps({"scores": bad}))

    def test_decimal_scores_accepted(self) -> None:
        scores = {"novelty": 7.5, "efficiency": 8.5, "precision": 6.5, "defect_rate": 9.5}
        parsed = _parse_scores(json.dumps({"scores": scores}))
        assert parsed["novelty"] == 7.5


# ── SkillScorer ───────────────────────────────────────────────────────────


class TestSkillScorer:
    def test_score_returns_scoring_result(self) -> None:
        backend = _make_mock_backend(SAMPLE_SCORES)
        scorer = SkillScorer(backend)
        result = scorer.score("my-skill", _make_test_results(), VALID_WEIGHT_VECTOR)

        assert isinstance(result, ScoringResult)
        assert result.skill_name == "my-skill"
        assert len(result.dimension_scores) == 4

    def test_composite_is_weighted_sum(self) -> None:
        backend = _make_mock_backend(SAMPLE_SCORES)
        scorer = SkillScorer(backend)
        result = scorer.score("my-skill", _make_test_results(), VALID_WEIGHT_VECTOR)

        expected = sum(SAMPLE_SCORES[d] * VALID_WEIGHT_VECTOR[d] for d in REQUIRED_DIMENSIONS)
        assert result.composite_score == round(expected, 4)

    def test_unequal_weights(self) -> None:
        wv = {"novelty": 0.40, "efficiency": 0.10, "precision": 0.30, "defect_rate": 0.20}
        backend = _make_mock_backend(SAMPLE_SCORES)
        scorer = SkillScorer(backend)
        result = scorer.score("s", _make_test_results(), wv)

        expected = sum(SAMPLE_SCORES[d] * wv[d] for d in REQUIRED_DIMENSIONS)
        assert result.composite_score == round(expected, 4)

    def test_dimension_scores_have_correct_values(self) -> None:
        backend = _make_mock_backend(SAMPLE_SCORES)
        scorer = SkillScorer(backend)
        result = scorer.score("s", _make_test_results(), VALID_WEIGHT_VECTOR)

        by_dim = {ds.dimension: ds for ds in result.dimension_scores}
        for dim in REQUIRED_DIMENSIONS:
            assert by_dim[dim].raw_score == SAMPLE_SCORES[dim]
            assert by_dim[dim].weighted_score == SAMPLE_SCORES[dim] * VALID_WEIGHT_VECTOR[dim]

    def test_backend_called_with_judge_operation(self) -> None:
        backend = _make_mock_backend(SAMPLE_SCORES)
        scorer = SkillScorer(backend)
        scorer.score("s", _make_test_results(), VALID_WEIGHT_VECTOR)

        backend.completion.assert_called_once()
        call_kwargs = backend.completion.call_args[1]
        assert call_kwargs["operation"] == "judge"

    def test_skill_name_in_user_message(self) -> None:
        backend = _make_mock_backend(SAMPLE_SCORES)
        scorer = SkillScorer(backend)
        scorer.score("my-cool-skill", _make_test_results(), VALID_WEIGHT_VECTOR)

        call_kwargs = backend.completion.call_args[1]
        assert "my-cool-skill" in call_kwargs["user_message"]

    def test_scored_at_is_iso_timestamp(self) -> None:
        backend = _make_mock_backend(SAMPLE_SCORES)
        scorer = SkillScorer(backend)
        result = scorer.score("s", _make_test_results(), VALID_WEIGHT_VECTOR)

        assert "T" in result.scored_at
        assert (
            "+" in result.scored_at
            or "Z" in result.scored_at
            or result.scored_at.endswith("+00:00")
        )

    def test_weight_vector_preserved(self) -> None:
        backend = _make_mock_backend(SAMPLE_SCORES)
        scorer = SkillScorer(backend)
        result = scorer.score("s", _make_test_results(), VALID_WEIGHT_VECTOR)

        assert result.weight_vector == VALID_WEIGHT_VECTOR

    def test_empty_test_results_raises(self) -> None:
        backend = _make_mock_backend(SAMPLE_SCORES)
        scorer = SkillScorer(backend)
        with pytest.raises(ValueError, match="must not be empty"):
            scorer.score("s", [], VALID_WEIGHT_VECTOR)

    def test_invalid_weight_vector_raises(self) -> None:
        backend = _make_mock_backend(SAMPLE_SCORES)
        scorer = SkillScorer(backend)
        bad_wv = {"novelty": 0.5, "efficiency": 0.5}
        with pytest.raises(ValueError, match="invalid dimensions"):
            scorer.score("s", _make_test_results(), bad_wv)

    def test_backend_error_propagates(self) -> None:
        backend = MagicMock()
        backend.completion.side_effect = RuntimeError("API down")
        scorer = SkillScorer(backend)
        with pytest.raises(RuntimeError, match="API down"):
            scorer.score("s", _make_test_results(), VALID_WEIGHT_VECTOR)
