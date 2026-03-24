"""Tests for the skill type classifier (S028)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from open_workspace_builder.evaluator.classifier import (
    ClassificationResult,
    SkillClassifier,
    _parse_classification,
    load_weight_vectors,
)


class TestParseClassification:
    def test_valid_json(self) -> None:
        raw = json.dumps(
            {
                "skill_type": "security-analysis",
                "confidence": 0.92,
                "reasoning": "Contains vulnerability scanning logic",
            }
        )
        result = _parse_classification(raw)
        assert result.skill_type == "security-analysis"
        assert result.confidence == 0.92
        assert result.reasoning == "Contains vulnerability scanning logic"

    def test_json_in_markdown_fence(self) -> None:
        raw = '```json\n{"skill_type": "code-review", "confidence": 0.85, "reasoning": "x"}\n```'
        result = _parse_classification(raw)
        assert result.skill_type == "code-review"

    def test_missing_skill_type_raises(self) -> None:
        raw = json.dumps({"confidence": 0.5, "reasoning": "x"})
        with pytest.raises(ValueError, match="missing 'skill_type'"):
            _parse_classification(raw)

    def test_confidence_above_one_raises(self) -> None:
        raw = json.dumps({"skill_type": "general", "confidence": 1.5, "reasoning": "x"})
        with pytest.raises(ValueError, match="out of range"):
            _parse_classification(raw)

    def test_negative_confidence_raises(self) -> None:
        raw = json.dumps({"skill_type": "general", "confidence": -0.1, "reasoning": "x"})
        with pytest.raises(ValueError, match="out of range"):
            _parse_classification(raw)

    def test_unparseable_response_raises(self) -> None:
        with pytest.raises(ValueError, match="Could not parse"):
            _parse_classification("this is not json at all")

    def test_result_is_frozen(self) -> None:
        result = ClassificationResult(skill_type="general", confidence=0.5, reasoning="test")
        with pytest.raises(AttributeError):
            result.skill_type = "changed"  # type: ignore[misc]


class TestSkillClassifier:
    def test_classify_returns_result(self) -> None:
        backend = MagicMock()
        backend.completion.return_value = json.dumps(
            {
                "skill_type": "security-analysis",
                "confidence": 0.95,
                "reasoning": "Scans for vulnerabilities",
            }
        )
        classifier = SkillClassifier(model_backend=backend)
        result = classifier.classify("scan code for OWASP issues")

        assert isinstance(result, ClassificationResult)
        assert result.skill_type == "security-analysis"
        backend.completion.assert_called_once()
        assert backend.completion.call_args.kwargs["operation"] == "classify"

    def test_system_user_prompt_separation(self) -> None:
        backend = MagicMock()
        backend.completion.return_value = json.dumps(
            {
                "skill_type": "general",
                "confidence": 0.8,
                "reasoning": "test",
            }
        )
        classifier = SkillClassifier(model_backend=backend)
        classifier.classify("some skill content")

        kw = backend.completion.call_args.kwargs
        assert "classifier" in kw["system_prompt"].lower()
        assert "some skill content" in kw["user_message"]
        assert "some skill content" not in kw["system_prompt"]

    def test_propagates_backend_error(self) -> None:
        from open_workspace_builder.llm.backend import ModelBackendError

        backend = MagicMock()
        backend.completion.side_effect = ModelBackendError("API down")
        classifier = SkillClassifier(model_backend=backend)
        with pytest.raises(ModelBackendError):
            classifier.classify("anything")


class TestLoadWeightVectors:
    def test_loads_bundled_vectors(self) -> None:
        vectors = load_weight_vectors()
        assert "security-analysis" in vectors
        assert "general" in vectors
        assert len(vectors) >= 10

    def test_all_vectors_sum_to_one(self) -> None:
        vectors = load_weight_vectors()
        for skill_type, weights in vectors.items():
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.01, f"{skill_type} sums to {total}"

    def test_custom_path(self, tmp_path: Path) -> None:
        custom = tmp_path / "custom.yaml"
        custom.write_text(
            "skill_types:\n  custom-type:\n    novelty: 0.25\n    efficiency: 0.25\n"
            "    precision: 0.25\n    defect_rate: 0.25\n",
            encoding="utf-8",
        )
        vectors = load_weight_vectors(custom)
        assert "custom-type" in vectors

    def test_nonexistent_path_raises(self, tmp_path: Path) -> None:
        with pytest.raises(Exception):
            load_weight_vectors(tmp_path / "nope.yaml")
