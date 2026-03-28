---
name: token-analysis
description: >-
  Analyze token consumption and API-equivalent costs from Claude Code sessions.
  Use this skill during sprint close (write cost section to retro, update
  tracking sheet), sprint planning (show trailing cost trend and estimate),
  monthly review (full breakdown with charts), or ad-hoc cost analysis. Wraps
  the `owb metrics tokens` CLI commands.
---

# Token Consumption Analysis

This skill interprets token consumption data from Claude Code sessions using the `owb metrics tokens` CLI. It supports three workflow integration points: sprint close, sprint planning, and monthly review.

## When to Run

- Sprint close: "record costs", "token report for this sprint", "update the cost sheet"
- Sprint planning: "estimate costs", "what did last sprint cost", "cost trend"
- Monthly review: "monthly cost report", "refresh the cost sheet", "cost analysis"
- Ad-hoc: "how much am I spending", "token usage", "cost breakdown"

## Prerequisites

- `owb metrics tokens` CLI is available (installed with OWB)
- For Google Sheets export: `owb auth google` has been run and a Sheet ID is configured
- Session data exists in `~/.claude/projects/`

---

## Workflow 1: Sprint Close — Cost Recording

**Trigger:** During sprint close, after stories are delivered and before the retro is written.

### Step 1: Capture Sprint Token Data

Run the token report for the sprint date range:

```bash
owb metrics tokens --since <sprint_start_YYYYMMDD> --until <sprint_end_YYYYMMDD> --format json
```

Parse the JSON output to extract:
- Total API-equivalent cost
- Per-project breakdown (identify the primary project for this sprint)
- Per-model breakdown (Opus vs Sonnet vs Haiku)
- Cache efficiency (hit ratio, cost reduction percentage)
- Message count and session count

### Step 2: Write Cost Section to Retro

Add a "Token Consumption" section to the sprint retrospective. Format:

```markdown
## Token Consumption — Sprint <N>

| Metric | Value |
|--------|-------|
| API-equivalent cost | $<total> |
| Sessions | <count> |
| Messages | <count> |
| Cache hit ratio | <pct>% |
| Cost reduction from caching | <pct>% |

### Model Mix
| Model | Output Tokens | Cost |
|-------|--------------|------|
| claude-opus-4-6 | <tokens> | $<cost> |
| claude-sonnet-4-6 | <tokens> | $<cost> |
| claude-haiku-4-5 | <tokens> | $<cost> |

### Comparison to Previous Sprint
| Metric | Sprint <N-1> | Sprint <N> | Delta |
|--------|-------------|-----------|-------|
| Total cost | $<prev> | $<current> | <+/- pct>% |
| Output tokens | <prev> | <current> | <+/- pct>% |
| Cache hit ratio | <prev>% | <current>% | <+/- pp> |
```

To populate the comparison, read the previous sprint's retro for its token consumption section. If no previous data exists, omit the comparison table.

### Step 3: Update Tracking Sheet

If Google Sheets is configured, push the sprint data:

```bash
owb metrics export --format gsheets --sheet-id <configured_sheet_id> --since <sprint_start> --until <sprint_end>
```

Report whether the export succeeded or failed. If it fails (no auth, no sheet ID), log a warning and continue — the Sheet update is not a sprint-close blocker.

---

## Workflow 2: Sprint Planning — Cost Estimation

**Trigger:** During sprint planning, after stories are selected.

### Step 1: Pull Trailing Cost Data

Run reports for the previous 2 sprints:

```bash
owb metrics tokens --since <sprint_N-2_start> --until <sprint_N-1_end> --format json
```

Extract per-sprint totals. If sprint date ranges are not known, fall back to the last 30 days.

### Step 2: Calculate Cost-Per-Story

Divide each sprint's total cost by the number of stories delivered in that sprint. If story counts are available from the vault status files, use those. Otherwise, ask the operator.

### Step 3: Estimate Next Sprint Cost

Multiply the trailing average cost-per-story by the number of stories planned for the upcoming sprint.

Present:

```markdown
## Cost Estimate — Sprint <N>

| Metric | Sprint <N-2> | Sprint <N-1> | Avg |
|--------|-------------|-------------|-----|
| Total cost | $<cost> | $<cost> | $<avg> |
| Stories delivered | <count> | <count> | <avg> |
| Cost per story | $<cps> | $<cps> | $<avg_cps> |

**Estimated cost for Sprint <N>:** $<avg_cps × planned_story_count>
(based on <planned_story_count> planned stories × $<avg_cps> avg cost/story)

**Note:** This is a rough estimate. Actual costs depend on story complexity,
model selection, and cache efficiency. The estimate assumes similar work
patterns to the trailing sprints.
```

---

## Workflow 3: Monthly Review

**Trigger:** End of month, or when the operator requests a full cost review.

### Step 1: Generate Full Monthly Report

```bash
owb metrics tokens --since <month_start_YYYYMMDD> --until <month_end_YYYYMMDD> --format json
```

### Step 2: Refresh Tracking Sheet

```bash
owb metrics export --format gsheets --sheet-id <configured_sheet_id> --since <month_start> --until <month_end>
```

### Step 3: Produce Summary

Write a summary suitable for inclusion in a monthly status update:

```markdown
## Monthly Token Report — <Month Year>

**Total API-equivalent cost:** $<total>
**Subscription cost:** $200 (Max 20x plan)
**Effective savings:** $<total - 200> (<pct>% subsidy)

### Daily Average
- Active days: <count>
- Average daily cost: $<avg>
- Peak day: $<max> (<date>)

### Project Breakdown
| Project | Cost | % of Total |
|---------|------|-----------|
| <project> | $<cost> | <pct>% |

### Model Mix
| Model | Cost | % of Total |
|-------|------|-----------|
| <model> | $<cost> | <pct>% |

### Cache Efficiency
- Hit ratio: <pct>%
- Cost reduction: <pct>%

### Trend
<Compare to previous month if data exists. Note direction of cost,
cache efficiency, and model mix changes.>
```

---

## Error Handling

- If `owb metrics tokens` is not available, instruct the operator to ensure OWB is installed
- If no session data exists for the requested date range, report "No data" and skip
- If Google Sheets export fails, log the error and continue — never block a sprint workflow on Sheet export
- If previous sprint data is not available for comparison, omit comparison sections

## Related Skills

- **sprint-complete** — calls this skill at Item 5 (Metrics Recorded)
- **sprint-plan** — calls this skill for cost estimation during planning
- **retro** — the cost section is written into the retro artifact
