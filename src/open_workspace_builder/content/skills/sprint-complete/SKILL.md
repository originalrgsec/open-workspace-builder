---
name: sprint-close
description: >-
  Walk through the full sprint completion checklist to ensure no steps are
  missed. Use this skill when finishing a sprint, closing a release, or when
  the user says 'sprint complete', 'close the sprint', 'sprint close', or
  'release checklist'.
---

# Sprint Completion Orchestration

This skill walks through the development-process sprint completion checklist, running automated checks where possible and prompting the operator for judgment items.

## When to Run

- Sprint is finished and the final PR is about to merge
- Operator says "sprint complete", "close the sprint", "sprint close", "release checklist", or "are we done"
- Before tagging a release
- A commit-message hook prints a reminder about this skill

## Important: Fresh Context

This skill exists specifically to solve the problem of process instructions being compressed out of context during long sessions. When invoked, it reads the checklist source fresh from the vault or policy file rather than relying on cached context. If the session is long and you are uncertain whether you have the full checklist, re-read `Obsidian/code/development-process.md` before proceeding.

## Checklist Execution

Work through each item sequentially. For each item, report its status as PASS, FAIL, SKIP, or NEEDS REVIEW. Produce a summary table at the end.

### Item 0: Session Budget Check

**Automated check.** Before running the full closeout, assess whether the current session has headroom for it.

The recommended session budget cap is 8 story points. Sprint closeout itself consumes approximately 20-30kT of context. If the session has already executed a large sprint (9+ story points), warn the operator:

"This session has executed a large sprint. Consider starting a fresh session for closeout to avoid context pressure degrading the quality of documentation and vault updates."

If the operator chooses to proceed in the current session, continue but flag this as a risk in the summary.

### Item 1: Stories Complete — All AC Green

**Automated check.** Run the project test suite and verify all tests pass.

```bash
# Detect test runner and execute
# Python: uv run pytest or pytest
# Node: npm test
# Go: go test ./...
```

If tests fail, report the failures and stop. The sprint cannot close with failing tests.

**Integration verification sub-check.** Check whether the project has:
- A doctor command (e.g., `homeops doctor`)
- Tests marked with `@pytest.mark.integration_verification`
- A pipeline smoke test

If any exist, they must be executed as part of this item. If the project has a doctor command, run it and verify all checks pass. If the project has integration verification tests, run them. If neither exists, prompt the operator to confirm that system boundaries were manually verified or that no system boundaries were touched.

Per the integration verification policy, the application's primary command must be exercised end-to-end before sprint closure.

### Item 2: Project Docs Updated

**Judgment item — prompt the operator.**

Ask: "Have project documents (PRD, ADR, SDR, threat model) been updated to reflect design changes made during this sprint?"

List the project doc files found in the repo (e.g., `docs/prd.md`, `docs/adr.md`, `docs/sdr.md`, `docs/threat-model.md`). Check their last git commit date relative to source code changes in the sprint. If docs were not touched but source code changed significantly, flag this as a concern.

**SDR sprint plan gate.** The SDR must contain an entry for the completing sprint with stories delivered, goal summary, and final test count. Check for the sprint number in the SDR. If missing, report FAIL.

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

**5a: Token consumption.** Run `owb metrics record` to flush any unrecorded sessions to the ledger. Then run `owb metrics tokens --since <sprint_start> --until <sprint_end>` (or `owb metrics by-story`) to produce the sprint cost summary. Include the summary in the release manifest.

**5b: Pipeline metrics.** Determine if the project has an active pipeline metrics system (look for metrics configuration, metrics directory, or pipeline metrics files). If metrics are active, prompt the operator to confirm metrics have been recorded for this sprint. If no metrics system is detected, report SKIP for 5b.

### Item 6: Vault Audit

**Automated check.** If the project uses an Obsidian vault, run the vault-audit skill (or equivalent mechanical and semantic checks). Sprint completion often involves bulk edits to project docs, status files, bootstrap, retro-log, and decisions index. These edits are high-risk for broken wiki links, stale references, and structural drift. The audit catches issues introduced during close-out itself, not just during active development.

Per the development-process policy, this is a sprint completion gate, not an optional post-step. If vault audit finds issues, they must be fixed before the sprint can close.

**6a: Research review.** Review all research notes tagged to this project (search `projects:` frontmatter in `research/processed/`). Assign dispositions: pending, accepted, rejected, or deferred.

**6b: PII and secrets audit.** Run the `vault-pii-audit` skill against files modified during the sprint. If findings are confirmed, redact per the PII handling policy.

If the project does not use an Obsidian vault, report SKIP.

### Item 7: Memory Hygiene Check

**Automated check.** Scan the project's Claude memory directory for entries that violate the memory delineation policy:

- Memory entries longer than 10 lines (should be vault notes instead)
- Memory entries that describe project state, decisions, or architecture (should be in the vault)
- Memory entries that duplicate content already in CLAUDE.md or vault files

Report any violations as NEEDS REVIEW with a recommendation to migrate or delete.

### Item 8: Tag the Release

**Prompt the operator.** This step happens after the PR merges, not before. Remind the operator:

"After the PR merges, tag the release with `git tag v<version>` and push the tag. Do not tag before the merge."

Report this item as PENDING until the operator confirms the PR has merged and the tag has been pushed.

## Summary Output

Present a final table:

```
## Sprint Completion Summary — v<version>

| # | Item                    | Status       | Notes                     |
|---|-------------------------|--------------|---------------------------|
| 0 | Session budget          | PASS / WARN  | Within cap / over budget  |
| 1 | Stories / tests green   | PASS / FAIL  | X tests passed, Y failed  |
| 1a| Integration verification| PASS / SKIP  | Doctor / smoke test run   |
| 2 | Project docs updated    | PASS / NEEDS REVIEW | Operator confirmed / flagged |
| 3 | CHANGELOG updated       | PASS / FAIL  | Entry found / missing     |
| 4 | Release manifest        | PASS / FAIL  | docs/releases/vX.Y.Z.md  |
| 5 | Metrics recorded        | PASS / SKIP  | Active / not configured   |
| 6 | Vault audit             | PASS / FAIL / SKIP | Issues found / clean / no vault |
| 7 | Memory hygiene          | PASS / NEEDS REVIEW | Clean / violations found |
| 8 | Release tagged          | PENDING      | Tag after PR merge        |
```

If any item is FAIL, the sprint is not ready to close. List the blocking items and what the operator needs to do to resolve them.
