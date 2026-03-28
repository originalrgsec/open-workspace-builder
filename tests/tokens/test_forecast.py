"""Tests for cost forecasting — linear trend extrapolation with confidence bands."""

from __future__ import annotations

import pytest

from open_workspace_builder.tokens.models import LedgerEntry, TokenCost


def _make_entries(daily_costs: list[tuple[str, float]]) -> list[LedgerEntry]:
    """Create ledger entries with specified dates and total costs."""
    entries = []
    for i, (date, cost) in enumerate(daily_costs):
        entries.append(
            LedgerEntry(
                session_id=f"s{i}",
                project="proj",
                timestamp=f"{date}T10:00:00.000Z",
                total_input=100,
                total_output=500,
                total_cache_creation=0,
                total_cache_read=0,
                cost=TokenCost(input_cost=cost),
                story_id="",
            )
        )
    return entries


class TestSprintForecast:
    """forecast_sprint estimates cost for a planned sprint."""

    def test_basic_forecast(self) -> None:
        from open_workspace_builder.tokens.forecast import forecast_sprint

        # 3 historical sprints with varying cost-per-story
        history = [
            {"sprint": "S10", "cost": 30.0, "stories": 3},   # $10/story
            {"sprint": "S11", "cost": 48.0, "stories": 4},   # $12/story
            {"sprint": "S12", "cost": 40.0, "stories": 5},   # $8/story
        ]
        result = forecast_sprint(history, planned_stories=4)

        assert result.estimated_cost > 0
        assert result.cost_per_story > 0
        assert result.confidence_low < result.estimated_cost
        assert result.confidence_high > result.estimated_cost

    def test_single_sprint_uses_average(self) -> None:
        from open_workspace_builder.tokens.forecast import forecast_sprint

        history = [{"sprint": "S12", "cost": 50.0, "stories": 5}]
        result = forecast_sprint(history, planned_stories=5)

        # With one data point, estimated cost equals the historical cost
        assert result.estimated_cost == pytest.approx(50.0)
        assert result.cost_per_story == pytest.approx(10.0)

    def test_empty_history_returns_zero(self) -> None:
        from open_workspace_builder.tokens.forecast import forecast_sprint

        result = forecast_sprint([], planned_stories=4)
        assert result.estimated_cost == 0.0
        assert result.cost_per_story == 0.0
        assert result.confidence_low == 0.0
        assert result.confidence_high == 0.0

    def test_story_count_scaling(self) -> None:
        from open_workspace_builder.tokens.forecast import forecast_sprint

        history = [
            {"sprint": "S10", "cost": 30.0, "stories": 3},
            {"sprint": "S11", "cost": 40.0, "stories": 4},
        ]
        result_small = forecast_sprint(history, planned_stories=2)
        result_large = forecast_sprint(history, planned_stories=8)

        assert result_large.estimated_cost > result_small.estimated_cost


class TestMonthlyForecast:
    """forecast_monthly extrapolates monthly cost from ledger entries."""

    def test_extrapolates_from_partial_month(self) -> None:
        from open_workspace_builder.tokens.forecast import forecast_monthly

        # 14 days of data in March, ~$5/day
        entries = _make_entries(
            [(f"2026-03-{d:02d}", 5.0) for d in range(15, 29)]
        )
        result = forecast_monthly(entries, current_date="2026-03-28")

        # 14 days × $5 = $70 actual, extrapolated to 31 days ≈ $155
        assert result.month_to_date > 0
        assert result.projected_total > result.month_to_date
        assert result.days_elapsed == 28
        assert result.days_in_month == 31

    def test_empty_entries(self) -> None:
        from open_workspace_builder.tokens.forecast import forecast_monthly

        result = forecast_monthly([], current_date="2026-03-28")
        assert result.month_to_date == 0.0
        assert result.projected_total == 0.0


class TestForecastResult:
    """SprintForecast and MonthlyForecast are frozen dataclasses."""

    def test_sprint_forecast_frozen(self) -> None:
        from open_workspace_builder.tokens.forecast import SprintForecast

        f = SprintForecast(
            estimated_cost=50.0,
            cost_per_story=10.0,
            confidence_low=40.0,
            confidence_high=60.0,
            data_points=3,
        )
        with pytest.raises(AttributeError):
            f.estimated_cost = 99.0  # type: ignore[misc]

    def test_monthly_forecast_frozen(self) -> None:
        from open_workspace_builder.tokens.forecast import MonthlyForecast

        f = MonthlyForecast(
            month_to_date=70.0,
            projected_total=155.0,
            daily_average=5.0,
            days_elapsed=14,
            days_in_month=31,
        )
        with pytest.raises(AttributeError):
            f.month_to_date = 0.0  # type: ignore[misc]
