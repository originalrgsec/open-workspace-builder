---
name: sprint-complete
description: >-
  Walk through the full sprint completion checklist to ensure no steps are
  missed. Use this skill when finishing a sprint, closing a release, or when
  the user says 'sprint complete', 'close the sprint', or 'release checklist'.
---

# Sprint Completion Orchestration

This skill walks through the development-process sprint completion checklist, running automated checks where possible and prompting the operator for judgment items.

## When to Run

- Sprint is finished and the final PR is about to merge
- Operator says "sprint complete", "close the sprint", "release checklist", or "are we done"
- Before tagging a release

## Checklist Execution

Work through each item sequentially. For each item, report its status as PASS, FAIL, SKIP, or NEEDS REVIEW. Produce a summary table at the end.

### Item 1: Stories Complete — All AC Green

**Automated check.** Run the project test suite and verify all tests pass.

```bash
# Detect test runner and execute
# Python: uv run pytest or pytest
# Node: npm test
# Go: go test ./...
```

If tests fail, report the failures and stop. The sprint cannot close with failing tests.

Also check for a pipeline smoke test. Per the integration verification policy, the application's primary command must be exercised end-to-end before sprint closure. If a smoke test exists, run it. If not, warn the operator that a smoke test is missing and ask whether to proceed.

### Item 2: Project Docs Updated

**Judgment item — prompt the operator.**

Ask: "Have project documents (PRD, ADR, SDR, threat model) been updated to reflect design changes made during this sprint?"

List the project doc files found in the repo (e.g., `docs/prd.md`, `docs/adr.md`, `docs/sdr.md`, `docs/threat-model.md`). Check their last git commit date relative to source code changes in the sprint. If docs were not touched but source code changed significantly, flag this as a concern.

### Item 3: CHANGELOG Updated

**Automated check.** Verify that `CHANGELOG.md` exists in the repo root and that it contains an entry for the current version or an `[Unreleased]` section with content.

```bash
# Check CHANGELOG.md exists and has recent content
test -f CHANGELOG.md && head -30 CHANGELOG.md
```

If the CHANGELOG is missing or the latest section is empty, report FAIL with instructions to update it using Keep a Changelog format.

### Item 4: Release Manifest Written

**Automated check.** Look for `docs/releases/v<version>.md` matching the version being released. If the releases directory does not exist or no manifest matches the current version, report FAIL and describe the expected manifest contents: Code changes, Project Docs changes, Content changes, Infrastructure changes, Test breakdown, Stories completed.

### Item 5: Metrics Recorded (including Token Consumption)

**Conditional check.** Two sub-items:

**5a: Token consumption.** Invoke the **token-analysis** skill's sprint close workflow. This runs `owb metrics tokens` for the sprint date range, writes the cost section to the retro, and updates the tracking Google Sheet. If the token-analysis skill is available, run it. If not, run `owb metrics tokens --since <sprint_start> --until <sprint_end>` directly and include the summary in the retro manually.

**5b: Pipeline metrics.** Determine if the project has an active pipeline metrics system (look for metrics configuration, metrics directory, or pipeline metrics files). If metrics are active, prompt the operator to confirm metrics have been recorded for this sprint. If no metrics system is detected, report SKIP for 5b.

### Item 6: Vault Audit

**Automated check.** If the project uses an Obsidian vault, run the vault-audit skill (or equivalent mechanical and semantic checks). Sprint completion often involves bulk edits to project docs, status files, bootstrap, retro-log, and decisions index. These edits are high-risk for broken wiki links, stale references, and structural drift. The audit catches issues introduced during close-out itself, not just during active development.

Per the development-process policy, this is a sprint completion gate, not an optional post-step. If vault audit finds issues, they must be fixed before the sprint can close.

If the project does not use an Obsidian vault, report SKIP.

### Item 7: Tag the Release

**Prompt the operator.** This step happens after the PR merges, not before. Remind the operator:

"After the PR merges, tag the release with `git tag v<version>` and push the tag. Do not tag before the merge."

Report this item as PENDING until the operator confirms the PR has merged and the tag has been pushed.

## Summary Output

Present a final table:

```
## Sprint Completion Summary — v<version>

| # | Item                    | Status       | Notes                     |
|---|-------------------------|--------------|---------------------------|
| 1 | Stories / tests green   | PASS / FAIL  | X tests passed, Y failed  |
| 2 | Project docs updated    | PASS / NEEDS REVIEW | Operator confirmed / flagged |
| 3 | CHANGELOG updated       | PASS / FAIL  | Entry found / missing     |
| 4 | Release manifest        | PASS / FAIL  | docs/releases/vX.Y.Z.md  |
| 5 | Metrics recorded        | PASS / SKIP  | Active / not configured   |
| 6 | Vault audit             | PASS / FAIL / SKIP | Issues found / clean / no vault |
| 7 | Release tagged          | PENDING      | Tag after PR merge        |
```

If any item is FAIL, the sprint is not ready to close. List the blocking items and what the operator needs to do to resolve them.
