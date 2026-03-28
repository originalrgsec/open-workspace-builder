"""Tests for budget alerts — threshold checking against month-to-date cost."""

from __future__ import annotations

import pytest

from open_workspace_builder.tokens.models import LedgerEntry, TokenCost


def _make_entry(day: int, cost: float, month: int = 3) -> LedgerEntry:
    return LedgerEntry(
        session_id=f"s{month}{day}",
        project="proj",
        timestamp=f"2026-{month:02d}-{day:02d}T10:00:00.000Z",
        total_input=100,
        total_output=500,
        total_cache_creation=0,
        total_cache_read=0,
        cost=TokenCost(input_cost=cost),
    )


class TestBudgetCheck:
    """check_budget compares month-to-date cost against a configured threshold."""

    def test_under_budget(self) -> None:
        from open_workspace_builder.tokens.budget import check_budget

        entries = [_make_entry(d, 5.0) for d in range(1, 11)]  # $50 MTD
        result = check_budget(entries, threshold=200.0, current_date="2026-03-10")

        assert not result.exceeded
        assert result.month_to_date == pytest.approx(50.0)
        assert result.threshold == 200.0
        assert result.remaining == pytest.approx(150.0)

    def test_over_budget(self) -> None:
        from open_workspace_builder.tokens.budget import check_budget

        entries = [_make_entry(d, 25.0) for d in range(1, 11)]  # $250 MTD
        result = check_budget(entries, threshold=200.0, current_date="2026-03-10")

        assert result.exceeded
        assert result.month_to_date == pytest.approx(250.0)
        assert result.remaining == pytest.approx(-50.0)

    def test_exact_threshold(self) -> None:
        from open_workspace_builder.tokens.budget import check_budget

        entries = [_make_entry(d, 20.0) for d in range(1, 11)]  # $200 MTD
        result = check_budget(entries, threshold=200.0, current_date="2026-03-10")

        assert not result.exceeded  # at threshold is OK
        assert result.remaining == pytest.approx(0.0)

    def test_filters_to_current_month(self) -> None:
        from open_workspace_builder.tokens.budget import check_budget

        entries = [
            _make_entry(28, 100.0, month=2),  # February — should be excluded
            _make_entry(1, 10.0, month=3),
            _make_entry(2, 10.0, month=3),
        ]
        result = check_budget(entries, threshold=200.0, current_date="2026-03-10")

        assert result.month_to_date == pytest.approx(20.0)

    def test_empty_entries(self) -> None:
        from open_workspace_builder.tokens.budget import check_budget

        result = check_budget([], threshold=200.0, current_date="2026-03-10")
        assert not result.exceeded
        assert result.month_to_date == 0.0
        assert result.remaining == pytest.approx(200.0)

    def test_pct_used(self) -> None:
        from open_workspace_builder.tokens.budget import check_budget

        entries = [_make_entry(d, 10.0) for d in range(1, 11)]  # $100 MTD
        result = check_budget(entries, threshold=200.0, current_date="2026-03-10")

        assert result.pct_used == pytest.approx(50.0)


class TestBudgetResult:
    """BudgetResult is a frozen dataclass."""

    def test_frozen(self) -> None:
        from open_workspace_builder.tokens.budget import BudgetResult

        r = BudgetResult(
            month_to_date=100.0,
            threshold=200.0,
            remaining=100.0,
            pct_used=50.0,
            exceeded=False,
        )
        with pytest.raises(AttributeError):
            r.exceeded = True  # type: ignore[misc]
