"""Cost forecasting — linear trend extrapolation with confidence bands."""

from __future__ import annotations

import calendar
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_workspace_builder.tokens.models import LedgerEntry


def _validate_date(date_str: str) -> None:
    """Validate that a date string is in YYYY-MM-DD format."""
    from datetime import date as date_cls

    try:
        date_cls.fromisoformat(date_str)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"Invalid date format: {date_str!r}. Expected YYYY-MM-DD."
        ) from exc


@dataclass(frozen=True)
class SprintForecast:
    """Estimated cost for a planned sprint."""

    estimated_cost: float
    cost_per_story: float
    confidence_low: float
    confidence_high: float
    data_points: int


@dataclass(frozen=True)
class MonthlyForecast:
    """Month-to-date actual and projected monthly total."""

    month_to_date: float
    projected_total: float
    daily_average: float
    days_elapsed: int
    days_in_month: int


def forecast_sprint(
    history: list[dict[str, object]],
    planned_stories: int,
) -> SprintForecast:
    """Estimate cost for a sprint using historical cost-per-story.

    Args:
        history: List of dicts with keys 'sprint', 'cost', 'stories'.
        planned_stories: Number of stories planned for the upcoming sprint.

    Returns:
        SprintForecast with estimate and confidence bands based on variance.
    """
    if not history:
        return SprintForecast(
            estimated_cost=0.0,
            cost_per_story=0.0,
            confidence_low=0.0,
            confidence_high=0.0,
            data_points=0,
        )

    # Compute cost-per-story for each historical sprint.
    per_story_costs = [
        float(h.get("cost", 0)) / int(h["stories"])
        for h in history
        if h.get("stories", 0) > 0 and h.get("cost") is not None
    ]

    if not per_story_costs:
        return SprintForecast(
            estimated_cost=0.0,
            cost_per_story=0.0,
            confidence_low=0.0,
            confidence_high=0.0,
            data_points=0,
        )

    mean_per_story = sum(per_story_costs) / len(per_story_costs)
    estimated = mean_per_story * planned_stories

    # Confidence band from standard deviation (1 sigma).
    if len(per_story_costs) >= 2:
        variance = sum((c - mean_per_story) ** 2 for c in per_story_costs) / (
            len(per_story_costs) - 1
        )
        std_dev = math.sqrt(variance)
        margin = std_dev * planned_stories
    else:
        # Single data point — use 20% margin.
        margin = estimated * 0.2

    return SprintForecast(
        estimated_cost=estimated,
        cost_per_story=mean_per_story,
        confidence_low=max(0.0, estimated - margin),
        confidence_high=estimated + margin,
        data_points=len(per_story_costs),
    )


def forecast_monthly(
    entries: list[LedgerEntry],
    current_date: str,
) -> MonthlyForecast:
    """Extrapolate monthly cost from ledger entries in the current month.

    Args:
        entries: List of LedgerEntry objects.
        current_date: Current date as YYYY-MM-DD string.

    Returns:
        MonthlyForecast with MTD actual and projected total.
    """
    if not entries:
        return MonthlyForecast(
            month_to_date=0.0,
            projected_total=0.0,
            daily_average=0.0,
            days_elapsed=0,
            days_in_month=0,
        )

    _validate_date(current_date)
    year = int(current_date[:4])
    month = int(current_date[5:7])
    day = int(current_date[8:10])
    days_in_month = calendar.monthrange(year, month)[1]

    # Filter to current month and sum costs.
    month_prefix = current_date[:7]  # YYYY-MM
    mtd_cost = sum(
        e.cost.total
        for e in entries
        if e.timestamp[:7] == month_prefix
    )

    daily_avg = mtd_cost / day if day > 0 else 0.0
    projected = daily_avg * days_in_month

    return MonthlyForecast(
        month_to_date=mtd_cost,
        projected_total=projected,
        daily_average=daily_avg,
        days_elapsed=day,
        days_in_month=days_in_month,
    )
