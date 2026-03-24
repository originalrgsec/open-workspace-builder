"""Test suite and evaluation result persistence."""

from __future__ import annotations

import json
from pathlib import Path

from open_workspace_builder.evaluator.generator import TestCase, TestSuite


class TestSuitePersistence:
    """Persist and load test suites and evaluation results."""

    def __init__(self, base_path: str) -> None:
        """Initialize with base path for skill metadata storage."""
        self._base = Path(base_path)

    def save_suite(self, suite: TestSuite, source: str) -> str:
        """Save test suite as JSON. Returns file path."""
        suite_dir = self._suite_dir(suite.skill_name, source)
        suite_dir.mkdir(parents=True, exist_ok=True)
        file_path = suite_dir / "suite.json"
        file_path.write_text(
            json.dumps(_suite_to_dict(suite), indent=2, sort_keys=False),
            encoding="utf-8",
        )
        return str(file_path)

    def load_suite(self, skill_name: str, source: str) -> TestSuite | None:
        """Load persisted test suite. Returns None if not found."""
        file_path = self._suite_dir(skill_name, source) / "suite.json"
        if not file_path.is_file():
            return None
        raw = json.loads(file_path.read_text(encoding="utf-8"))
        return _dict_to_suite(raw)

    def save_result(self, skill_name: str, source: str, result: dict[str, object]) -> str:
        """Save evaluation result as JSON alongside the test suite."""
        suite_dir = self._suite_dir(skill_name, source)
        suite_dir.mkdir(parents=True, exist_ok=True)
        file_path = suite_dir / "result.json"
        file_path.write_text(
            json.dumps(result, indent=2, sort_keys=False),
            encoding="utf-8",
        )
        return str(file_path)

    def load_result(self, skill_name: str, source: str) -> dict[str, object] | None:
        """Load persisted evaluation result. Returns None if not found."""
        file_path = self._suite_dir(skill_name, source) / "result.json"
        if not file_path.is_file():
            return None
        return json.loads(file_path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]

    def _suite_dir(self, skill_name: str, source: str) -> Path:
        """Compute directory path for a skill's test suite."""
        return self._base / source / ".skill-meta" / "tests" / skill_name


def _suite_to_dict(suite: TestSuite) -> dict[str, object]:
    """Serialize a TestSuite to a dict suitable for JSON."""
    return {
        "skill_name": suite.skill_name,
        "skill_type": suite.skill_type,
        "generated_at": suite.generated_at,
        "generator_model": suite.generator_model,
        "hash": suite.hash,
        "test_cases": [
            {
                "id": tc.id,
                "description": tc.description,
                "prompt": tc.prompt,
                "expected_behavior": tc.expected_behavior,
                "dimensions_tested": list(tc.dimensions_tested),
            }
            for tc in suite.test_cases
        ],
    }


def _dict_to_suite(data: dict[str, object]) -> TestSuite:
    """Deserialize a dict into a TestSuite."""
    raw_cases = data.get("test_cases", [])
    cases: list[TestCase] = []
    if isinstance(raw_cases, list):
        for entry in raw_cases:
            if isinstance(entry, dict):
                dims = entry.get("dimensions_tested", [])
                cases.append(
                    TestCase(
                        id=str(entry.get("id", "")),
                        description=str(entry.get("description", "")),
                        prompt=str(entry.get("prompt", "")),
                        expected_behavior=str(entry.get("expected_behavior", "")),
                        dimensions_tested=tuple(str(d) for d in dims)
                        if isinstance(dims, list)
                        else (str(dims),),
                    )
                )
    return TestSuite(
        skill_name=str(data.get("skill_name", "")),
        skill_type=str(data.get("skill_type", "")),
        generated_at=str(data.get("generated_at", "")),
        generator_model=str(data.get("generator_model", "")),
        test_cases=tuple(cases),
        hash=str(data.get("hash", "")),
    )
