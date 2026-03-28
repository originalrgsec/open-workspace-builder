"""Terminal report formatting for token consumption data."""

from __future__ import annotations

from open_workspace_builder.tokens.models import TokenReport


def _fmt_tokens(n: int) -> str:
    """Format a token count with comma separators."""
    return f"{n:,}"


def _fmt_cost(c: float) -> str:
    """Format a dollar amount."""
    return f"${c:,.2f}"


def _fmt_pct(p: float) -> str:
    """Format a percentage."""
    return f"{p * 100:.1f}%"


def format_report(report: TokenReport) -> str:
    """Format a TokenReport as a human-readable terminal report."""
    lines: list[str] = []

    lines.append("=" * 70)
    lines.append("Token Consumption Report")
    lines.append(f"Period: {report.period_start} to {report.period_end}")
    lines.append(f"Sessions: {report.session_count}  Messages: {report.message_count}")
    lines.append("=" * 70)

    # Totals
    lines.append("")
    lines.append("TOTALS")
    lines.append("-" * 40)
    lines.append(f"  Input tokens:          {_fmt_tokens(report.total_input)}")
    lines.append(f"  Output tokens:         {_fmt_tokens(report.total_output)}")
    lines.append(f"  Cache creation tokens: {_fmt_tokens(report.total_cache_creation)}")
    lines.append(f"  Cache read tokens:     {_fmt_tokens(report.total_cache_read)}")
    lines.append(f"  API-equivalent cost:   {_fmt_cost(report.total_cost.total)}")

    # Cost breakdown
    lines.append("")
    lines.append("COST BREAKDOWN")
    lines.append("-" * 40)
    lines.append(f"  Input:       {_fmt_cost(report.total_cost.input_cost)}")
    lines.append(f"  Output:      {_fmt_cost(report.total_cost.output_cost)}")
    lines.append(f"  Cache write: {_fmt_cost(report.total_cost.cache_write_cost)}")
    lines.append(f"  Cache read:  {_fmt_cost(report.total_cost.cache_read_cost)}")

    # Cache efficiency
    if report.cache_efficiency.total_cache_reads > 0:
        lines.append("")
        lines.append("CACHE EFFICIENCY")
        lines.append("-" * 40)
        eff = report.cache_efficiency
        lines.append(f"  Cache hit ratio:       {_fmt_pct(eff.cache_hit_ratio)}")
        lines.append(f"  Cost reduction:        {_fmt_pct(eff.cost_reduction_pct)}")
        lines.append(f"  Total cache reads:     {_fmt_tokens(eff.total_cache_reads)}")
        lines.append(f"  Total cache writes:    {_fmt_tokens(eff.total_cache_writes)}")

    # Per-model breakdown
    if report.by_model:
        lines.append("")
        lines.append("BY MODEL")
        lines.append("-" * 70)
        lines.append(
            f"  {'Model':<30} {'Input':>10} {'Output':>10} {'Cost':>12}"
        )
        lines.append(f"  {'-' * 30} {'-' * 10} {'-' * 10} {'-' * 12}")
        for m in report.by_model:
            lines.append(
                f"  {m.model:<30} {_fmt_tokens(m.input_tokens):>10} "
                f"{_fmt_tokens(m.output_tokens):>10} {_fmt_cost(m.cost.total):>12}"
            )

    # Per-project breakdown
    if report.by_project:
        lines.append("")
        lines.append("BY PROJECT")
        lines.append("-" * 70)
        lines.append(
            f"  {'Project':<30} {'Sessions':>8} {'Output':>10} {'Cost':>12}"
        )
        lines.append(f"  {'-' * 30} {'-' * 8} {'-' * 10} {'-' * 12}")
        for p in report.by_project:
            lines.append(
                f"  {p.project:<30} {p.session_count:>8} "
                f"{_fmt_tokens(p.output_tokens):>10} {_fmt_cost(p.cost.total):>12}"
            )

    # Per-day breakdown
    if report.by_day:
        lines.append("")
        lines.append("BY DAY")
        lines.append("-" * 70)
        lines.append(
            f"  {'Date':<12} {'Input':>10} {'Output':>10} {'Cache Read':>12} {'Cost':>12}"
        )
        lines.append(
            f"  {'-' * 12} {'-' * 10} {'-' * 10} {'-' * 12} {'-' * 12}"
        )
        for d in report.by_day:
            lines.append(
                f"  {d.date:<12} {_fmt_tokens(d.input_tokens):>10} "
                f"{_fmt_tokens(d.output_tokens):>10} "
                f"{_fmt_tokens(d.cache_read_tokens):>12} "
                f"{_fmt_cost(d.cost.total):>12}"
            )

    lines.append("")
    return "\n".join(lines)


def format_report_json(report: TokenReport) -> dict:
    """Convert a TokenReport to a JSON-serializable dict."""
    return {
        "period_start": report.period_start,
        "period_end": report.period_end,
        "sessions": report.session_count,
        "messages": report.message_count,
        "totals": {
            "input_tokens": report.total_input,
            "output_tokens": report.total_output,
            "cache_creation_tokens": report.total_cache_creation,
            "cache_read_tokens": report.total_cache_read,
            "cost": {
                "input": report.total_cost.input_cost,
                "output": report.total_cost.output_cost,
                "cache_write": report.total_cost.cache_write_cost,
                "cache_read": report.total_cost.cache_read_cost,
                "total": report.total_cost.total,
            },
        },
        "cache_efficiency": {
            "hit_ratio": report.cache_efficiency.cache_hit_ratio,
            "cost_reduction_pct": report.cache_efficiency.cost_reduction_pct,
            "total_reads": report.cache_efficiency.total_cache_reads,
            "total_writes": report.cache_efficiency.total_cache_writes,
        },
        "by_model": [
            {
                "model": m.model,
                "input_tokens": m.input_tokens,
                "output_tokens": m.output_tokens,
                "cache_creation_tokens": m.cache_creation_tokens,
                "cache_read_tokens": m.cache_read_tokens,
                "cost": m.cost.total,
            }
            for m in report.by_model
        ],
        "by_project": [
            {
                "project": p.project,
                "sessions": p.session_count,
                "input_tokens": p.input_tokens,
                "output_tokens": p.output_tokens,
                "cost": p.cost.total,
            }
            for p in report.by_project
        ],
        "by_day": [
            {
                "date": d.date,
                "input_tokens": d.input_tokens,
                "output_tokens": d.output_tokens,
                "cache_read_tokens": d.cache_read_tokens,
                "cost": d.cost.total,
            }
            for d in report.by_day
        ],
    }
