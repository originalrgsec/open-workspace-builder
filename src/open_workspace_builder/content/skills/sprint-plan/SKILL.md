---
name: sprint-plan
description: >-
  Automate vault artifact updates for sprint open and sprint close. Use this
  skill when the user says 'open sprint', 'plan sprint', 'close sprint',
  'sprint planning', or when coordinating multi-file sprint documentation updates.
---

# Sprint Planning Orchestration

This skill automates the multi-file vault artifact updates required to open and close a sprint. A typical sprint boundary touches 10+ files (story frontmatter, status.md, SDR, bootstrap, retro-log, session logs). This skill makes those updates repeatable and complete.

## When to Run

- Operator says "open sprint", "plan sprint", "start sprint N", or "sprint planning"
- Operator says "close sprint", "sprint done", "finish sprint", or "wrap up the sprint"
- When coordinating bulk documentation updates across stories, status, SDR, and bootstrap

---

## Part 1: Sprint Open

### Step 1: Gather Sprint Parameters

Prompt the operator for:

1. **Sprint number** — the sequential sprint identifier (e.g., "Sprint 9")
2. **Sprint theme** — one-line description of what the sprint delivers
3. **Story list** — which stories are assigned to this sprint (by ID, e.g., OWB-S066, OWB-S068)
4. **Phase assignments** — if the project has multiple phases, which phase each story belongs to

If the operator provides all parameters in the initial request (e.g., "open Sprint 9 with stories S066, S068, S070"), skip the prompts for information already provided.

### Step 2: Load Current State

Read the following files to understand the current project state:

1. **Bootstrap** (`_bootstrap.md`) — current project phase and next action
2. **Status** (`status.md` in the project folder) — current sprint, blockers, recent activity
3. **SDR** — sprint plan section showing previous sprint assignments
4. **Story files** — frontmatter for each assigned story (check `status`, `sprint`, `depends-on`)

### Step 3: Pre-Sprint Validation

Run the following checks. Each produces a PASS, WARN, or SKIP result. Validation failures are warnings, not blockers — the operator can override and proceed.

#### 3a: Prerequisite Stories Complete

For each assigned story, read its `depends-on` frontmatter field. If any prerequisite story has a status other than `complete`, report:

```
WARN: Story {id} depends on {dep_id} which is status: {status} (not complete)
```

If no stories have `depends-on` fields, report SKIP.

#### 3b: Clean Working Tree

Check the code repository for uncommitted changes:

```bash
git status --porcelain
```

If there are uncommitted changes on the default branch, report:

```
WARN: Repository has uncommitted changes — consider committing or stashing before sprint open
```

#### 3c: Test Suite Green

Run the project's test suite:

```bash
# Detect and run the appropriate test command
# Python: uv run pytest
# Node: npm test
# Go: go test ./...
# Makefile: make test
```

Report the result. If tests fail, report WARN with failure count. Do not block sprint open on test failures — the operator may be aware of pre-existing issues.

#### 3d: Stale Branches

Check for unmerged branches from the previous sprint:

```bash
git branch --no-merged main
```

If stale branches exist, list them as a warning. The operator may need to clean them up or they may be intentionally long-lived.

#### Validation Summary

Present a summary table:

```
## Pre-Sprint Validation

| Check                    | Result | Details                           |
|--------------------------|--------|-----------------------------------|
| Prerequisites complete   | PASS   | All 3 dependencies satisfied      |
| Clean working tree       | WARN   | 2 uncommitted files               |
| Test suite               | PASS   | 147 passed, 0 failed              |
| Stale branches           | SKIP   | No unmerged branches              |
```

Ask: "Proceed with sprint open?" If the operator confirms (or if all checks passed), continue to Step 4.

### Step 4: Update Story Frontmatter

For each story assigned to the sprint, update its frontmatter:

- Set `sprint: <sprint_number>`
- Set `status: planned`

Do not overwrite other frontmatter fields. Read the file, modify only the target fields, and write it back.

Report each file updated:

```
Updated stories/OWB-S066-inline-policy.md: sprint → 9, status → planned
Updated stories/OWB-S068-license-audit.md: sprint → 9, status → planned
```

### Step 5: Update Status File

Update the project's `status.md`:

1. Set `last-updated` in frontmatter to today's date
2. Update the "Current Phase" section if the phase has changed
3. Add a sprint plan table under "Recent Activity" or a dedicated "Current Sprint" section:

```markdown
## Current Sprint — Sprint <N>: <theme>

| Story | Title | Status |
|-------|-------|--------|
| OWB-S066 | Inline policy enforcement rules | planned |
| OWB-S068 | License audit command | planned |
```

4. Update "Next Actions" to reflect sprint goals

### Step 6: Update SDR Sprint Plan

Locate the SDR file (typically `docs/sdr.md` or in the vault under the project folder). Find the sprint plan section and add the new sprint entry:

```markdown
### Sprint <N>: <theme>

Stories: OWB-S066, OWB-S068, ...

Goals:
- <goal derived from sprint theme and story titles>
```

If no SDR exists or has no sprint plan section, skip this step and report SKIP.

### Step 7: Update Bootstrap

Update `_bootstrap.md` project manifest table:

- Update the project's "Phase" column if changed
- Update the "Next Action" column to reflect the sprint theme

### Step 8: Cost Estimate

Invoke the **token-analysis** skill's sprint planning workflow. This pulls trailing cost data from the previous 2 sprints, calculates cost-per-story, and estimates the upcoming sprint's cost based on the planned story count.

If the token-analysis skill is not available, run `owb metrics tokens --format json` for the last 30 days and calculate the estimate manually. If no historical data exists, report SKIP.

Present the cost estimate table as part of the sprint open summary.

### Step 9: Sprint Open Summary

Present the complete summary:

```
## Sprint <N> Opened — <theme>

### Files Updated
- stories/OWB-S066-inline-policy.md (sprint, status)
- stories/OWB-S068-license-audit.md (sprint, status)
- status.md (sprint plan, last-updated)
- docs/sdr.md (sprint plan section)
- _bootstrap.md (phase, next action)

### Validation Results
- Prerequisites: PASS
- Working tree: WARN (2 uncommitted files)
- Tests: PASS (147/147)
- Stale branches: SKIP

### Stories in Sprint <N>
| ID | Title | Dependencies | Status |
|----|-------|-------------|--------|
| OWB-S066 | Inline policy rules | none | planned |
| OWB-S068 | License audit | S066 | planned |
```

---

## Part 2: Sprint Close

### Step 1: Run Sprint Completion Checklist

Invoke the sprint-complete skill if available. If not available, run the equivalent checks inline:

1. **Tests green** — run the test suite and confirm all tests pass
2. **Project docs updated** — prompt the operator to confirm PRD/ADR/SDR/threat model are current
3. **CHANGELOG updated** — check that CHANGELOG.md has an entry for this version
4. **Release manifest written** — check for `docs/releases/v<version>.md`
5. **Metrics recorded** — check if metrics system is active; if so, prompt for confirmation

If any item fails, report the failure and ask the operator whether to proceed with sprint close or address the issue first.

### Step 2: Retrospective

Invoke the retro skill if available. If not available, prompt the operator:

"Sprint close requires a retrospective. Would you like to:"
1. Write a full retro now (standalone file)
2. Write a lightweight retro (inline in retro-log)
3. Skip for now and file later (creates a reminder in status.md)

If the operator chooses option 3, add a "Pending Retro" item to the project's status.md blockers section.

### Step 3: Update Story Frontmatter

For each story delivered in the sprint, update its frontmatter:

- Set `status: complete`
- Set `completed: <today's date>` if the field exists in the template

Prompt the operator: "Which stories were delivered? (Enter story IDs, or 'all' for all planned stories)"

If some stories were not completed, leave their status unchanged and note them as carried over.

### Step 4: Update Status File

Update the project's `status.md`:

1. Set `last-updated` to today's date
2. Move the sprint plan table to "Recent Activity" with final statuses
3. Update "Current Phase" if appropriate
4. Clear or update "Blockers"
5. Set "Next Actions" to reflect what comes after this sprint

### Step 5: Update Bootstrap

Update `_bootstrap.md`:

- Update the project's "Phase" column to reflect post-sprint state
- Update "Next Action" to the next planned work

### Step 6: Write Session Log

Create a session log file in the project's `sessions/` folder using the session-log template:

```yaml
---
type: session
date: <today>
tool: code
project: <project_name>
tags: [sprint-close, sprint-<N>]
---

# Session: <today> — Sprint <N> Close

## Context
Sprint <N> (<theme>) close and documentation updates.

## Work Done
- Completed sprint checklist (all items PASS)
- Updated <count> story files to status: complete
- Updated status.md with sprint results
- Updated bootstrap manifest
- Ran vault audit (<issues> issues found)

## Decisions Made
<from operator input during close>

## State Changes
- Sprint <N> → closed
- Stories completed: <list>
- Stories carried over: <list or "none">

## Open Items
- <any items from retro or checklist>
```

### Step 7: Run Vault Audit

Invoke the vault-audit skill. Sprint close involves bulk edits that can introduce broken wiki links or stale references. Report the audit results.

If the vault-audit skill is not available, run a basic link check:

```bash
# Find broken wiki links in recently modified files
grep -r '\[\[' <vault_path> --include='*.md' | grep -v '_templates/'
```

### Step 8: Record Metrics

If the project has an active metrics system (look for a metrics directory, metrics configuration, or pipeline metrics files), prompt the operator to confirm metrics have been recorded for this sprint.

If no metrics system is detected, skip this step.

### Step 9: Sprint Close Summary

Present the final summary:

```
## Sprint <N> Closed — <theme>

### Completion Checklist
| Item | Status |
|------|--------|
| Tests green | PASS |
| Docs updated | PASS |
| CHANGELOG | PASS |
| Release manifest | PASS |
| Metrics | SKIP |

### Stories Delivered
| ID | Title | Status |
|----|-------|--------|
| OWB-S066 | Inline policy rules | complete |
| OWB-S068 | License audit | complete |

### Carried Over
(none)

### Retrospective
RETRO-<NNN> filed at self/retros/RETRO-<NNN>-sprint-<N>.md

### Session Log
sessions/<today>-sprint-<N>-close.md

### Vault Audit
<N> issues found, <N> warnings
```

---

## Error Handling

- If a file listed for update does not exist, skip it and report SKIP (do not create files this skill does not own)
- If story files cannot be found by ID, prompt the operator for the file path
- If the vault path cannot be determined, ask the operator to provide it
- If any automated check (tests, git status) fails to run, report the error and continue with remaining steps
- All file writes should be reported before execution so the operator can confirm

## Related Skills

- **sprint-complete** — sprint completion checklist (called during close)
- **retro** — retrospective scaffolding (called during close)
- **write-story** — story file generation (used during planning)
- **vault-audit** — vault integrity checking (called during close)
