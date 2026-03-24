"""Tests for evaluator persistence: save/load test suites and results."""

from __future__ import annotations

import json
from pathlib import Path


from open_workspace_builder.evaluator.generator import TestCase, TestSuite
from open_workspace_builder.evaluator.persistence import TestSuitePersistence


def _make_suite(skill_name: str = "test-skill") -> TestSuite:
    return TestSuite(
        skill_name=skill_name,
        skill_type="general",
        generated_at="2026-01-01T00:00:00Z",
        generator_model="litellm",
        test_cases=(
            TestCase("TC-001", "desc1", "prompt1", "expected1", ("novelty",)),
            TestCase("TC-002", "desc2", "prompt2", "expected2", ("efficiency", "precision")),
        ),
        hash="sha256:abc123",
    )


class TestSaveSuite:
    def test_creates_directory_and_file(self, tmp_path: Path) -> None:
        p = TestSuitePersistence(str(tmp_path))
        path = p.save_suite(_make_suite(), "src")
        assert Path(path).is_file()

    def test_file_is_valid_json(self, tmp_path: Path) -> None:
        p = TestSuitePersistence(str(tmp_path))
        path = p.save_suite(_make_suite(), "src")
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        assert data["skill_name"] == "test-skill"
        assert len(data["test_cases"]) == 2


class TestLoadSuite:
    def test_roundtrip_preserves_all_fields(self, tmp_path: Path) -> None:
        p = TestSuitePersistence(str(tmp_path))
        original = _make_suite()
        p.save_suite(original, "src")
        loaded = p.load_suite("test-skill", "src")
        assert loaded is not None
        assert loaded.skill_name == original.skill_name
        assert loaded.skill_type == original.skill_type
        assert loaded.hash == original.hash
        assert len(loaded.test_cases) == len(original.test_cases)

    def test_roundtrip_preserves_test_case_details(self, tmp_path: Path) -> None:
        p = TestSuitePersistence(str(tmp_path))
        p.save_suite(_make_suite(), "src")
        loaded = p.load_suite("test-skill", "src")
        assert loaded is not None
        tc = loaded.test_cases[0]
        assert tc.id == "TC-001"
        assert tc.prompt == "prompt1"
        assert tc.dimensions_tested == ("novelty",)

    def test_returns_none_for_nonexistent_skill(self, tmp_path: Path) -> None:
        p = TestSuitePersistence(str(tmp_path))
        assert p.load_suite("nonexistent", "src") is None

    def test_hash_preserved_through_cycle(self, tmp_path: Path) -> None:
        p = TestSuitePersistence(str(tmp_path))
        original = _make_suite()
        p.save_suite(original, "src")
        loaded = p.load_suite("test-skill", "src")
        assert loaded is not None
        assert loaded.hash == original.hash


class TestSaveResult:
    def test_saves_result_alongside_suite(self, tmp_path: Path) -> None:
        p = TestSuitePersistence(str(tmp_path))
        result = {"decision": "incorporate", "score": 7.5}
        path = p.save_result("my-skill", "src", result)
        assert Path(path).is_file()
        assert "result.json" in path


class TestLoadResult:
    def test_roundtrip_result(self, tmp_path: Path) -> None:
        p = TestSuitePersistence(str(tmp_path))
        original = {"decision": "reject", "delta": -0.5}
        p.save_result("my-skill", "src", original)
        loaded = p.load_result("my-skill", "src")
        assert loaded == original

    def test_returns_none_for_nonexistent_result(self, tmp_path: Path) -> None:
        p = TestSuitePersistence(str(tmp_path))
        assert p.load_result("nonexistent", "src") is None
