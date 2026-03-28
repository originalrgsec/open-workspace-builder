"""Cost calculation and report building from token usage data."""

from __future__ import annotations

from collections import defaultdict

from open_workspace_builder.tokens.models import (
    CacheEfficiency,
    DailyBreakdown,
    ModelBreakdown,
    ModelPricing,
    ProjectBreakdown,
    TokenCost,
    TokenReport,
    TokenUsage,
)


def calculate_cost(usage: TokenUsage, pricing: ModelPricing) -> TokenCost:
    """Calculate API-equivalent cost for a single usage record."""
    return TokenCost(
        input_cost=usage.input_tokens * pricing.input_per_mtok / 1_000_000,
        output_cost=usage.output_tokens * pricing.output_per_mtok / 1_000_000,
        cache_write_cost=usage.cache_creation_tokens * pricing.cache_write_per_mtok / 1_000_000,
        cache_read_cost=usage.cache_read_tokens * pricing.cache_read_per_mtok / 1_000_000,
    )


def _add_costs(a: TokenCost, b: TokenCost) -> TokenCost:
    """Return a new TokenCost that is the sum of two costs."""
    return TokenCost(
        input_cost=a.input_cost + b.input_cost,
        output_cost=a.output_cost + b.output_cost,
        cache_write_cost=a.cache_write_cost + b.cache_write_cost,
        cache_read_cost=a.cache_read_cost + b.cache_read_cost,
    )


def calculate_cache_efficiency(usages: list[TokenUsage]) -> CacheEfficiency:
    """Calculate cache utilization metrics across a set of usage records."""
    total_reads = sum(u.cache_read_tokens for u in usages)
    total_writes = sum(u.cache_creation_tokens for u in usages)
    total_input = sum(u.input_tokens for u in usages)
    total_all = total_reads + total_writes + total_input

    if total_all == 0:
        return CacheEfficiency()

    hit_ratio = total_reads / total_all

    # Cost reduction: what would input cost without caching vs with caching.
    # Without caching, all tokens are input tokens at full price.
    # With caching, reads are 0.1x and writes are 1.25x.
    # This is model-independent for the ratio calculation.
    uncached_cost = total_all  # normalized units
    cached_cost = total_input + (total_writes * 1.25) + (total_reads * 0.1)
    reduction = (uncached_cost - cached_cost) / uncached_cost if uncached_cost > 0 else 0.0

    return CacheEfficiency(
        total_cache_reads=total_reads,
        total_cache_writes=total_writes,
        total_input_tokens=total_input,
        cache_hit_ratio=hit_ratio,
        cost_reduction_pct=reduction,
    )


def _date_from_timestamp(timestamp: str) -> str:
    """Extract YYYY-MM-DD from an ISO timestamp string."""
    if not timestamp or len(timestamp) < 10:
        return "unknown"
    return timestamp[:10]


def _matches_date_filter(
    timestamp: str, since: str | None, until: str | None
) -> bool:
    """Check if a timestamp falls within the date filter range.

    since/until are in YYYYMMDD format. Inclusive on both ends.
    """
    if not since and not until:
        return True

    date_str = _date_from_timestamp(timestamp).replace("-", "")

    if since and date_str < since:
        return False
    if until and date_str > until:
        return False
    return True


def build_report(
    session_data: list[tuple[str, str, list[TokenUsage]]],
    pricing: dict[str, ModelPricing],
    since: str | None = None,
    until: str | None = None,
) -> TokenReport:
    """Build a complete TokenReport from parsed session data.

    Args:
        session_data: List of (project_name, session_id, usages) tuples.
        pricing: Model name -> pricing mapping.
        since: Optional start date filter (YYYYMMDD, inclusive).
        until: Optional end date filter (YYYYMMDD, inclusive).
    """
    # Collect all filtered usages with their project context.
    all_usages: list[tuple[str, TokenUsage]] = []
    session_count = 0
    sessions_seen: set[str] = set()

    for project, session_id, usages in session_data:
        session_had_usage = False
        for usage in usages:
            if not _matches_date_filter(usage.timestamp, since, until):
                continue
            all_usages.append((project, usage))
            session_had_usage = True
        if session_had_usage and session_id not in sessions_seen:
            sessions_seen.add(session_id)
            session_count += 1

    if not all_usages:
        return TokenReport(
            period_start=since or "",
            period_end=until or "",
        )

    # Aggregate totals.
    total_input = 0
    total_output = 0
    total_cache_creation = 0
    total_cache_read = 0
    total_cost = TokenCost()

    # Per-model accumulators.
    model_input: dict[str, int] = defaultdict(int)
    model_output: dict[str, int] = defaultdict(int)
    model_cache_create: dict[str, int] = defaultdict(int)
    model_cache_read: dict[str, int] = defaultdict(int)
    model_cost: dict[str, TokenCost] = defaultdict(TokenCost)

    # Per-project accumulators.
    project_input: dict[str, int] = defaultdict(int)
    project_output: dict[str, int] = defaultdict(int)
    project_cache_create: dict[str, int] = defaultdict(int)
    project_cache_read: dict[str, int] = defaultdict(int)
    project_cost: dict[str, TokenCost] = defaultdict(TokenCost)
    project_sessions: dict[str, set[str]] = defaultdict(set)

    # Per-day accumulators.
    day_input: dict[str, int] = defaultdict(int)
    day_output: dict[str, int] = defaultdict(int)
    day_cache_create: dict[str, int] = defaultdict(int)
    day_cache_read: dict[str, int] = defaultdict(int)
    day_cost: dict[str, TokenCost] = defaultdict(TokenCost)

    all_dates: list[str] = []
    raw_usages: list[TokenUsage] = []

    for project, usage in all_usages:
        raw_usages.append(usage)
        total_input += usage.input_tokens
        total_output += usage.output_tokens
        total_cache_creation += usage.cache_creation_tokens
        total_cache_read += usage.cache_read_tokens

        model_pricing = pricing.get(usage.model)
        cost = calculate_cost(usage, model_pricing) if model_pricing else TokenCost()
        total_cost = _add_costs(total_cost, cost)

        model_input[usage.model] += usage.input_tokens
        model_output[usage.model] += usage.output_tokens
        model_cache_create[usage.model] += usage.cache_creation_tokens
        model_cache_read[usage.model] += usage.cache_read_tokens
        model_cost[usage.model] = _add_costs(model_cost[usage.model], cost)

        project_input[project] += usage.input_tokens
        project_output[project] += usage.output_tokens
        project_cache_create[project] += usage.cache_creation_tokens
        project_cache_read[project] += usage.cache_read_tokens
        project_cost[project] = _add_costs(project_cost[project], cost)

        date = _date_from_timestamp(usage.timestamp)
        all_dates.append(date)
        day_input[date] += usage.input_tokens
        day_output[date] += usage.output_tokens
        day_cache_create[date] += usage.cache_creation_tokens
        day_cache_read[date] += usage.cache_read_tokens
        day_cost[date] = _add_costs(day_cost[date], cost)

    # Track which sessions belong to which project (for session count).
    for project, session_id, usages in session_data:
        for usage in usages:
            if _matches_date_filter(usage.timestamp, since, until):
                project_sessions[project].add(session_id)
                break

    # Build breakdown tuples.
    by_model = tuple(
        ModelBreakdown(
            model=model,
            input_tokens=model_input[model],
            output_tokens=model_output[model],
            cache_creation_tokens=model_cache_create[model],
            cache_read_tokens=model_cache_read[model],
            cost=model_cost[model],
        )
        for model in sorted(model_input.keys())
    )

    by_project = tuple(
        ProjectBreakdown(
            project=proj,
            session_count=len(project_sessions.get(proj, set())),
            input_tokens=project_input[proj],
            output_tokens=project_output[proj],
            cache_creation_tokens=project_cache_create[proj],
            cache_read_tokens=project_cache_read[proj],
            cost=project_cost[proj],
        )
        for proj in sorted(project_input.keys())
    )

    by_day = tuple(
        DailyBreakdown(
            date=date,
            input_tokens=day_input[date],
            output_tokens=day_output[date],
            cache_creation_tokens=day_cache_create[date],
            cache_read_tokens=day_cache_read[date],
            cost=day_cost[date],
        )
        for date in sorted(day_input.keys())
    )

    sorted_dates = sorted(set(all_dates))
    period_start = sorted_dates[0] if sorted_dates else (since or "")
    period_end = sorted_dates[-1] if sorted_dates else (until or "")

    return TokenReport(
        period_start=period_start,
        period_end=period_end,
        total_input=total_input,
        total_output=total_output,
        total_cache_creation=total_cache_creation,
        total_cache_read=total_cache_read,
        total_cost=total_cost,
        by_model=by_model,
        by_project=by_project,
        by_day=by_day,
        cache_efficiency=calculate_cache_efficiency(raw_usages),
        session_count=session_count,
        message_count=len(all_usages),
    )
