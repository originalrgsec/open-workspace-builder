---
type: policy
scope: all-projects
created: 2026-03-16
origin: workspace-builder Sprint 4 design discussion (metrics system and release notes conventions)
tags: [policy, process, sprint, release-notes, metrics]
---

# Development Process

## Purpose

This document defines the project lifecycle standards that apply across all Volcanix projects where Claude Code or Cowork handles implementation. It covers the process layer: how to run a sprint end-to-end, what happens at sprint completion, and how to maintain project documentation alongside code.

This sits above two other layers that are already documented:

- **Coding layer:** ECC rules (`development-workflow.md`, `git-workflow.md`, `coding-style.md`, `testing.md`, `security.md`) define how to write code within a session: TDD cycle, conventional commits, file size limits, coverage targets, security pre-commit checks.
- **Quality gate layer:** integration-verification-policy and oss-health-policy define how to verify code: workflow-level acceptance criteria, pipeline smoke tests, CLI contract verification, dependency health checks.

This document defines how to run a sprint end-to-end and what artifacts must be updated at each phase.

## Sprint Completion Checklist

Every sprint ends with the following before the final PR is merged:

### 1. Stories Complete

All stories in the sprint pass their acceptance criteria. Tests are green. The pipeline smoke test (per integration-verification-policy) has been run.

### 2. Project Docs Updated

Project documents (PRD, ADR, SDR, threat model, specs) are updated to reflect any design changes made during the sprint. This includes new use cases, architectural decisions, module designs, threat analysis for new components, and story additions or modifications. Project docs ship in the same repo as the code and must stay in sync.

The SDR sprint plan section must include an entry for the completing sprint with the stories delivered, goal summary, and final test count. This is a sprint-close gate, not optional. Origin: RETRO-005 identified two sprints of SDR drift; RETRO-006 escalated to a checklist item.

Changes to project docs during a sprint are expected and normal. The goal is not to prevent doc changes but to ensure they are captured before the sprint closes, not left as undocumented drift.

### 3. Release Notes Updated

Update CHANGELOG.md in the repo root with a summary of code and project doc changes. Use Keep a Changelog format (https://keepachangelog.com/en/1.1.0/). Standard sections: Added, Changed, Deprecated, Removed, Fixed, Security.

Write or update the detailed manifest in `docs/releases/v<version>.md`. The manifest provides a full inventory of everything that changed, categorized by: Code (modules added/modified/removed), Project Docs (document changes), Content (skills, templates, ECC updates), Infrastructure (CI, config, packaging), Tests (count and category breakdown), Stories Completed (list with one-line descriptions).

The CHANGELOG entry links to the manifest for the full picture.

Tag the release after the PR merges.

### 4. Supply Chain Verification

Verify all dependencies pass the quarantine window and scan battery before the sprint closes. Run `owb audit pins` to confirm no dependency was published within the 7-day quarantine window. Run `owb audit gate --all` to confirm all direct dependencies pass the full scan battery (CVEs, malware indicators, advisory flags). If any dependency fails, resolve it before merging the final PR. See `supply-chain-protection.md` for the full policy.

### 5. Vault Audit

Run the vault-audit skill (or equivalent mechanical + semantic checks) before declaring the sprint closed. Sprint-level documentation changes (status.md, bootstrap, retro-log, decisions index, policy files) are high-risk for link rot and structural drift. The audit catches issues introduced during close-out itself, not just during active development. Origin: RETRO-006 — vault audit was omitted from Sprint 9 close-out until the owner caught it.

### 6. Metrics Recorded

Metrics recording is mandatory for every sprint on every project with a git repo.

**Sprint start:** Run `owb metrics record` to flush any unrecorded sessions from prior work into the ledger. This ensures the ledger is clean before the sprint begins and that session costs from the previous sprint are not misattributed.

**During sprint:** Tag sessions with story IDs as you work: `owb metrics record --story {PREFIX}-S{NNN}`. Run this at the end of each session or at natural breakpoints. The command is idempotent — it discovers all Claude Code session files, parses token usage, and appends entries to the ledger, skipping sessions already recorded.

**Sprint end:** Run `owb metrics record` to capture all remaining sessions. Then run `owb metrics by-story --since {sprint-start-date}` to produce the sprint cost summary. Include the total sprint cost in the release notes manifest.

The `--story` tag enables cost attribution at the story level. Sprint-level aggregation comes from grouping the story IDs that belong to the sprint. The `owb metrics by-story` command produces this breakdown from the ledger.

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

When a sprint produces a finding that applies beyond the originating project, it becomes a cross-project policy in `code/`. Examples:

- integration-verification-policy — originated from ingest-pipeline Phase 1 retro
- oss-health-policy — originated from dependency evaluation across multiple projects
- This document — originated from workspace-builder Sprint 4 design discussion

## Retrospective Requirements

Retrospectives are conducted after each sprint, phase, or significant incident. The retro template lives at `_templates/retrospective.md`.

### When to Retro

A retrospective is required after any sprint completion, any production incident or feature regression, any phase transition (design → implementation → production), and any session where more than two bugs are discovered that trace to a common root cause.

### Linked Deliverables Are Mandatory

Every retro must produce at least one concrete deliverable linked in the "Linked Deliverables" section. Acceptable deliverable types: bug stories, new stories, cross-project policy documents, process changes to working-style.md or other process docs, config or template updates, and additions to the sprint acceptance gate.

A retro that identifies problems but links to zero deliverables is incomplete. The deliverable does not need to be implemented immediately, but it must be filed and tracked.

### Numbering Convention

Retros use a global sequential ID: `RETRO-NNN`. The numbering is global across all projects because retros frequently span multiple projects or cover process-level concerns that are not scoped to a single codebase. The next available ID is tracked in the `next_id` frontmatter field of `self/retro-log.md`.

Retro files are named `RETRO-NNN-short-description.md` (e.g., `RETRO-004-timeline-digest-regression.md`).

### Retro Log and File Locations

All retros are indexed in `self/retro-log.md` with a summary, linked deliverables reference, and open items for the next retro. Standalone retros (those with root cause analysis, multiple issues, or significant length) live in `self/retros/RETRO-NNN-*.md`. Lightweight retros are inline in the retro-log with the same RETRO-NNN heading.

Retros do not live in project folders. Even when a retro is triggered by a single project, the findings and process changes often apply cross-project. The retro-log and `self/retros/` are the canonical locations.

### Follow-Through Verification

The "Open Items for Next Retro" section in each retro entry creates a verification chain. The next retro must address those open items explicitly, confirming whether the actions taken actually improved the process. If an open item has not been addressed by the next retro, it escalates to a standing item until resolved.

## Story ID Convention

Story IDs use a three-character project prefix followed by a sequential number: `{PREFIX}-S{NNN}`. This prevents ambiguity when referencing stories across projects in session logs, decision records, and the bootstrap file.

| Project | Prefix |
|---------|--------|
| open-workspace-builder | OWB |
| claude-workspace-builder | CWB |
| ingest-pipeline | INP |
| claude-skills | CSK |

File names follow the pattern `{PREFIX}-S{NNN}-short-description.md`. The frontmatter `id` field uses the same prefixed format.

Story numbers are sequential per project. Stories in a later sprint must have higher numbers than stories in the preceding sprint for the same project.

Stories created before this convention (pre-OWB Sprint 7, pre-CWB Sprint 6) retain their unprefixed IDs. When reading an unprefixed story ID, interpret it in the context of the project folder where the story file lives.

When a new project is created, assign a unique three-character prefix and add it to this table.

## Release Versioning

Projects use Semantic Versioning (https://semver.org/). For projects not yet at 1.0 (all current Volcanix projects), minor version bumps indicate feature additions (sprint completion) and patch bumps indicate bug fixes.

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

### Metrics Baseline

Run `owb metrics baseline <project-path>` to establish the zero-point snapshot. This records source LOC, test LOC, test count, commit count, and per-module breakdown at the project's starting state. The baseline is a one-time operation; subsequent sprints rely on session recording (checklist item 6) for ongoing cost and effort tracking.

For existing projects that have not yet established a baseline, run `owb metrics baseline` once. Future baselines can be compared against this initial snapshot to measure growth over time.

## Applying This Policy

This policy applies to all Volcanix projects with a git repo and sprint-based development. Reference this document in each project's SDR sprint plan section rather than duplicating the checklist inline.

For existing projects, adopt the sprint completion checklist starting with the next sprint. Retroactive release notes for prior sprints are optional but recommended for projects that have shipped code (currently workspace-builder and ingest-pipeline).
