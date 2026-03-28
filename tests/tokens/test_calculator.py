"""Tests for token cost calculator."""

from __future__ import annotations

import pytest

from open_workspace_builder.tokens.calculator import (
    calculate_cache_efficiency,
    calculate_cost,
    build_report,
)
from open_workspace_builder.tokens.models import (
    ModelPricing,
    TokenUsage,
)


class TestCalculateCost:
    def test_basic_cost(self) -> None:
        usage = TokenUsage(
            model="claude-opus-4-6",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        pricing = ModelPricing(
            input_per_mtok=5.0,
            output_per_mtok=25.0,
            cache_write_per_mtok=6.25,
            cache_read_per_mtok=0.50,
        )
        cost = calculate_cost(usage, pricing)
        assert cost.input_cost == pytest.approx(5.0)
        assert cost.output_cost == pytest.approx(25.0)
        assert cost.total == pytest.approx(30.0)

    def test_cache_costs(self) -> None:
        usage = TokenUsage(
            model="claude-opus-4-6",
            input_tokens=0,
            output_tokens=0,
            cache_creation_tokens=1_000_000,
            cache_read_tokens=10_000_000,
        )
        pricing = ModelPricing(
            input_per_mtok=5.0,
            output_per_mtok=25.0,
            cache_write_per_mtok=6.25,
            cache_read_per_mtok=0.50,
        )
        cost = calculate_cost(usage, pricing)
        assert cost.cache_write_cost == pytest.approx(6.25)
        assert cost.cache_read_cost == pytest.approx(5.0)
        assert cost.total == pytest.approx(11.25)

    def test_zero_tokens(self) -> None:
        usage = TokenUsage(model="test")
        pricing = ModelPricing(5.0, 25.0, 6.25, 0.50)
        cost = calculate_cost(usage, pricing)
        assert cost.total == 0.0

    def test_fractional_tokens(self) -> None:
        """Cost should be proportional for sub-million token counts."""
        usage = TokenUsage(model="test", input_tokens=500_000, output_tokens=250_000)
        pricing = ModelPricing(
            input_per_mtok=10.0,
            output_per_mtok=20.0,
            cache_write_per_mtok=0.0,
            cache_read_per_mtok=0.0,
        )
        cost = calculate_cost(usage, pricing)
        assert cost.input_cost == pytest.approx(5.0)
        assert cost.output_cost == pytest.approx(5.0)


class TestCalculateCacheEfficiency:
    def test_high_cache_hit(self) -> None:
        usages = [
            TokenUsage(
                model="opus",
                input_tokens=100,
                cache_creation_tokens=1000,
                cache_read_tokens=9000,
            ),
        ]
        eff = calculate_cache_efficiency(usages)
        assert eff.total_cache_reads == 9000
        assert eff.total_cache_writes == 1000
        assert eff.total_input_tokens == 100
        # hit ratio = reads / (reads + writes + input)
        assert eff.cache_hit_ratio == pytest.approx(9000 / (9000 + 1000 + 100))

    def test_no_cache(self) -> None:
        usages = [
            TokenUsage(model="test", input_tokens=1000),
        ]
        eff = calculate_cache_efficiency(usages)
        assert eff.cache_hit_ratio == 0.0
        assert eff.total_cache_reads == 0

    def test_empty_usages(self) -> None:
        eff = calculate_cache_efficiency([])
        assert eff.cache_hit_ratio == 0.0


class TestBuildReport:
    def _make_usages(self) -> list[tuple[str, str, list[TokenUsage]]]:
        """Return (project, session_id, usages) tuples for testing."""
        return [
            (
                "project-a",
                "session-1",
                [
                    TokenUsage(
                        model="claude-opus-4-6",
                        input_tokens=100,
                        output_tokens=500,
                        cache_creation_tokens=2000,
                        cache_read_tokens=10000,
                        timestamp="2026-03-15T10:00:00.000Z",
                    ),
                    TokenUsage(
                        model="claude-opus-4-6",
                        input_tokens=50,
                        output_tokens=200,
                        cache_creation_tokens=0,
                        cache_read_tokens=12000,
                        timestamp="2026-03-15T11:00:00.000Z",
                    ),
                ],
            ),
            (
                "project-b",
                "session-2",
                [
                    TokenUsage(
                        model="claude-sonnet-4-6",
                        input_tokens=80,
                        output_tokens=300,
                        cache_creation_tokens=1500,
                        cache_read_tokens=8000,
                        timestamp="2026-03-16T09:00:00.000Z",
                    ),
                ],
            ),
        ]

    def test_report_totals(self) -> None:
        data = self._make_usages()
        pricing = {
            "claude-opus-4-6": ModelPricing(5.0, 25.0, 6.25, 0.50),
            "claude-sonnet-4-6": ModelPricing(3.0, 15.0, 3.75, 0.30),
        }
        report = build_report(data, pricing)
        assert report.total_input == 100 + 50 + 80
        assert report.total_output == 500 + 200 + 300
        assert report.session_count == 2
        assert report.message_count == 3

    def test_report_model_breakdown(self) -> None:
        data = self._make_usages()
        pricing = {
            "claude-opus-4-6": ModelPricing(5.0, 25.0, 6.25, 0.50),
            "claude-sonnet-4-6": ModelPricing(3.0, 15.0, 3.75, 0.30),
        }
        report = build_report(data, pricing)
        models = {m.model: m for m in report.by_model}
        assert "claude-opus-4-6" in models
        assert "claude-sonnet-4-6" in models
        assert models["claude-opus-4-6"].input_tokens == 150
        assert models["claude-sonnet-4-6"].input_tokens == 80

    def test_report_project_breakdown(self) -> None:
        data = self._make_usages()
        pricing = {
            "claude-opus-4-6": ModelPricing(5.0, 25.0, 6.25, 0.50),
            "claude-sonnet-4-6": ModelPricing(3.0, 15.0, 3.75, 0.30),
        }
        report = build_report(data, pricing)
        projects = {p.project: p for p in report.by_project}
        assert "project-a" in projects
        assert "project-b" in projects
        assert projects["project-a"].session_count == 1
        assert projects["project-b"].session_count == 1

    def test_report_daily_breakdown(self) -> None:
        data = self._make_usages()
        pricing = {
            "claude-opus-4-6": ModelPricing(5.0, 25.0, 6.25, 0.50),
            "claude-sonnet-4-6": ModelPricing(3.0, 15.0, 3.75, 0.30),
        }
        report = build_report(data, pricing)
        days = {d.date: d for d in report.by_day}
        assert "2026-03-15" in days
        assert "2026-03-16" in days

    def test_report_date_filtering(self) -> None:
        data = self._make_usages()
        pricing = {
            "claude-opus-4-6": ModelPricing(5.0, 25.0, 6.25, 0.50),
            "claude-sonnet-4-6": ModelPricing(3.0, 15.0, 3.75, 0.30),
        }
        report = build_report(data, pricing, since="20260316", until="20260316")
        # Only session-2 from project-b on 2026-03-16 should be included
        assert report.message_count == 1
        assert report.total_input == 80

    def test_report_empty_data(self) -> None:
        report = build_report([], {})
        assert report.session_count == 0
        assert report.message_count == 0
        assert report.total_cost.total == 0.0

    def test_report_unknown_model_excluded_from_cost(self) -> None:
        data = [
            (
                "proj",
                "sess",
                [
                    TokenUsage(
                        model="unknown-model",
                        input_tokens=1000,
                        output_tokens=5000,
                        timestamp="2026-03-28T10:00:00.000Z",
                    ),
                ],
            ),
        ]
        report = build_report(data, {})
        assert report.total_input == 1000
        assert report.total_output == 5000
        # Cost should be zero since model has no pricing
        assert report.total_cost.total == 0.0

    def test_report_period_bounds(self) -> None:
        data = self._make_usages()
        pricing = {
            "claude-opus-4-6": ModelPricing(5.0, 25.0, 6.25, 0.50),
            "claude-sonnet-4-6": ModelPricing(3.0, 15.0, 3.75, 0.30),
        }
        report = build_report(data, pricing)
        assert report.period_start == "2026-03-15"
        assert report.period_end == "2026-03-16"

    def test_cost_matches_manual_calculation(self) -> None:
        """Verify cost calculation against hand-computed values."""
        data = [
            (
                "proj",
                "sess",
                [
                    TokenUsage(
                        model="claude-opus-4-6",
                        input_tokens=100_000,
                        output_tokens=50_000,
                        cache_creation_tokens=200_000,
                        cache_read_tokens=1_000_000,
                        timestamp="2026-03-28T10:00:00.000Z",
                    ),
                ],
            ),
        ]
        pricing = {
            "claude-opus-4-6": ModelPricing(5.0, 25.0, 6.25, 0.50),
        }
        report = build_report(data, pricing)
        # Manual: input = 0.1M * $5 = $0.50
        #         output = 0.05M * $25 = $1.25
        #         cache_write = 0.2M * $6.25 = $1.25
        #         cache_read = 1.0M * $0.50 = $0.50
        #         total = $3.50
        assert report.total_cost.input_cost == pytest.approx(0.50)
        assert report.total_cost.output_cost == pytest.approx(1.25)
        assert report.total_cost.cache_write_cost == pytest.approx(1.25)
        assert report.total_cost.cache_read_cost == pytest.approx(0.50)
        assert report.total_cost.total == pytest.approx(3.50)
