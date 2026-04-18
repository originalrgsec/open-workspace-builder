"""Tests for OWB-S139: Pyright pre-commit hook gate.

Tests the pyright-gate.py script's output parser and budget comparison.
The script runs `uv run pyright`, parses the summary line, and fails
the hook when the observed error count exceeds the frozen budget from
DRN-078 (96 as of v1.15.0).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_script_path = Path(__file__).resolve().parent.parent / "scripts" / "pyright-gate.py"
_spec = importlib.util.spec_from_file_location("pyright_gate", _script_path)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules["pyright_gate"] = _mod
_spec.loader.exec_module(_mod)

parse_error_count = _mod.parse_error_count
check_budget = _mod.check_budget


class TestParseErrorCount:
    """AC-3: Budget enforcement relies on accurate parsing of pyright summary."""

    @pytest.mark.parametrize(
        "line,expected",
        [
            ("96 errors, 0 warnings, 0 informations", 96),
            ("0 errors, 0 warnings, 0 informations", 0),
            ("1 error, 2 warnings, 3 informations", 1),
            ("150 errors, 0 warnings, 0 informations", 150),
        ],
    )
    def test_parse_valid_summary(self, line: str, expected: int) -> None:
        assert parse_error_count(line) == expected

    def test_parse_finds_summary_in_full_output(self) -> None:
        output = """
        /path/to/file.py:10:20 - error: Something broke
        /path/to/other.py:5:10 - error: Also broke
        2 errors, 0 warnings, 0 informations
        """
        assert parse_error_count(output) == 2

    def test_parse_returns_none_on_missing_summary(self) -> None:
        assert parse_error_count("pyright failed to start") is None

    def test_parse_returns_none_on_empty(self) -> None:
        assert parse_error_count("") is None


class TestCheckBudget:
    """AC-3: Hook fails with clear message naming budget and current count."""

    def test_under_budget_passes(self) -> None:
        passed, msg = check_budget(count=90, budget=96)
        assert passed is True
        assert "96" in msg
        assert "90" in msg

    def test_at_budget_passes(self) -> None:
        passed, msg = check_budget(count=96, budget=96)
        assert passed is True
        assert "96" in msg

    def test_over_budget_fails(self) -> None:
        passed, msg = check_budget(count=97, budget=96)
        assert passed is False
        assert "96" in msg
        assert "97" in msg
        assert "budget" in msg.lower()

    def test_over_budget_mentions_drn(self) -> None:
        """Regression message should point operator to the decision record."""
        _, msg = check_budget(count=100, budget=96)
        assert "DRN-078" in msg

    def test_zero_budget_zero_count_passes(self) -> None:
        passed, _ = check_budget(count=0, budget=0)
        assert passed is True

    def test_zero_budget_any_count_fails(self) -> None:
        passed, _ = check_budget(count=1, budget=0)
        assert passed is False
