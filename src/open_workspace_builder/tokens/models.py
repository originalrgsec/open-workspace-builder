"""Frozen dataclasses for token consumption data."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TokenUsage:
    """Token counts from a single assistant message."""

    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    timestamp: str = ""


@dataclass(frozen=True)
class ModelPricing:
    """API pricing per million tokens for a single model."""

    input_per_mtok: float
    output_per_mtok: float
    cache_write_per_mtok: float
    cache_read_per_mtok: float


@dataclass(frozen=True)
class TokenCost:
    """Calculated cost breakdown for a set of token usage records."""

    input_cost: float = 0.0
    output_cost: float = 0.0
    cache_write_cost: float = 0.0
    cache_read_cost: float = 0.0

    @property
    def total(self) -> float:
        return self.input_cost + self.output_cost + self.cache_write_cost + self.cache_read_cost


@dataclass(frozen=True)
class CacheEfficiency:
    """Cache utilization metrics."""

    total_cache_reads: int = 0
    total_cache_writes: int = 0
    total_input_tokens: int = 0
    cache_hit_ratio: float = 0.0
    cost_reduction_pct: float = 0.0


@dataclass(frozen=True)
class SessionSummary:
    """Aggregated token data for one Claude Code session."""

    session_id: str
    project: str
    start_time: str
    end_time: str
    message_count: int
    models_used: tuple[str, ...] = ()
    total_input: int = 0
    total_output: int = 0
    total_cache_creation: int = 0
    total_cache_read: int = 0
    cost: TokenCost = field(default_factory=TokenCost)


@dataclass(frozen=True)
class ModelBreakdown:
    """Token totals and cost for a single model."""

    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    cost: TokenCost = field(default_factory=TokenCost)


@dataclass(frozen=True)
class ProjectBreakdown:
    """Token totals and cost for a single project."""

    project: str
    session_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    cost: TokenCost = field(default_factory=TokenCost)


@dataclass(frozen=True)
class DailyBreakdown:
    """Token totals and cost for a single day."""

    date: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    cost: TokenCost = field(default_factory=TokenCost)


@dataclass(frozen=True)
class TokenReport:
    """Complete token consumption report."""

    period_start: str
    period_end: str
    total_input: int = 0
    total_output: int = 0
    total_cache_creation: int = 0
    total_cache_read: int = 0
    total_cost: TokenCost = field(default_factory=TokenCost)
    by_model: tuple[ModelBreakdown, ...] = ()
    by_project: tuple[ProjectBreakdown, ...] = ()
    by_day: tuple[DailyBreakdown, ...] = ()
    cache_efficiency: CacheEfficiency = field(default_factory=CacheEfficiency)
    session_count: int = 0
    message_count: int = 0
