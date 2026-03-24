"""Shared data types for the evaluator package."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TestExecutionResult:
    """Result of executing a single test case against a skill or baseline."""

    test_case_id: str
    prompt_sent: str
    response_text: str
    token_count: int | None = None
    latency_ms: float | None = None
