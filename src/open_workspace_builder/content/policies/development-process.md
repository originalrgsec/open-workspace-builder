---
type: policy
scope: all-projects
created: 2026-03-16
tags: [policy, process, sprint, release-notes, metrics]
---

# Development Process

## Purpose

This document defines the project lifecycle standards that apply across all projects in a workspace where an AI coding agent handles implementation. It covers the process layer: how to run a sprint end-to-end, what happens at sprint completion, and how to maintain project documentation alongside code.

This sits above two other layers that are already documented:

- **Coding layer:** ECC rules (`development-workflow.md`, `git-workflow.md`, `coding-style.md`, `testing.md`, `security.md`) define how to write code within a session: TDD cycle, conventional commits, file size limits, coverage targets, security pre-commit checks.
- **Quality gate layer:** `integration-verification-policy.md` and `oss-health-policy.md` define how to verify code: workflow-level acceptance criteria, pipeline smoke tests, CLI contract verification, dependency health checks.

This document defines how to run a sprint end-to-end and what artifacts must be updated at each phase.

## Scrub Skills (mid-sprint quality pass)

Three Claude Code built-in skills run against changed code **mid-sprint**, before sprint close but after the main implementation stories have landed. They do not replace CI, code review, or security review — they are additive passes that catch different classes of issue than the automated gates.

### Definitions

| Skill | Purpose | Run when |
|---|---|---|
| `/simplify` | Non-destructive clarity + reuse pass. Identifies dead abstractions, redundant indirection, and missed opportunities to reuse existing code. Produces suggested refactors; no deletions. | After the sprint's implementation stories are merged to the integration branch; before `/code-review`. Blocking if any suggestion materially changes behaviour (file a story and address) — advisory if cosmetic. |
| `/code-review` | Correctness + security + design findings at HIGH / MED / LOW severity. | After `/simplify` lands. CRITICAL and HIGH are blocking — fix in-sprint or spawn a follow-up story before close. MED / LOW default to a tech-debt bundle story unless the bundle would exceed a 2-pt budget. |
| `/refactor-clean` | Destructive pass: remove dead code, delete unused public API surface, produce a public-API changelog for downstream consumers. | After `/code-review` fixes land. Blocking for the sprint that runs it. Output includes a `docs/public-api-changes.md` entry that downstream projects absorb in their next sprint. |

### Sequencing

Run in strict order: `/simplify` → `/code-review` → `/refactor-clean`. Non-destructive before destructive so the destructive pass operates on post-cleanup code (fewer false positives, smaller diffs). A static-type scrub (e.g., pyright strict-mode triage) runs alongside the trio only when the project-local type-budget policy has been updated since the last scrub.

### Blocking vs advisory status

- `/simplify`: blocking only when a suggestion is behaviour-changing.
- `/code-review`: blocking for CRITICAL and HIGH findings; advisory for MED / LOW unless they bundle into a 2-pt story.
- `/refactor-clean`: blocking for the sprint that runs it; the downstream absorption story (for projects that consume your package) is blocking for the consumer's next sprint.

### Quick reference

See `scrub-skills-quick-reference.md` for a single-page summary.

## Sprint Completion Trigger

When all stories in a sprint are implemented and the full test suite passes green (coverage meets threshold, linter clean), the sprint close procedure begins automatically. The agent proceeds directly into the Sprint Completion Checklist below without waiting for user confirmation. This is a standing instruction, not a per-sprint decision. If something unexpected surfaces during close (test regression, coverage drop, vault conflict), pause and surface it to the owner.

## Sprint Completion Checklist

Every sprint ends with the following before the final PR is merged. Items 1–10 are all mandatory; items 5 and 6 can legitimately be "n/a" for certain project shapes (vault-only sprints, docs-only sprints, projects without live infrastructure). Skipping without a recorded reason is a defect.

### 1. Stories Complete

All stories in the sprint pass their acceptance criteria. Tests are green. The pipeline smoke test (per `integration-verification-policy.md`) has been run.

### 2. Project Docs Updated

Project documents (PRD, ADR, SDR, threat model, specs) are updated to reflect any design changes made during the sprint. This includes new use cases, architectural decisions, module designs, threat analysis for new components, and story additions or modifications. Project docs ship in the same repo as the code and must stay in sync.

The SDR sprint plan section must include an entry for the completing sprint with the stories delivered, goal summary, and final test count. This is a sprint-close gate, not optional.

Changes to project docs during a sprint are expected and normal. The goal is not to prevent doc changes but to ensure they are captured before the sprint closes, not left as undocumented drift.

### 3. Release Notes Updated

Update `CHANGELOG.md` in the repo root with a summary of code and project doc changes. Use Keep a Changelog format (https://keepachangelog.com/en/1.1.0/). Standard sections: Added, Changed, Deprecated, Removed, Fixed, Security.

Write or update the detailed manifest in `docs/releases/v<version>.md`. The manifest provides a full inventory of everything that changed, categorized by: Code (modules added/modified/removed), Project Docs (document changes), Content (skills, templates, ECC updates), Infrastructure (CI, config, packaging), Tests (count and category breakdown), Stories Completed (list with one-line descriptions).

**Include the sprint's quality-gate table and total metrics in the manifest** (see item 7).

The `CHANGELOG` entry links to the manifest for the full picture.

Tag the release after the PR merges.

### 3a. GitHub Release — Verify, Don't Create

For projects that ship a release pipeline through GitHub Actions on `v*` tag push, the release workflow **owns** the Release object. Sprint close **verifies** the workflow created it with the expected assets and a `CHANGELOG`-sourced body. **Do not run `gh release create` manually during close** — it races the workflow's `Create GitHub Release` step and any downstream notification gates. If the workflow fails to create the Release, re-dispatch via `gh workflow run release.yml --ref main -f tag=vX.Y.Z` rather than creating it by hand.

**Expected assets per the project's release workflow:**

- Source distribution (`*.tar.gz`)
- Built wheel or equivalent platform artifact (`*.whl` for Python projects)
- Project-own SBOM in CycloneDX JSON format (describing the project's own dependency tree, not user-generated content)
- Any additional assets declared by the project's release workflow

**Expected Release body:** the section of `CHANGELOG.md` matching the released version, sourced via the project's changelog extraction helper. An empty or mismatched Release body is a sprint-close blocker — fix the `CHANGELOG` and re-run the workflow before closing the sprint.

**Pre-release tags** (matching `*-rc.*`, `*-alpha.*`, `*-beta.*`) produce a prerelease-flagged Release, not a canonical release. These are expected during RC rehearsal on scratch branches. Delete RC tags and their Release objects after validation; they are not part of the release history.

**Historical tag backfill is out of scope.** Projects that adopted this gate after shipping canonical releases under a prior process have no Release objects for those historical tags. Sprint-close verification applies only from the adoption point forward. Do not run release workflows against historical tags to backfill Release objects inside a sprint; file a separate story if retroactive backfill is ever needed.

### 4. Supply Chain Verification

Verify all dependencies pass the quarantine window and scan battery before the sprint closes. Run `owb audit pins` to confirm no dependency was published within the 7-day quarantine window. Run `owb audit gate --all` to confirm all direct dependencies pass the full scan battery (CVEs, malware indicators, advisory flags). If any dependency fails, resolve it before merging the final PR. See `supply-chain-protection.md` for the full policy.

### 5. Post-Deploy Verification (Projects with Live Infrastructure)

For projects that run against live infrastructure, run the project's health validation command after the release tag is created and verify all checks pass. A passing health run confirms that the release did not break the live pipeline. If health fails, investigate and fix before declaring the sprint closed.

### 6. Scrub Skills Record

Note in the sprint-close session log which scrub skills ran this sprint (`/simplify`, `/code-review`, `/refactor-clean`, or any subset) and link to the relevant PRs. Sprints that did not run the scrub (vault-only sprints, docs-only sprints, or small-scope sprints below the threshold) record "scrub skipped" and the reason. This is a record-keeping line, not a gate — sprint close is not blocked on running the scrub. Full definitions are under **Scrub Skills** earlier in this document.

### 7. Quality-Metrics Report

Mandatory, every sprint, every project with a git repo. Record and report:

- `owb metrics record` run at sprint start (to flush prior sessions), during execution (per-story tagging: `owb metrics record --story {PREFIX}-S{NNN}`), and at sprint end.
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

**During sprint:** Tag sessions with story IDs as you work: `owb metrics record --story {PREFIX}-S{NNN}`. Run this at the end of each session or at natural breakpoints. The command is idempotent — it discovers all agent session files, parses token usage, and appends entries to the ledger, skipping sessions already recorded.

The `--story` tag enables cost attribution at the story level. Sprint-level aggregation comes from grouping the story IDs that belong to the sprint. The `owb metrics by-story` command produces this breakdown from the ledger.

### 8. Vault Audit

Run the `vault-audit` skill (or equivalent mechanical + semantic checks) before declaring the sprint closed. Sprint-level documentation changes (status.md, bootstrap, retro-log, decisions index, policy files) are high-risk for link rot and structural drift. The audit catches issues introduced during close-out itself, not just during active development.

### 9. Research Review

Review all research notes tagged to this project (search `projects:` frontmatter field in `research/processed/`). For each note, assign a disposition in the project's `_index.md` Research section:

- **pending** — not yet reviewed in a sprint planning context
- **accepted** — influenced a story, decision, or design change (link the artifact)
- **rejected** — evaluated and dismissed (one-line reason)
- **deferred** — interesting but not actionable now

Notes tagged during inbox triage are tentative assignments. Sprint planning is where they get a real review. If a note's project tag is wrong, update the frontmatter to the correct project.

### 10. PII and Secrets Audit

Run the `vault-pii-audit` skill in session mode against all files modified during the sprint. This catches credentials, API keys, personal identifiers, and other sensitive data that may have entered vault files through research imports, session logs, or design documents. If findings are confirmed, redact and update the encrypted PII store per `pii-handling-policy.md`. The secrets inventory at `.secure/secrets-inventory.md` must be current before the sprint closes.

## Project Documentation Standards

### Which Docs

Every project that reaches the Design phase or beyond maintains the following documents in its repo:

- **PRD** — use cases, goals, personas, success criteria
- **ADR** — C4 model, architectural decisions with alternatives and consequences, technology stack, data flow diagrams
- **SDR** — module designs with interfaces, data schemas, story breakdown, sprint plan
- **Threat Model** — STRIDE analysis per DFD element, risk assessment, mitigations with NIST 800-53 mapping

Additional docs (specs, retros, session logs) are added as needed per project.

### When to Update

Project docs are updated during a sprint when:

- A new feature or capability is added (PRD: use case, goal; ADR: decision if architectural; SDR: module design, story; Threat Model: if new data store or data flow)
- An existing design changes during implementation (all affected docs)
- A retrospective identifies a process or design gap (relevant doc + cross-project policy if applicable)

The sprint completion checklist (item 2) is the backstop, not the primary update trigger. Docs should be updated as decisions are made, not batched at sprint end.

### Cross-Project Policies

When a sprint produces a finding that applies beyond the originating project, it becomes a cross-project policy in the `code/` folder of the vault. Examples distributed with this workspace scaffold:

- `integration-verification-policy.md`
- `oss-health-policy.md`
- This document (`development-process.md`)

## Retrospective Requirements

Retrospectives are conducted after each sprint, phase, or significant incident. The retro template lives at `_templates/retrospective.md`.

### When to Retro

A retrospective is required after any sprint completion, any production incident or feature regression, any phase transition (design → implementation → production), and any session where more than two bugs are discovered that trace to a common root cause.

### Linked Deliverables Are Mandatory

Every retro must produce at least one concrete deliverable linked in the "Linked Deliverables" section. Acceptable deliverable types: bug stories, new stories, cross-project policy documents, process changes to working-style.md or other process docs, config or template updates, and additions to the sprint acceptance gate.

A retro that identifies problems but links to zero deliverables is incomplete. The deliverable does not need to be implemented immediately, but it must be filed and tracked.

### Numbering Convention

Retros use a global sequential ID: `RETRO-NNN`. The numbering is global across all projects because retros frequently span multiple projects or cover process-level concerns that are not scoped to a single codebase. The next available ID is tracked in the `next_id` frontmatter field of `self/retro-log.md`.

Retro files are named `RETRO-NNN-short-description.md`.

### Retro Log and File Locations

All retros are indexed in `self/retro-log.md` with a summary, linked deliverables reference, and open items for the next retro. Standalone retros (those with root cause analysis, multiple issues, or significant length) live in `self/retros/RETRO-NNN-*.md`. Lightweight retros are inline in the retro-log with the same RETRO-NNN heading.

Retros do not live in project folders. Even when a retro is triggered by a single project, the findings and process changes often apply cross-project. The retro-log and `self/retros/` are the canonical locations.

### Follow-Through Verification

The "Open Items for Next Retro" section in each retro entry creates a verification chain. The next retro must address those open items explicitly, confirming whether the actions taken actually improved the process. If an open item has not been addressed by the next retro, it escalates to a standing item until resolved.

## Story ID Convention

Story IDs use a three-character project prefix followed by a sequential number: `{PREFIX}-S{NNN}`. This prevents ambiguity when referencing stories across projects in session logs, decision records, and the bootstrap file.

Example mapping (add your own projects as you create them):

| Project | Prefix |
|---------|--------|
| open-workspace-builder | OWB |
| claude-workspace-builder | CWB |
| your-project-name | PRJ |

File names follow the pattern `{PREFIX}-S{NNN}-short-description.md`. The frontmatter `id` field uses the same prefixed format.

Story numbers are sequential per project. Stories in a later sprint must have higher numbers than stories in the preceding sprint for the same project.

When a new project is created, assign a unique three-character prefix and add it to your project's prefix table.

## Project Status Lifecycle

The `status` field in each project's `_index.md` frontmatter tracks where the project is in its lifecycle. Status values are ordered; a project moves forward through these phases (though it may skip phases or move directly to a terminal state).

### Active Phases

| Status | Meaning | Sprint Work? |
|--------|---------|-------------|
| `concept` | Idea captured, no design work started | No |
| `research` | Active investigation, no design artifacts yet | No |
| `design` | Design documents (PRD, ADR, SDR, threat model) in progress | No |
| `design-complete` | All design documents written, ready for implementation | No |
| `development` | Active sprint-based implementation | Yes |
| `production` | Shipped, running, and receiving active feature work | Yes |
| `maintenance` | Feature-complete, no planned active development. Bugs, dependency updates, and security patches only. | No (reactive only) |

### Terminal States

| Status | Meaning |
|--------|---------|
| `evaluated` | Assessment project completed (evals, proof-of-concepts) |
| `archived` | No longer active, kept for reference |

### Transitions

- `concept` → `research` or `design` (owner decides to pursue)
- `design` → `development` (SDR complete, Sprint 1 planned)
- `development` → `production` (first release, pipeline activated or users onboarded)
- `production` → `maintenance` (feature-complete, no planned sprints)
- Any phase → `archived` (project shelved or abandoned)

A project entering `maintenance` should update `_bootstrap.md` to reflect the new phase and remove active next-action items. Maintenance projects are not included in sprint planning unless a bug or security issue triggers reactive work.

## Release Versioning

Projects use Semantic Versioning (https://semver.org/). For projects not yet at 1.0, minor version bumps indicate feature additions (sprint completion) and patch bumps indicate bug fixes. For projects at 1.0 or above, follow standard SemVer rules: breaking changes bump major, new features bump minor, bug fixes bump patch.

## New Project Setup

When a new project repo is created, the following one-time setup steps are required before the first sprint begins:

### Pre-Commit Hooks

Run `owb security hooks install <project-path>` to generate `.pre-commit-config.yaml` and activate the hooks. The default hook set includes:

| Hook | Purpose |
|------|---------|
| **gitleaks** | Secrets detection on staged files |
| **ruff --fix** | Python linting with auto-fix |
| **ruff-format** | Python code formatting |
| **trivy** | Vulnerability scanning of lockfiles and dependencies (local, requires `trivy` binary) |
| **semgrep** | SAST on staged Python files |

If `owb init` detects sibling projects without pre-commit hooks, it prompts to install them. For existing projects that predate this policy, run `owb security hooks install` manually.

Pre-commit hooks are a commit-time gate. They complement but do not replace the sprint-level security scans (`owb security scan --all`, `owb audit gate --all`).

### Security Drift Baseline

Run `owb security drift <project-path> --update-baseline` to establish the initial directive drift baseline. This creates `.owb/drift-baseline.json`, which records the current state of all security-relevant directives (CLAUDE.md, settings, hook configs, MCP definitions). Future runs of `owb security drift` compare against this snapshot to detect unauthorized or accidental changes.

Commit the baseline file to the repo so it is versioned alongside the code. The baseline must be updated whenever a deliberate change is made to project directives (e.g., adding a new MCP server, modifying CLAUDE.md instructions, or changing hook configuration). Run `owb security drift <project-path> --update-baseline` after such changes and commit the updated file.

For existing projects that predate this policy, run the baseline command once and commit the result.

### Metrics Baseline

Run `owb metrics baseline <project-path>` to establish the zero-point snapshot. This records source LOC, test LOC, test count, commit count, and per-module breakdown at the project's starting state. The baseline is a one-time operation; subsequent sprints rely on session recording (checklist item 7) for ongoing cost and effort tracking.

For existing projects that have not yet established a baseline, run `owb metrics baseline` once. Future baselines can be compared against this initial snapshot to measure growth over time.

## Applying This Policy

This policy applies to all projects in a workspace with a git repo and sprint-based development. Reference this document in each project's SDR sprint plan section rather than duplicating the checklist inline.

For existing projects, adopt the sprint completion checklist starting with the next sprint. Retroactive release notes for prior sprints are optional but recommended for projects that have shipped code.
