"""Tests for evaluation manager: full pipeline orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from open_workspace_builder.evaluator.classifier import ClassificationResult
from open_workspace_builder.evaluator.generator import TestCase, TestSuite
from open_workspace_builder.evaluator.manager import (
    EvaluationConfig,
    EvaluationDecision,
    EvaluationManager,
    EvaluationResult,
    _execute_test_suite,
    _extract_skill_name_from_content,
    _result_to_dict,
)
from open_workspace_builder.evaluator.persistence import TestSuitePersistence
from open_workspace_builder.evaluator.scorer import ScoringResult

SAMPLE_CLASSIFICATION = ClassificationResult(
    skill_type="general", confidence=0.9, reasoning="General skill"
)

SAMPLE_SCORES = {"novelty": 7.0, "efficiency": 7.0, "precision": 7.0, "defect_rate": 7.0}
EQUAL_WEIGHTS = {"novelty": 0.25, "efficiency": 0.25, "precision": 0.25, "defect_rate": 0.25}

SAMPLE_CASES_JSON = json.dumps(
    [
        {
            "id": "TC-001",
            "description": "d1",
            "prompt": "p1",
            "expected_behavior": "e1",
            "dimensions_tested": ["novelty"],
        },
        {
            "id": "TC-002",
            "description": "d2",
            "prompt": "p2",
            "expected_behavior": "e2",
            "dimensions_tested": ["efficiency"],
        },
    ]
)


def _mock_scoring_response(scores: dict[str, float]) -> str:
    return json.dumps({"scores": scores})


def _make_skill_file(tmp_path: Path, name: str = "test-skill", content: str = "") -> Path:
    skill_dir = tmp_path / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    default_content = (
        f"---\nname: {name}\ndescription: Use this when evaluating test skills.\n---\n\n"
        f"# {name}\n\nA test skill for evaluation."
    )
    skill_file.write_text(content or default_content, encoding="utf-8")
    return skill_file


def _make_backend_with_pipeline_responses(
    classify_response: str,
    generate_response: str,
    score_high: dict[str, float],
    score_low: dict[str, float],
) -> MagicMock:
    """Create a backend that returns appropriate responses for the full pipeline.

    The completion method is called in sequence: classify, generate, then alternating
    generate (execution) and judge (scoring) calls.
    """
    backend = MagicMock()

    responses: list[str] = []
    # 1. classify
    responses.append(classify_response)
    # 2. generate test suite
    responses.append(generate_response)
    # 3. execute baseline (2 test cases)
    responses.extend(["Baseline response 1", "Baseline response 2"])
    # 4. execute candidate (2 test cases)
    responses.extend(["Candidate response 1", "Candidate response 2"])
    # 5. score baseline
    responses.append(_mock_scoring_response(score_low))
    # 6. score candidate
    responses.append(_mock_scoring_response(score_high))

    backend.completion.side_effect = responses
    return backend


# ── EvaluationDecision ────────────────────────────────────────────────────


class TestEvaluationDecision:
    def test_values(self) -> None:
        assert EvaluationDecision.INCORPORATE.value == "incorporate"
        assert EvaluationDecision.REJECT.value == "reject"
        assert EvaluationDecision.DEPRECATE_AND_REPLACE.value == "deprecate_and_replace"


# ── EvaluationConfig ─────────────────────────────────────────────────────


class TestEvaluationConfig:
    def test_defaults(self) -> None:
        ec = EvaluationConfig()
        assert ec.incorporation_threshold == 1.0
        assert ec.min_test_cases == 8

    def test_frozen(self) -> None:
        ec = EvaluationConfig()
        with pytest.raises(AttributeError):
            ec.incorporation_threshold = 2.0  # type: ignore[misc]

    def test_custom_values(self) -> None:
        ec = EvaluationConfig(incorporation_threshold=0.5, min_test_cases=4)
        assert ec.incorporation_threshold == 0.5
        assert ec.min_test_cases == 4


# ── EvaluationResult ─────────────────────────────────────────────────────


class TestEvaluationResult:
    def test_frozen(self) -> None:
        sr = ScoringResult("s", (), 7.0, EQUAL_WEIGHTS, "now")
        er = EvaluationResult(
            skill_name="s",
            skill_type="general",
            decision=EvaluationDecision.INCORPORATE,
            candidate_scores=sr,
            baseline_scores=None,
            delta_vs_baseline=1.0,
            existing_scores=None,
            delta_vs_existing=None,
            reasoning="test",
            evaluated_at="now",
        )
        with pytest.raises(AttributeError):
            er.decision = EvaluationDecision.REJECT  # type: ignore[misc]


# ── _extract_skill_name_from_content ──────────────────────────────────────


class TestExtractSkillName:
    def test_extracts_from_heading(self) -> None:
        assert _extract_skill_name_from_content("# My Skill\nContent") == "my-skill"

    def test_unknown_when_no_heading(self) -> None:
        assert _extract_skill_name_from_content("No heading") == "unknown"


# ── _execute_test_suite ───────────────────────────────────────────────────


class TestExecuteTestSuite:
    def test_without_skill_content(self) -> None:
        backend = MagicMock()
        backend.completion.return_value = "response"
        results = _execute_test_suite(backend, [("TC-001", "prompt")], skill_content=None)
        assert len(results) == 1
        assert results[0].test_case_id == "TC-001"
        assert "prompt" in backend.completion.call_args[1]["user_message"]

    def test_with_skill_content(self) -> None:
        backend = MagicMock()
        backend.completion.return_value = "response"
        results = _execute_test_suite(
            backend, [("TC-001", "prompt")], skill_content="skill instructions"
        )
        assert len(results) == 1
        um = backend.completion.call_args[1]["user_message"]
        assert "skill instructions" in um
        assert "<skill_instructions>" in um

    def test_multiple_prompts(self) -> None:
        backend = MagicMock()
        backend.completion.side_effect = ["r1", "r2", "r3"]
        results = _execute_test_suite(
            backend, [("TC-001", "p1"), ("TC-002", "p2"), ("TC-003", "p3")], skill_content=None
        )
        assert len(results) == 3
        assert backend.completion.call_count == 3

    def test_uses_generate_operation(self) -> None:
        backend = MagicMock()
        backend.completion.return_value = "r"
        _execute_test_suite(backend, [("TC-001", "p")], skill_content=None)
        assert backend.completion.call_args[1]["operation"] == "generate"


# ── _result_to_dict ──────────────────────────────────────────────────────


class TestResultToDict:
    def test_serializes_decision_as_string(self) -> None:
        sr = ScoringResult("s", (), 7.0, EQUAL_WEIGHTS, "now")
        er = EvaluationResult(
            skill_name="s",
            skill_type="general",
            decision=EvaluationDecision.INCORPORATE,
            candidate_scores=sr,
            baseline_scores=sr,
            delta_vs_baseline=1.0,
            existing_scores=None,
            delta_vs_existing=None,
            reasoning="good",
            evaluated_at="now",
        )
        d = _result_to_dict(er)
        assert d["decision"] == "incorporate"
        assert d["skill_name"] == "s"

    def test_handles_none_baseline(self) -> None:
        sr = ScoringResult("s", (), 7.0, EQUAL_WEIGHTS, "now")
        er = EvaluationResult(
            skill_name="s",
            skill_type="general",
            decision=EvaluationDecision.REJECT,
            candidate_scores=sr,
            baseline_scores=None,
            delta_vs_baseline=0.0,
            existing_scores=None,
            delta_vs_existing=None,
            reasoning="r",
            evaluated_at="now",
        )
        d = _result_to_dict(er)
        assert d["baseline_scores"] is None


# ── EvaluationManager.evaluate_new ────────────────────────────────────────


class TestEvaluateNew:
    def test_incorporate_when_delta_above_threshold(self, tmp_path: Path) -> None:
        skill_file = _make_skill_file(tmp_path)
        persistence = TestSuitePersistence(str(tmp_path / "meta"))

        classify_resp = json.dumps({"skill_type": "general", "confidence": 0.9, "reasoning": "r"})
        high_scores = {"novelty": 9.0, "efficiency": 8.0, "precision": 9.0, "defect_rate": 8.0}
        low_scores = {"novelty": 5.0, "efficiency": 5.0, "precision": 5.0, "defect_rate": 5.0}

        backend = _make_backend_with_pipeline_responses(
            classify_resp,
            SAMPLE_CASES_JSON,
            high_scores,
            low_scores,
        )

        manager = EvaluationManager(
            backend, persistence, EvaluationConfig(incorporation_threshold=1.0)
        )
        result = manager.evaluate_new(str(skill_file))

        assert result.decision == EvaluationDecision.INCORPORATE
        assert result.delta_vs_baseline > 0
        assert result.skill_type == "general"

    def test_reject_when_delta_below_threshold(self, tmp_path: Path) -> None:
        skill_file = _make_skill_file(tmp_path)
        persistence = TestSuitePersistence(str(tmp_path / "meta"))

        classify_resp = json.dumps({"skill_type": "general", "confidence": 0.9, "reasoning": "r"})
        equal_scores = {"novelty": 6.0, "efficiency": 6.0, "precision": 6.0, "defect_rate": 6.0}

        backend = _make_backend_with_pipeline_responses(
            classify_resp,
            SAMPLE_CASES_JSON,
            equal_scores,
            equal_scores,
        )

        manager = EvaluationManager(
            backend, persistence, EvaluationConfig(incorporation_threshold=1.0)
        )
        result = manager.evaluate_new(str(skill_file))

        assert result.decision == EvaluationDecision.REJECT
        assert result.delta_vs_baseline <= 0

    def test_persists_suite_and_result(self, tmp_path: Path) -> None:
        skill_file = _make_skill_file(tmp_path)
        persistence = TestSuitePersistence(str(tmp_path / "meta"))

        classify_resp = json.dumps({"skill_type": "general", "confidence": 0.9, "reasoning": "r"})
        scores = {"novelty": 8.0, "efficiency": 8.0, "precision": 8.0, "defect_rate": 8.0}

        backend = _make_backend_with_pipeline_responses(
            classify_resp,
            SAMPLE_CASES_JSON,
            scores,
            scores,
        )

        manager = EvaluationManager(backend, persistence)
        manager.evaluate_new(str(skill_file))

        loaded = persistence.load_suite("test-skill", "default")
        assert loaded is not None
        assert len(loaded.test_cases) == 2

    def test_reasoning_includes_scores(self, tmp_path: Path) -> None:
        skill_file = _make_skill_file(tmp_path)
        persistence = TestSuitePersistence(str(tmp_path / "meta"))

        classify_resp = json.dumps({"skill_type": "general", "confidence": 0.9, "reasoning": "r"})
        high = {"novelty": 9.0, "efficiency": 9.0, "precision": 9.0, "defect_rate": 9.0}
        low = {"novelty": 3.0, "efficiency": 3.0, "precision": 3.0, "defect_rate": 3.0}

        backend = _make_backend_with_pipeline_responses(classify_resp, SAMPLE_CASES_JSON, high, low)
        result = EvaluationManager(backend, persistence).evaluate_new(str(skill_file))

        assert "baseline" in result.reasoning.lower() or "candidate" in result.reasoning.lower()


# ── EvaluationManager.evaluate_update ─────────────────────────────────────


class TestEvaluateUpdate:
    def test_falls_back_to_evaluate_new_when_no_existing(self, tmp_path: Path) -> None:
        skill_file = _make_skill_file(tmp_path)
        persistence = TestSuitePersistence(str(tmp_path / "meta"))

        classify_resp = json.dumps({"skill_type": "general", "confidence": 0.9, "reasoning": "r"})
        scores = {"novelty": 8.0, "efficiency": 8.0, "precision": 8.0, "defect_rate": 8.0}
        low = {"novelty": 4.0, "efficiency": 4.0, "precision": 4.0, "defect_rate": 4.0}

        # evaluate_update calls classify, finds no suite, falls back to evaluate_new
        # which calls classify again + generate + execute + score
        backend = MagicMock()
        backend.completion.side_effect = [
            classify_resp,  # classify in evaluate_update
            classify_resp,  # classify in evaluate_new (fallback)
            SAMPLE_CASES_JSON,  # generate test suite
            "b1",
            "b2",  # baseline execution
            "c1",
            "c2",  # candidate execution
            _mock_scoring_response(low),  # score baseline
            _mock_scoring_response(scores),  # score candidate
        ]
        result = EvaluationManager(backend, persistence).evaluate_update(str(skill_file))

        assert result.decision in (EvaluationDecision.INCORPORATE, EvaluationDecision.REJECT)

    def test_deprecate_when_new_exceeds_existing(self, tmp_path: Path) -> None:
        skill_file = _make_skill_file(tmp_path)
        persistence = TestSuitePersistence(str(tmp_path / "meta"))

        # Pre-seed an existing suite and low-scoring result
        suite = TestSuite(
            skill_name="test-skill",
            skill_type="general",
            generated_at="",
            generator_model="m",
            test_cases=(
                TestCase("TC-001", "d1", "p1", "e1", ("novelty",)),
                TestCase("TC-002", "d2", "p2", "e2", ("efficiency",)),
            ),
            hash="sha256:abc",
        )
        persistence.save_suite(suite, "default")
        persistence.save_result(
            "test-skill",
            "default",
            {
                "candidate_scores": {"composite_score": 4.0},
            },
        )

        classify_resp = json.dumps({"skill_type": "general", "confidence": 0.9, "reasoning": "r"})
        high_scores = {"novelty": 9.0, "efficiency": 9.0, "precision": 9.0, "defect_rate": 9.0}

        # classify + execute candidate (2 prompts) + score candidate
        backend = MagicMock()
        backend.completion.side_effect = [
            classify_resp,
            "Candidate 1",
            "Candidate 2",
            _mock_scoring_response(high_scores),
        ]

        result = EvaluationManager(
            backend, persistence, EvaluationConfig(incorporation_threshold=1.0)
        ).evaluate_update(str(skill_file))

        assert result.decision == EvaluationDecision.DEPRECATE_AND_REPLACE
        assert result.delta_vs_existing is not None
        assert result.delta_vs_existing > 0


# ── EvaluationManager.evaluate_overlap ────────────────────────────────────


class TestEvaluateOverlap:
    def test_falls_back_when_no_existing_suite(self, tmp_path: Path) -> None:
        skill_file = _make_skill_file(tmp_path)
        persistence = TestSuitePersistence(str(tmp_path / "meta"))

        classify_resp = json.dumps({"skill_type": "general", "confidence": 0.9, "reasoning": "r"})
        scores = {"novelty": 8.0, "efficiency": 8.0, "precision": 8.0, "defect_rate": 8.0}
        low = {"novelty": 4.0, "efficiency": 4.0, "precision": 4.0, "defect_rate": 4.0}

        # evaluate_overlap calls classify, finds no suite, falls back to evaluate_new
        # which calls classify again + generate + execute + score
        backend = MagicMock()
        backend.completion.side_effect = [
            classify_resp,  # classify in evaluate_overlap
            classify_resp,  # classify in evaluate_new (fallback)
            SAMPLE_CASES_JSON,  # generate test suite
            "b1",
            "b2",  # baseline execution
            "c1",
            "c2",  # candidate execution
            _mock_scoring_response(low),  # score baseline
            _mock_scoring_response(scores),  # score candidate
        ]
        result = EvaluationManager(backend, persistence).evaluate_overlap(
            str(skill_file), "nonexistent", ["new cap"]
        )
        assert result.decision in (EvaluationDecision.INCORPORATE, EvaluationDecision.REJECT)

    def test_merges_incremental_tests(self, tmp_path: Path) -> None:
        skill_file = _make_skill_file(tmp_path)
        persistence = TestSuitePersistence(str(tmp_path / "meta"))

        existing_suite = TestSuite(
            skill_name="existing-skill",
            skill_type="general",
            generated_at="",
            generator_model="m",
            test_cases=(TestCase("TC-001", "d", "p", "e", ("novelty",)),),
            hash="sha256:abc",
        )
        persistence.save_suite(existing_suite, "default")

        classify_resp = json.dumps({"skill_type": "general", "confidence": 0.9, "reasoning": "r"})
        new_tc = json.dumps(
            [
                {
                    "id": "TC-002",
                    "description": "d2",
                    "prompt": "p2",
                    "expected_behavior": "e2",
                    "dimensions_tested": ["efficiency"],
                }
            ]
        )
        high = {"novelty": 9.0, "efficiency": 9.0, "precision": 9.0, "defect_rate": 9.0}
        low = {"novelty": 4.0, "efficiency": 4.0, "precision": 4.0, "defect_rate": 4.0}

        # classify, generate_incremental, execute candidate (2), execute baseline (2), score candidate, score baseline
        backend = MagicMock()
        backend.completion.side_effect = [
            classify_resp,  # classify
            new_tc,  # generate incremental
            "c1",
            "c2",  # candidate execution (first)
            "b1",
            "b2",  # baseline execution (second)
            _mock_scoring_response(high),  # score candidate
            _mock_scoring_response(low),  # score baseline
        ]

        result = EvaluationManager(
            backend, persistence, EvaluationConfig(incorporation_threshold=1.0)
        ).evaluate_overlap(str(skill_file), "existing-skill", ["new capability"])

        assert result.decision == EvaluationDecision.INCORPORATE
        assert result.delta_vs_baseline > 0
