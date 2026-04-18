"""Test suite generator — creates tailored test prompts for skill evaluation."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from open_workspace_builder._llm_json import parse_json_array
from open_workspace_builder.evaluator.classifier import ClassificationResult

# Bracket-fallback input cap: see note in _llm_json._MAX_FENCE_INPUT.
# Same rationale: bounds regex backtracking cost when LLM responses
# contain unterminated or pathological array-like content.
_MAX_BRACKET_INPUT = 131_072

if TYPE_CHECKING:
    from open_workspace_builder.llm.backend import ModelBackend


@dataclass(frozen=True)
class TestCase:
    """A single test case for skill evaluation."""

    id: str
    description: str
    prompt: str
    expected_behavior: str
    dimensions_tested: tuple[str, ...]


@dataclass(frozen=True)
class TestSuite:
    """A collection of test cases for evaluating a skill."""

    skill_name: str
    skill_type: str
    generated_at: str
    generator_model: str
    test_cases: tuple[TestCase, ...]
    hash: str


def _compute_suite_hash(test_cases: tuple[TestCase, ...] | list[TestCase]) -> str:
    """Compute SHA-256 hash of serialized test cases for identity tracking."""
    cases_data = [
        {
            "id": tc.id,
            "description": tc.description,
            "dimensions_tested": list(tc.dimensions_tested)
            if isinstance(tc.dimensions_tested, tuple)
            else tc.dimensions_tested,
            "expected_behavior": tc.expected_behavior,
            "prompt": tc.prompt,
        }
        for tc in test_cases
    ]
    serialized = json.dumps(cases_data, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


_GENERATION_SYSTEM_PROMPT = """\
You are a test suite generator for evaluating AI skills. Generate test cases \
that cover four evaluation dimensions: novelty, efficiency, precision, and defect_rate.

Requirements:
1. Generate at least 8 test cases total.
2. At least 2 test cases per dimension.
3. Some tests should cover multiple dimensions.
4. Make prompts realistic and representative of how the skill would be used.
5. Include edge cases (ambiguous inputs, out-of-scope requests) to test precision.

Return ONLY a JSON array where each entry has:
- "id": test case ID (e.g., "TC-001")
- "description": what this test evaluates
- "prompt": the actual prompt to send to the AI
- "expected_behavior": description of what a good response looks like
- "dimensions_tested": array of dimension names this test covers
"""

_INCREMENTAL_SYSTEM_PROMPT = """\
You are a test suite generator. Generate ADDITIONAL test cases for newly added \
capabilities of a skill. Cover the four evaluation dimensions: novelty, efficiency, \
precision, and defect_rate.

Return ONLY a JSON array of test case objects with: \
"id", "description", "prompt", "expected_behavior", "dimensions_tested".
"""


class TestSuiteGenerator:
    """Generates tailored test suites for skill evaluation."""

    def __init__(self, model_backend: ModelBackend) -> None:
        """Initialize with model backend for test generation."""
        self._backend = model_backend

    def generate(
        self,
        skill_content: str,
        classification: ClassificationResult,
    ) -> TestSuite:
        """Generate a test suite tailored to the skill's capabilities."""
        user_message = (
            f"## Skill Type: {classification.skill_type}\n\n## SKILL.md Content\n\n{skill_content}"
        )
        response = self._backend.completion(
            operation="generate",
            system_prompt=_GENERATION_SYSTEM_PROMPT,
            user_message=user_message,
            max_tokens=4096,
        )
        test_cases = _parse_test_cases(response)

        suite_hash = _compute_suite_hash(test_cases)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        skill_name = _extract_skill_name(skill_content)

        return TestSuite(
            skill_name=skill_name,
            skill_type=classification.skill_type,
            generated_at=now,
            generator_model="litellm",
            test_cases=tuple(test_cases),
            hash=suite_hash,
        )

    def generate_incremental(
        self,
        skill_content: str,
        classification: ClassificationResult,
        existing_suite: TestSuite,
        new_capabilities: list[str],
    ) -> TestSuite:
        """Generate additional test cases for new capabilities and merge with existing suite."""
        caps = "\n".join(f"- {cap}" for cap in new_capabilities)
        user_message = (
            f"## Skill Type: {classification.skill_type}\n\n"
            f"## SKILL.md Content\n\n{skill_content}\n\n"
            f"## New Capabilities to Test\n\n{caps}"
        )
        response = self._backend.completion(
            operation="generate",
            system_prompt=_INCREMENTAL_SYSTEM_PROMPT,
            user_message=user_message,
            max_tokens=4096,
        )
        new_cases = _parse_test_cases(response)

        existing_ids = {tc.id for tc in existing_suite.test_cases}
        next_id = len(existing_suite.test_cases) + 1
        renumbered: list[TestCase] = []
        for tc in new_cases:
            if tc.id in existing_ids:
                new_id = f"TC-{next_id:03d}"
                next_id += 1
                renumbered.append(
                    TestCase(
                        id=new_id,
                        description=tc.description,
                        prompt=tc.prompt,
                        expected_behavior=tc.expected_behavior,
                        dimensions_tested=tc.dimensions_tested,
                    )
                )
            else:
                renumbered.append(tc)

        merged = list(existing_suite.test_cases) + renumbered
        suite_hash = _compute_suite_hash(merged)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        return TestSuite(
            skill_name=existing_suite.skill_name,
            skill_type=existing_suite.skill_type,
            generated_at=now,
            generator_model=existing_suite.generator_model,
            test_cases=tuple(merged),
            hash=suite_hash,
        )


def _parse_test_cases(response: str) -> list[TestCase]:
    """Parse model response into list of TestCase objects.

    Handles raw JSON arrays and JSON wrapped in code fences via the
    shared `_llm_json.parse_json_array` helper. Falls back to a
    length-capped bracket-scan for LLM responses that embed an array
    inside surrounding prose without a fence.

    Raises ValueError if the response cannot be parsed.
    """
    text = response.strip()
    try:
        parsed = parse_json_array(text, context="test cases response")
    except ValueError:
        parsed = None
    if parsed is not None:
        # Parsed successfully via helper; parse_json_array already
        # narrowed to list at runtime.
        return _convert_to_test_cases([item for item in parsed if isinstance(item, dict)])

    # Bracket fallback for prose-wrapped arrays. Cap the input before
    # regex to bound backtracking on pathological payloads.
    capped = text[:_MAX_BRACKET_INPUT]
    bracket_match = re.search(r"\[.*\]", capped, re.DOTALL)
    if bracket_match:
        maybe = _try_parse_json_array(bracket_match.group(0))
        if maybe is not None:
            return _convert_to_test_cases(maybe)

    raise ValueError(f"Could not parse test cases from response: {text[:200]}")


def _try_parse_json_array(text: str) -> list[dict[str, object]] | None:
    """Try to parse text as a JSON array. Returns None on failure."""
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    return None


def _convert_to_test_cases(data: list[dict[str, object]]) -> list[TestCase]:
    """Convert parsed JSON dicts into TestCase objects."""
    cases: list[TestCase] = []
    for entry in data:
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
    return cases


def _extract_skill_name(skill_content: str) -> str:
    """Extract skill name from SKILL.md content.

    Looks for a top-level heading or returns 'unknown'.
    """
    for line in skill_content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip().lower().replace(" ", "-")
    return "unknown"
