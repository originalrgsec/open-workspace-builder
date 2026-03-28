"""Tests for token consumption data models."""

from __future__ import annotations

import pytest

from open_workspace_builder.tokens.models import (
    CacheEfficiency,
    ModelBreakdown,
    ProjectBreakdown,
    SessionSummary,
    TokenCost,
    TokenReport,
    TokenUsage,
)


class TestTokenUsage:
    def test_frozen(self) -> None:
        usage = TokenUsage(model="claude-opus-4-6", input_tokens=100)
        with pytest.raises(AttributeError):
            usage.input_tokens = 200  # type: ignore[misc]

    def test_defaults(self) -> None:
        usage = TokenUsage(model="test")
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.cache_creation_tokens == 0
        assert usage.cache_read_tokens == 0
        assert usage.timestamp == ""

    def test_all_fields(self) -> None:
        usage = TokenUsage(
            model="claude-opus-4-6",
            input_tokens=100,
            output_tokens=200,
            cache_creation_tokens=300,
            cache_read_tokens=400,
            timestamp="2026-03-28T10:00:00.000Z",
        )
        assert usage.model == "claude-opus-4-6"
        assert usage.input_tokens == 100
        assert usage.output_tokens == 200
        assert usage.cache_creation_tokens == 300
        assert usage.cache_read_tokens == 400


class TestTokenCost:
    def test_total(self) -> None:
        cost = TokenCost(input_cost=1.0, output_cost=2.0, cache_write_cost=0.5, cache_read_cost=0.1)
        assert cost.total == pytest.approx(3.6)

    def test_total_defaults(self) -> None:
        cost = TokenCost()
        assert cost.total == 0.0

    def test_frozen(self) -> None:
        cost = TokenCost(input_cost=1.0)
        with pytest.raises(AttributeError):
            cost.input_cost = 2.0  # type: ignore[misc]


class TestCacheEfficiency:
    def test_defaults(self) -> None:
        ce = CacheEfficiency()
        assert ce.cache_hit_ratio == 0.0
        assert ce.cost_reduction_pct == 0.0


class TestSessionSummary:
    def test_construction(self) -> None:
        session = SessionSummary(
            session_id="abc123",
            project="open-workspace-builder",
            start_time="2026-03-28T10:00:00.000Z",
            end_time="2026-03-28T12:00:00.000Z",
            message_count=50,
            models_used=("claude-opus-4-6",),
            total_input=1000,
            total_output=5000,
        )
        assert session.session_id == "abc123"
        assert session.project == "open-workspace-builder"
        assert session.message_count == 50
        assert session.models_used == ("claude-opus-4-6",)


class TestTokenReport:
    def test_empty_report(self) -> None:
        report = TokenReport(period_start="2026-03-01", period_end="2026-03-31")
        assert report.session_count == 0
        assert report.message_count == 0
        assert report.total_cost.total == 0.0
        assert report.by_model == ()
        assert report.by_project == ()
        assert report.by_day == ()

    def test_report_with_breakdowns(self) -> None:
        model_bd = ModelBreakdown(
            model="claude-opus-4-6",
            input_tokens=100,
            output_tokens=200,
            cost=TokenCost(input_cost=0.5, output_cost=5.0),
        )
        project_bd = ProjectBreakdown(
            project="owb",
            session_count=3,
            input_tokens=100,
            output_tokens=200,
        )
        report = TokenReport(
            period_start="2026-03-01",
            period_end="2026-03-31",
            by_model=(model_bd,),
            by_project=(project_bd,),
            session_count=3,
            message_count=50,
        )
        assert len(report.by_model) == 1
        assert report.by_model[0].model == "claude-opus-4-6"
        assert len(report.by_project) == 1
        assert report.by_project[0].project == "owb"
