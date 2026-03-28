"""Budget alerts — threshold checking against month-to-date cost."""

from __future__ import annotations

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
class BudgetResult:
    """Result of a budget threshold check."""

    month_to_date: float
    threshold: float
    remaining: float
    pct_used: float
    exceeded: bool


def check_budget(
    entries: list[LedgerEntry],
    threshold: float,
    current_date: str,
) -> BudgetResult:
    """Check month-to-date cost against a configured threshold.

    Args:
        entries: List of LedgerEntry objects (any month).
        threshold: Monthly budget threshold in dollars.
        current_date: Current date as YYYY-MM-DD string.

    Returns:
        BudgetResult with MTD cost, remaining budget, and exceeded flag.
    """
    _validate_date(current_date)
    month_prefix = current_date[:7]  # YYYY-MM

    mtd = sum(
        e.cost.total
        for e in entries
        if e.timestamp[:7] == month_prefix
    )

    remaining = threshold - mtd
    pct_used = (mtd / threshold * 100) if threshold > 0 else 0.0

    return BudgetResult(
        month_to_date=mtd,
        threshold=threshold,
        remaining=remaining,
        pct_used=pct_used,
        exceeded=mtd > threshold,
    )
