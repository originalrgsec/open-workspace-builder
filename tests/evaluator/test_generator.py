"""Tests for evaluator generator: test suite generation and parsing."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from open_workspace_builder.evaluator.classifier import ClassificationResult
from open_workspace_builder.evaluator.generator import (
    TestCase,
    TestSuite,
    TestSuiteGenerator,
    _compute_suite_hash,
    _convert_to_test_cases,
    _extract_skill_name,
    _parse_test_cases,
)

SAMPLE_CASES_JSON = json.dumps(
    [
        {
            "id": "TC-001",
            "description": "Test basic output",
            "prompt": "Write a greeting",
            "expected_behavior": "A polite greeting",
            "dimensions_tested": ["novelty", "precision"],
        },
        {
            "id": "TC-002",
            "description": "Test efficiency",
            "prompt": "Summarize in one sentence",
            "expected_behavior": "Concise summary",
            "dimensions_tested": ["efficiency"],
        },
    ]
)

SAMPLE_CLASSIFICATION = ClassificationResult(
    skill_type="document-generation",
    confidence=0.9,
    reasoning="Generates documents",
)


def _make_mock_backend(response: str) -> MagicMock:
    backend = MagicMock()
    backend.completion.return_value = response
    return backend


class TestTestCase:
    def test_frozen(self) -> None:
        tc = TestCase("TC-001", "desc", "prompt", "expected", ("novelty",))
        with pytest.raises(AttributeError):
            tc.id = "changed"  # type: ignore[misc]

    def test_fields(self) -> None:
        tc = TestCase("TC-001", "desc", "prompt", "expected", ("novelty", "precision"))
        assert tc.id == "TC-001"
        assert tc.dimensions_tested == ("novelty", "precision")


class TestTestSuite:
    def test_frozen(self) -> None:
        ts = TestSuite("s", "t", "now", "model", (), "hash")
        with pytest.raises(AttributeError):
            ts.skill_name = "changed"  # type: ignore[misc]


class TestComputeSuiteHash:
    def test_deterministic(self) -> None:
        cases = [TestCase("TC-001", "d", "p", "e", ("novelty",))]
        h1 = _compute_suite_hash(cases)
        h2 = _compute_suite_hash(cases)
        assert h1 == h2

    def test_starts_with_sha256(self) -> None:
        cases = [TestCase("TC-001", "d", "p", "e", ("novelty",))]
        assert _compute_suite_hash(cases).startswith("sha256:")

    def test_changes_with_different_cases(self) -> None:
        c1 = [TestCase("TC-001", "d1", "p1", "e1", ("novelty",))]
        c2 = [TestCase("TC-001", "d2", "p2", "e2", ("novelty",))]
        assert _compute_suite_hash(c1) != _compute_suite_hash(c2)


class TestParseTestCases:
    def test_raw_json_array(self) -> None:
        cases = _parse_test_cases(SAMPLE_CASES_JSON)
        assert len(cases) == 2
        assert cases[0].id == "TC-001"

    def test_json_in_code_fence(self) -> None:
        fenced = f"```json\n{SAMPLE_CASES_JSON}\n```"
        cases = _parse_test_cases(fenced)
        assert len(cases) == 2

    def test_invalid_response_raises(self) -> None:
        with pytest.raises(ValueError, match="Could not parse"):
            _parse_test_cases("not json at all")

    def test_dimensions_as_tuple(self) -> None:
        cases = _parse_test_cases(SAMPLE_CASES_JSON)
        assert isinstance(cases[0].dimensions_tested, tuple)


class TestConvertToTestCases:
    def test_basic_conversion(self) -> None:
        data = [
            {
                "id": "TC-001",
                "description": "d",
                "prompt": "p",
                "expected_behavior": "e",
                "dimensions_tested": ["novelty"],
            }
        ]
        cases = _convert_to_test_cases(data)
        assert len(cases) == 1
        assert cases[0].id == "TC-001"

    def test_missing_fields_default_empty(self) -> None:
        data = [{}]
        cases = _convert_to_test_cases(data)
        assert cases[0].id == ""
        assert cases[0].description == ""


class TestExtractSkillName:
    def test_from_heading(self) -> None:
        assert _extract_skill_name("# My Cool Skill\n\nDetails") == "my-cool-skill"

    def test_unknown_when_no_heading(self) -> None:
        assert _extract_skill_name("No heading here") == "unknown"


class TestTestSuiteGenerator:
    def test_generate_returns_suite(self) -> None:
        backend = _make_mock_backend(SAMPLE_CASES_JSON)
        gen = TestSuiteGenerator(backend)
        suite = gen.generate("# Test Skill\nContent", SAMPLE_CLASSIFICATION)
        assert isinstance(suite, TestSuite)
        assert suite.skill_name == "test-skill"
        assert suite.skill_type == "document-generation"
        assert len(suite.test_cases) == 2

    def test_generate_uses_generate_operation(self) -> None:
        backend = _make_mock_backend(SAMPLE_CASES_JSON)
        gen = TestSuiteGenerator(backend)
        gen.generate("# Skill\nContent", SAMPLE_CLASSIFICATION)
        assert backend.completion.call_args[1]["operation"] == "generate"

    def test_generate_sends_skill_content_in_user_message(self) -> None:
        backend = _make_mock_backend(SAMPLE_CASES_JSON)
        gen = TestSuiteGenerator(backend)
        gen.generate("# Skill\nContent here", SAMPLE_CLASSIFICATION)
        assert "Content here" in backend.completion.call_args[1]["user_message"]

    def test_generate_incremental_merges(self) -> None:
        existing = TestSuite(
            skill_name="s",
            skill_type="general",
            generated_at="",
            generator_model="m",
            test_cases=(TestCase("TC-001", "d", "p", "e", ("novelty",)),),
            hash="sha256:abc",
        )
        new_cases = json.dumps(
            [
                {
                    "id": "TC-002",
                    "description": "new",
                    "prompt": "np",
                    "expected_behavior": "ne",
                    "dimensions_tested": ["efficiency"],
                }
            ]
        )
        backend = _make_mock_backend(new_cases)
        gen = TestSuiteGenerator(backend)
        merged = gen.generate_incremental(
            "# Skill\nContent", SAMPLE_CLASSIFICATION, existing, ["new feature"]
        )
        assert len(merged.test_cases) == 2
        assert merged.test_cases[0].id == "TC-001"
        assert merged.test_cases[1].id == "TC-002"

    def test_incremental_renumbers_conflicts(self) -> None:
        existing = TestSuite(
            skill_name="s",
            skill_type="general",
            generated_at="",
            generator_model="m",
            test_cases=(TestCase("TC-001", "d", "p", "e", ("novelty",)),),
            hash="sha256:abc",
        )
        conflicting = json.dumps(
            [
                {
                    "id": "TC-001",
                    "description": "conflict",
                    "prompt": "cp",
                    "expected_behavior": "ce",
                    "dimensions_tested": ["precision"],
                }
            ]
        )
        backend = _make_mock_backend(conflicting)
        gen = TestSuiteGenerator(backend)
        merged = gen.generate_incremental("# Skill\nC", SAMPLE_CLASSIFICATION, existing, ["cap"])
        ids = [tc.id for tc in merged.test_cases]
        assert "TC-001" in ids
        assert "TC-002" in ids
        assert len(set(ids)) == 2

    def test_hash_recomputed_on_merge(self) -> None:
        existing = TestSuite(
            skill_name="s",
            skill_type="general",
            generated_at="",
            generator_model="m",
            test_cases=(TestCase("TC-001", "d", "p", "e", ("novelty",)),),
            hash="sha256:original",
        )
        backend = _make_mock_backend(
            json.dumps(
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
        )
        gen = TestSuiteGenerator(backend)
        merged = gen.generate_incremental("# S\nC", SAMPLE_CLASSIFICATION, existing, ["cap"])
        assert merged.hash != "sha256:original"
        assert merged.hash.startswith("sha256:")
