# Sprint Workflow

This rule is optional and intended for teams using sprint-driven development workflows. It does not interfere with ad-hoc usage patterns. Remove this file if your project does not use sprints.

> **Authoritative checklist:** the `Sprint Completion Checklist` in `development-process.md` (bundled with OWB under `code/development-process.md` in the scaffolded vault). This file is the session-mechanics gloss; the policy is the source of truth for what must happen before a sprint is "closed". If they disagree, the policy wins.

## Autonomous End-to-End Contract

Once the operator says "start", "go", "kick off", "ship it", or any equivalent confirming a planned sprint, every remaining phase runs autonomously in the same session. Do not ask before each phase. The phases are:

1. **Kickoff** — sprint plan file, branch cut, frontmatter, status, project `_index`, bootstrap manifest (see *Autonomous Sprint Mechanics* below).
2. **Execution** — stories implemented per their acceptance criteria; TDD; silent code-review + security-review agents; commits pushed to the sprint branch.
3. **Sprint close** — *Sprint Completion Checklist* in the bundled `development-process.md` policy, executed in order. No prompts. Release PR created, merged to main, tag pushed, release workflow runs, quality-metrics report recorded.
4. **Session close** — session log, status.md, project `_index.md`, bootstrap, story frontmatters flipped to `done`, `vault-pii-audit` run, vault commit + push.

The only reasons to pause during an autonomous run:

- A test regression, coverage drop, CI failure, or security-reviewer HIGH/CRITICAL that cannot be resolved inside the current sprint's scope.
- A destructive or cross-account git op surfaces (see *Gated Actions*).
- The operator explicitly interrupts.

All other friction — "should I commit now?", "do you want me to open the PR?", "do you want me to tag the release?" — is dead weight. Skip it.

### When clarifying questions are allowed

During **sprint planning only**. Once the operator has confirmed the scope, story set, order, and deferrals, every downstream decision is covered by the story files and the checklists below. Re-asking during execution or close is a defect. If a genuinely ambiguous decision surfaces mid-execution that the story file does not cover, prefer the smallest change that matches the story's acceptance criteria and note the decision in the session log — don't pause to ask.

## Autonomous Sprint Mechanics

When the operator confirms a sprint plan — scope, story set, and order — execute the full mechanical follow-through as one atomic unit. Do NOT list these as "optional next steps" and ask permission for each one.

The sprint-kickoff unit of work:

1. **Write the sprint plan file** to `projects/<area>/<project>/sprints/sprint-NN-<theme>.md` with the standard frontmatter, goal, theme, stories, DoD, scope, risks.
2. **Cut the sprint branch** from `main` at the current release tag (`git checkout -b sprint-NN-<theme>`). Do not push until first commit.
3. **Update each story file's frontmatter**: `status: planned`, `sprint: NN`. Bump `updated` to today's date.
4. **Update `status.md`** with a new "Last Updated" entry describing the sprint shape, sequencing rationale, and anything explicitly deferred.
5. **Update the project `_index.md`**: add the sprint table row, flip any newly in-scope story rows, bump the project `updated` date.
6. **Update `_bootstrap.md`** manifest line for the project to reflect the new active sprint.

## Rationale

Sprint planning is one task, not a menu of individual approvals. The operator has already made the load-bearing decisions (scope, story selection, order, deferrals) at confirmation time. Everything after that is mechanical bookkeeping: new branch from main, frontmatter bumps, status log entry, index updates, bootstrap line. Asking for each step wastes context and signals uncertainty that isn't there.

## Execution Phase Contract

Once a sprint is confirmed and kicked off, the entire lifecycle runs autonomously: setup, story implementation, repo management, and sprint closeout. All questions are resolved during sprint planning and story writing. Do not re-ask during execution.

### What this overrides during sprint execution

- **"Ask clarifying questions before any non-trivial task"** (from `CLAUDE.md` / project conventions) — stories were scoped during planning. Do not re-ask before implementing a planned story.
- **"Plan First" and "Research & Reuse"** (`development-workflow.md`) — skip these steps when the story file already contains acceptance criteria and an implementation approach. Run them only if a story explicitly says "research spike" or has no implementation section.
- **Policy re-reads** — policies were consulted during sprint planning. Do not re-read policy documents before each story unless the story involves a new dependency or a policy-governed decision not covered by the existing story scope.
- **Security and code quality checklists** (`security.md`, `coding-style.md`) — run these as silent self-checks before commits. Do not prompt the operator to confirm each checklist item.

### Actions that remain gated (always ask before executing)

See `git-workflow.md` for the canonical list of gated git ops. Only truly destructive or cross-account operations remain gated:

- `git push --force` / `--force-with-lease`, history rewrite on published refs, deleting committed work
- `git reset --hard` / `git clean -fd` when uncommitted work is present
- Pushing to any remote other than the project's own origin
- Deleting or renaming branches that contain uncommitted work
- Any operation that crosses a configured account boundary (e.g., work vs. personal GitHub accounts)

Non-destructive git ops (PR create, PR merge, release tag, commit, push to sprint branch, push to the project's own `main`) are default-yes per `git-workflow.md`. Sprint-close merge back to main happens autonomously once the sprint-completion checklist runs.

### Actions that are default-yes throughout the sprint

- Creating the sprint branch locally
- Writing/editing project files in the sprint's scope
- Updating story frontmatter within the confirmed sprint scope
- Updating project `_index` and bootstrap entries for the active sprint
- Implementing stories per their acceptance criteria (TDD, code, tests)
- Running code review and security review agents (silently, no prompt)
- Committing and pushing to the sprint branch
- Running the sprint-close checklist (verification, not confirmation)
- **Creating the sprint-close PR, merging to main, and tagging the release** (after the sprint-completion checklist runs)
- Writing session logs at session end

## Sprint Completion Checklist (enumerated)

Mirrors the bundled `development-process.md` "Sprint Completion Checklist". Run in order. Every item that produces a number (tests, coverage, type-check budget, metrics) goes into the release-notes manifest and the session log — not just the CHANGELOG one-liner.

1. **Stories complete.** Full suite green. Coverage ≥ project threshold (default 80%, configure per project). Linter clean. Pipeline smoke test (per `integration-verification-policy`) passed.
2. **Project docs updated.** PRD / ADR / SDR / threat model reflect this sprint's design changes. SDR sprint-plan section gets an entry for the completing sprint with stories delivered, goal, final test count. This is a close-time **gate**, not a nice-to-have.
3. **Release notes.** `CHANGELOG.md` updated in Keep-a-Changelog format. Detailed manifest at `docs/releases/v<version>.md`. Tag the release after the PR merges. **Include the sprint's quality-gate table and total metrics in the manifest** (see item 6).
4. **GitHub Release — verify, don't create.** The release workflow (typically `release.yml` on `v*` tag push) owns the Release object. Sprint close **verifies** the workflow created it with the expected assets (sdist, wheel, CycloneDX SBOM, etc.) and a CHANGELOG-sourced body. **Do not run `gh release create` manually during close** — it races the workflow's `Create GitHub Release` step and any downstream notification gates. If the workflow fails to create the Release, re-dispatch via `gh workflow run release.yml --ref main -f tag=vX.Y.Z` rather than creating it by hand.
5. **Post-deploy verification** (projects with live infrastructure only). Run the project's health command after the tag is created. Failures block close.
6. **Quality-metrics report — mandatory, every sprint, every project with a git repo.** Record and report:
   - `owb metrics record` run at sprint start (flush prior sessions), during execution (per-story tagging: `owb metrics record --story {PREFIX}-S{NNN}`), and at sprint end.
   - `owb metrics by-story --since <sprint-start-date>` → per-story cost breakdown. Include the total in the release manifest.
   - **Quality-gate table** in the release manifest and session log:

     | Gate | Previous | This Sprint | Delta |
     |------|----------|-------------|-------|
     | Tests | … | … | … |
     | Coverage | … | … | … |
     | Type checker (pyright, tsc, mypy — whichever applies) | … | … | … |
     | Linter / formatter | clean | clean | = |
     | SCA (Trivy / pip-audit / npm audit) | clean | clean | = |
     | SAST (Semgrep / equivalent) | clean | clean | = |
     | Sprint cost (tokens / USD) | — | … | — |

     If a gate is absent from the project, list it as `n/a`. Do not silently drop rows.
7. **Scrub-skills record.** Name which scrubs ran this sprint (`/simplify`, `/code-review`, `/refactor-clean`, or subset) in the sprint-close session log. Record-keeping line, not a gate.
8. **Vault audit.** Run `vault-audit` skill (or mechanical + semantic equivalent) before declaring the sprint closed.
9. **Research review.** Dispositions (pending / accepted / rejected / deferred) assigned for each research note tagged to the project in `_index.md` Research section.
10. **PII and secrets audit.** Run `vault-pii-audit` in session mode against all files modified during the sprint. Redact findings per `pii-handling-policy.md`. Secrets inventory at `.secure/secrets-inventory.md` must be current.

Items 1–10 are all mandatory; items 5 and 7 can legitimately be "n/a" or "skipped with reason" for certain project shapes (vault-only sprints, docs-only sprints, projects without live infrastructure). Skipping without a recorded reason is a defect.

## Git Ops Ownership (sprint-close)

All non-destructive git ops during sprint execution and close are default-yes per `git-workflow.md`. Specifically:

- Branch creation (`sprint-<nn>-<theme>` from `main` at the current release tag).
- Commits with descriptive messages per `git-workflow.md` format.
- Sprint branch pushes to `origin` (project's own account).
- Sprint-close PR creation (full title + Summary + Test plan + Follow-through sections).
- CI watch via `gh pr checks <n> --watch`; merge with `gh pr merge <n> --squash --delete-branch` once green.
- `main` fast-forward sync after merge.
- Annotated tag `vX.Y.Z` created and pushed to origin — this is what fires the release workflow. **Do not run `gh release create` manually after the tag push.** The workflow creates the Release object; close verifies it.
- `gh release` is acceptable **only** when re-fetching or inspecting existing Release state (`view`, `list`, `upload --clobber` during replay). Creation belongs to the pipeline.

Destructive or cross-account ops still require explicit confirmation per `git-workflow.md`'s gated list.
